import pytest
from sqlalchemy import select

from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.infrastructure.database.models.outbox import Outbox
from app.utils.enums import PaymentStatus
from tests.helpers import payment_data

pytestmark = pytest.mark.asyncio


async def test_create_returns_created(db_session):
    repository = PaymentRepository(db_session)

    payment, created = await repository.create(payment_data(), "order-123")

    assert created is True
    assert payment.status == PaymentStatus.PENDING
    assert payment.idempotency_key == "order-123"
    assert await db_session.get(type(payment), payment.id) is not None


async def test_create_conflict_returns_existing(db_session):
    repository = PaymentRepository(db_session)

    first, _ = await repository.create(payment_data(), "order-123")
    second, created = await repository.create(payment_data(), "order-123")

    assert created is False
    assert second.id == first.id


async def test_get_for_processing(db_session):
    repository = PaymentRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")

    found = await repository.get_for_processing(payment.id)

    assert found is not None
    assert found.id == payment.id


async def test_update_item(db_session):
    repository = PaymentRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")

    await repository.update_item(payment.id, status=PaymentStatus.FAILED)

    assert (await db_session.get(type(payment), payment.id)).status == PaymentStatus.FAILED


async def test_mark_webhook_sent_once(db_session):
    repository = PaymentRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")
    await repository.update_item(payment.id, status=PaymentStatus.SUCCEEDED)

    await repository.mark_webhook_sent(payment.id)
    first = (await db_session.get(type(payment), payment.id)).webhook_sent_at
    db_session.expunge_all()

    await repository.mark_webhook_sent(payment.id)
    second = (await db_session.get(type(payment), payment.id)).webhook_sent_at

    assert first is not None
    assert second == first


async def test_outbox_add_event_and_get_by_payment(db_session):
    repository = PaymentRepository(db_session)
    outbox_repository = OutboxRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")

    await outbox_repository.add_event(payment.id)

    event = await outbox_repository.get_by_payment(payment.id)
    assert event is not None
    assert event.payload == {"payment_id": str(payment.id)}
    assert event.published_at is None


async def test_outbox_add_event_idempotent(db_session):
    repository = PaymentRepository(db_session)
    outbox_repository = OutboxRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")

    await outbox_repository.add_event(payment.id)
    await outbox_repository.add_event(payment.id)

    events = (
        await db_session.execute(select(Outbox).where(Outbox.payment_id == payment.id))
    ).scalars().all()
    assert len(events) == 1


async def test_outbox_get_pending_and_mark_published(db_session):
    repository = PaymentRepository(db_session)
    outbox_repository = OutboxRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")
    await outbox_repository.add_event(payment.id)

    pending = await outbox_repository.get_pending()
    assert [event.payment_id for event in pending] == [payment.id]

    await outbox_repository.mark_published([event.id for event in pending])

    assert await outbox_repository.get_pending() == []
    event = await outbox_repository.get_by_payment(payment.id)
    assert event.published_at is not None


async def test_outbox_get_pending_skips_published(db_session):
    repository = PaymentRepository(db_session)
    outbox_repository = OutboxRepository(db_session)
    payment, _ = await repository.create(payment_data(), "order-123")
    await outbox_repository.add_event(payment.id)
    await outbox_repository.mark_published(
        [event.id for event in await outbox_repository.get_pending()]
    )

    assert await outbox_repository.get_pending() == []
