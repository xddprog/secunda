import asyncio
import logging
from contextlib import suppress
from typing import Annotated
from uuid import UUID

from aiohttp import ClientSession, ClientTimeout
from faststream import AckPolicy, Context, ContextRepo, FastStream
from faststream.rabbit import RabbitRouter
from faststream.rabbit.annotations import RabbitMessage

from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.core.services.outbox_service import OutboxService
from app.core.services.payment_service import PaymentService
from app.infrastructure.broker.rabbit_broker import PaymentBroker
from app.infrastructure.database.adapters.pg_connection import DatabaseConnection

logger = logging.getLogger(__name__)
router = RabbitRouter()
broker = PaymentBroker()
app = FastStream(broker)


@router.subscriber(PaymentBroker.PAYMENTS_QUEUE, ack_policy=AckPolicy.MANUAL)
async def process_payment(
    message: RabbitMessage,
    db_connection: Annotated[DatabaseConnection, Context(cast=True)],
    http_client: Annotated[ClientSession, Context(cast=True)],
) -> None:
    payment_id: UUID | None = None
    for attempt in range(3):
        try:
            payload = await message.decode()
            payment_id = UUID(payload["payment_id"])

            async with await db_connection.get_session() as session:
                service = PaymentService(
                    repository=PaymentRepository(session),
                    outbox_repository=OutboxRepository(session),
                    http_client=http_client,
                )
                await service.process_payment(payment_id)

        except Exception:
            logger.exception(
                f"Payment processing failed: payment_id={payment_id}, "
                f"message_id={message.message_id}, attempt={attempt + 1}/3"
            )
            if attempt < 2:
                await asyncio.sleep(2**attempt)
        else:
            await message.ack()
            return

    await message.reject(requeue=False)
    logger.error(
        f"Payment message rejected after 3 attempts: payment_id={payment_id}, "
        f"message_id={message.message_id}, requeue=False"
    )


async def publish_outbox(db_connection: DatabaseConnection) -> None:
    while True:
        try:
            async with await db_connection.get_session() as session:
                service = OutboxService(
                    repository=OutboxRepository(session), broker=broker
                )
                await service.publish_pending()
        except Exception:
            logger.exception("Outbox publication failed")
        await asyncio.sleep(1)


@app.after_startup
async def start_app(context: ContextRepo) -> None:
    db_connection = DatabaseConnection()
    http_client = ClientSession(timeout=ClientTimeout(total=10))
    context.set_global("db_connection", db_connection)
    context.set_global("http_client", http_client)
    await broker.declare_queues()
    context.set_global(
        "publisher_task", asyncio.create_task(publish_outbox(db_connection))
    )


@app.on_shutdown
async def stop_publisher(context: ContextRepo) -> None:
    task = context.get("publisher_task")
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task


@app.after_shutdown
async def close_resources(context: ContextRepo) -> None:
    await context.get("http_client").close()
    await context.get("db_connection").close()


broker.include_router(router)
