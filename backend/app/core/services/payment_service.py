import asyncio
import random
from datetime import UTC, datetime
from uuid import UUID

from aiohttp import ClientSession

from app.core.dto.payment import (
    CreatePaymentSchema,
    PaymentAcceptedSchema,
    PaymentSchema,
)
from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.infrastructure.errors.base import NotFoundException
from app.utils.enums import PaymentStatus


class PaymentService:
    def __init__(
        self,
        repository: PaymentRepository,
        outbox_repository: OutboxRepository,
        http_client: ClientSession | None = None,
    ):
        self.repository = repository
        self.outbox_repository = outbox_repository
        self.http_client = http_client

    async def create_payment(
        self, data: CreatePaymentSchema, idempotency_key: str
    ) -> PaymentAcceptedSchema:
        payment, created = await self.repository.create(data, idempotency_key)

        if created or await self.outbox_repository.get_by_payment(payment.id) is None:
            await self.outbox_repository.add_event(payment.id)

        return PaymentAcceptedSchema.model_validate(payment, from_attributes=True)

    async def get_payment(self, payment_id: UUID) -> PaymentSchema:
        payment = await self.repository.get_item(payment_id)
        if payment is None:
            raise NotFoundException("Payment not found")
        return PaymentSchema.model_validate(payment, from_attributes=True)

    async def process_payment(self, payment_id: UUID) -> None:
        payment = await self.repository.get_for_processing(payment_id)
        if payment is None:
            raise NotFoundException("Payment not found")

        if payment.status == PaymentStatus.PENDING:
            await asyncio.sleep(random.uniform(2, 5))

            await self.repository.update_item(
                payment_id,
                status=PaymentStatus.SUCCEEDED if random.randrange(100) < 90 else PaymentStatus.FAILED,
                processed_at=datetime.now(UTC),
            )

            payment = await self.repository.get_for_processing(payment_id)

        if payment.webhook_sent_at is not None:
            return

        payload = PaymentSchema.model_validate(payment, from_attributes=True).model_dump(mode="json")

        async with self.http_client.post(
            payment.webhook_url,
            json=payload,
        ) as response:
            response.raise_for_status()

        await self.repository.mark_webhook_sent(payment_id)
