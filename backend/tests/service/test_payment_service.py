from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, func, select

from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.core.services import payment_service as payment_service_module
from app.core.services.payment_service import PaymentService
from app.infrastructure.database.models.outbox import Outbox
from app.infrastructure.database.models.payment import Payment
from app.infrastructure.errors.base import NotFoundException
from app.utils.enums import PaymentStatus
from tests.helpers import fake_http_client, payment_data

pytestmark = pytest.mark.asyncio


class FastProcessing:
    randrange_result = 0

    @staticmethod
    async def sleep(delay: float) -> None:
        return None

    @staticmethod
    def uniform(low: float, high: float) -> float:
        return 0.0

    @classmethod
    def randrange(cls, stop: int) -> int:
        return cls.randrange_result


@pytest.fixture
def fast_processing(monkeypatch) -> type[FastProcessing]:
    stub = FastProcessing
    monkeypatch.setattr(payment_service_module, "asyncio", stub)
    monkeypatch.setattr(payment_service_module, "random", stub)
    return stub


@pytest_asyncio.fixture
async def payment_service(db_session, fast_processing) -> PaymentService:
    return PaymentService(
        repository=PaymentRepository(db_session),
        outbox_repository=OutboxRepository(db_session),
        http_client=fake_http_client(),
    )


async def test_create_payment_persists_event(payment_service, db_session):
    result = await payment_service.create_payment(payment_data(), "order-123")

    assert result.status == PaymentStatus.PENDING
    event = (
        await db_session.execute(
            select(Outbox).where(Outbox.payment_id == result.payment_id)
        )
    ).scalar_one()
    assert event.payload == {"payment_id": str(result.payment_id)}


async def test_create_payment_replay_keeps_single_event(payment_service, db_session):
    await payment_service.create_payment(payment_data(), "order-123")

    replay = await payment_service.create_payment(payment_data(), "order-123")

    assert replay.status == PaymentStatus.PENDING
    events_count = await db_session.scalar(select(func.count()).select_from(Outbox))
    assert events_count == 1


async def test_create_payment_replay_recreates_lost_event(payment_service, db_session):
    result = await payment_service.create_payment(payment_data(), "order-123")
    await db_session.execute(
        delete(Outbox).where(Outbox.payment_id == result.payment_id)
    )
    await db_session.commit()

    replay = await payment_service.create_payment(payment_data(), "order-123")

    assert replay.payment_id == result.payment_id
    event = (
        await db_session.execute(
            select(Outbox).where(Outbox.payment_id == result.payment_id)
        )
    ).scalar_one()
    assert event is not None


async def test_get_payment(payment_service):
    created = await payment_service.create_payment(payment_data(), "order-123")

    payment = await payment_service.get_payment(created.payment_id)

    assert payment.payment_id == created.payment_id
    assert payment.status == PaymentStatus.PENDING


async def test_get_payment_not_found(payment_service):
    with pytest.raises(NotFoundException):
        await payment_service.get_payment(uuid4())


async def test_process_payment_sends_webhook(payment_service, db_session):
    created = await payment_service.create_payment(payment_data(), "order-123")

    await payment_service.process_payment(created.payment_id)

    payment = await db_session.get(Payment, created.payment_id)
    assert payment.status == PaymentStatus.SUCCEEDED
    assert payment.processed_at is not None
    assert payment.webhook_sent_at is not None
    payment_service.http_client.post.assert_called_once()


async def test_process_payment_failed_status(payment_service, db_session, fast_processing):
    fast_processing.randrange_result = 99
    created = await payment_service.create_payment(payment_data(), "order-123")

    await payment_service.process_payment(created.payment_id)

    payment = await db_session.get(Payment, created.payment_id)
    assert payment.status == PaymentStatus.FAILED
    payment_service.http_client.post.assert_called_once()


async def test_process_payment_does_not_resend_webhook(payment_service, db_session):
    created = await payment_service.create_payment(payment_data(), "order-123")
    await payment_service.process_payment(created.payment_id)
    payment_service.http_client.post.reset_mock()

    await payment_service.process_payment(created.payment_id)

    payment_service.http_client.post.assert_not_called()


async def test_process_payment_webhook_failure(payment_service, db_session):
    created = await payment_service.create_payment(payment_data(), "order-123")
    payment_service.http_client = fake_http_client(fail=True)

    with pytest.raises(RuntimeError, match="webhook receiver returned 5xx"):
        await payment_service.process_payment(created.payment_id)

    payment = await db_session.get(Payment, created.payment_id)
    assert payment.webhook_sent_at is None
