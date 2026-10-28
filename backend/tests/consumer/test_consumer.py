import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from faststream import ContextRepo
from sqlalchemy import select

import app.consumer as consumer_module
from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.core.services import payment_service as payment_service_module
from app.infrastructure.database.models.outbox import Outbox
from app.infrastructure.database.models.payment import Payment
from app.utils.enums import PaymentStatus
from tests.helpers import fake_broker, fake_http_client, fake_message, payment_data
from tests.service.test_payment_service import FastProcessing

pytestmark = pytest.mark.asyncio


class CancelOnSleep:
    @staticmethod
    async def sleep(delay: float) -> None:
        raise asyncio.CancelledError


@pytest.fixture
def fast_consumer(monkeypatch) -> type[FastProcessing]:
    stub = FastProcessing
    monkeypatch.setattr(payment_service_module, "asyncio", stub)
    monkeypatch.setattr(payment_service_module, "random", stub)
    monkeypatch.setattr(consumer_module.asyncio, "sleep", stub.sleep)
    return stub


async def create_payment(session) -> Payment:
    payment, _ = await PaymentRepository(session).create(payment_data(), "order-123")
    await OutboxRepository(session).add_event(payment.id)
    return payment


async def test_process_payment_message_acks(db_connection, db_session, fast_consumer):
    payment = await create_payment(db_session)
    message = fake_message(payment.id)

    await consumer_module.process_payment(message, db_connection, fake_http_client())

    message.ack.assert_awaited_once()
    message.reject.assert_not_awaited()
    db_session.expunge_all()
    stored = await db_session.get(Payment, payment.id)
    assert stored.status == PaymentStatus.SUCCEEDED
    assert stored.webhook_sent_at is not None


async def test_process_payment_message_rejects_after_retries(
    db_connection, db_session, fast_consumer
):
    payment = await create_payment(db_session)
    message = fake_message(payment.id)

    await consumer_module.process_payment(
        message, db_connection, fake_http_client(fail=True)
    )

    message.reject.assert_awaited_once_with(requeue=False)
    message.ack.assert_not_awaited()


async def test_process_payment_message_recover_on_retry(
    db_connection, db_session, fast_consumer
):
    payment = await create_payment(db_session)
    message = fake_message(payment.id)
    http_client = fake_http_client()
    http_client.post = MagicMock(side_effect=[RuntimeError("boom"), http_client.post()])

    await consumer_module.process_payment(message, db_connection, http_client)

    message.ack.assert_awaited_once()
    db_session.expunge_all()
    stored = await db_session.get(Payment, payment.id)
    assert stored.webhook_sent_at is not None


async def test_publish_outbox(db_connection, db_session, monkeypatch):
    payment = await create_payment(db_session)
    broker = fake_broker()
    monkeypatch.setattr(consumer_module, "broker", broker)
    monkeypatch.setattr(consumer_module.asyncio, "sleep", CancelOnSleep.sleep)

    with pytest.raises(asyncio.CancelledError):
        await consumer_module.publish_outbox(db_connection)

    broker.publish.assert_awaited_once_with(
        {"payment_id": str(payment.id)},
        queue="payments.new",
        persist=True,
        mandatory=True,
        timeout=10,
    )
    event = (
        await db_session.execute(
            select(Outbox).where(Outbox.payment_id == payment.id)
        )
    ).scalar_one()
    assert event.published_at is not None


async def test_publish_outbox_survives_broker_failure(
    db_connection, db_session, monkeypatch
):
    await create_payment(db_session)
    broker = fake_broker()
    broker.publish = AsyncMock(side_effect=RuntimeError("broker down"))
    monkeypatch.setattr(consumer_module, "broker", broker)
    monkeypatch.setattr(consumer_module.asyncio, "sleep", CancelOnSleep.sleep)

    with pytest.raises(asyncio.CancelledError):
        await consumer_module.publish_outbox(db_connection)

    broker.publish.assert_awaited_once()


async def test_lifecycle_hooks(monkeypatch):
    context = ContextRepo()
    broker = fake_broker()
    broker.declare_queues = AsyncMock()
    db_connection = AsyncMock()
    http_client = AsyncMock()
    monkeypatch.setattr(consumer_module, "broker", broker)
    monkeypatch.setattr(consumer_module, "DatabaseConnection", lambda: db_connection)
    monkeypatch.setattr(consumer_module, "ClientSession", lambda **kwargs: http_client)
    monkeypatch.setattr(
        consumer_module.asyncio, "create_task", lambda coro: "task-sentinel"
    )

    await consumer_module.start_app(context)

    broker.declare_queues.assert_awaited_once()
    assert context.get("db_connection") is db_connection
    assert context.get("http_client") is http_client
    assert context.get("publisher_task") == "task-sentinel"

    task = asyncio.get_running_loop().create_task(asyncio.sleep(10))
    context.set_global("publisher_task", task)
    await consumer_module.stop_publisher(context)
    assert task.cancelled()

    context.set_global("http_client", http_client)
    context.set_global("db_connection", db_connection)
    await consumer_module.close_resources(context)
    http_client.close.assert_awaited_once()
    db_connection.close.assert_awaited_once()
