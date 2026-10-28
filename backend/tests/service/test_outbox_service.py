from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.core.services.outbox_service import OutboxService
from app.infrastructure.database.models.outbox import Outbox
from tests.helpers import fake_broker, payment_data

pytestmark = pytest.mark.asyncio


async def test_publish_pending(db_session):
    payment, _ = await PaymentRepository(db_session).create(payment_data(), "order-123")
    outbox_repository = OutboxRepository(db_session)
    await outbox_repository.add_event(payment.id)
    broker = fake_broker()
    service = OutboxService(repository=outbox_repository, broker=broker)

    await service.publish_pending()

    broker.publish.assert_awaited_once()
    event = (
        await db_session.execute(
            select(Outbox).where(Outbox.payment_id == payment.id)
        )
    ).scalar_one()
    assert event.published_at is not None


async def test_publish_pending_without_events(db_session):
    broker = fake_broker()
    service = OutboxService(repository=OutboxRepository(db_session), broker=broker)

    await service.publish_pending()

    broker.publish.assert_not_awaited()


async def test_publish_pending_broker_failure(db_session):
    payment, _ = await PaymentRepository(db_session).create(payment_data(), "order-123")
    outbox_repository = OutboxRepository(db_session)
    await outbox_repository.add_event(payment.id)
    broker = fake_broker()
    broker.publish = AsyncMock(side_effect=RuntimeError("broker unavailable"))
    service = OutboxService(repository=outbox_repository, broker=broker)

    with pytest.raises(RuntimeError, match="broker unavailable"):
        await service.publish_pending()

    event = (
        await db_session.execute(
            select(Outbox).where(Outbox.payment_id == payment.id)
        )
    ).scalar_one()
    assert event.published_at is None
