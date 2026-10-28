from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dto.payment import CreatePaymentSchema
from app.core.repositories.base_repository import SqlAlchemyRepository
from app.infrastructure.database.models.payment import Payment


class PaymentRepository(SqlAlchemyRepository[Payment]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Payment)

    async def create(
        self, data: CreatePaymentSchema, idempotency_key: str
    ) -> tuple[Payment, bool]:
        query = (
            insert(Payment)
            .values(
                **data.model_dump(exclude={"metadata"}),
                payment_metadata=data.metadata,
                idempotency_key=idempotency_key,
            )
            .on_conflict_do_nothing(index_elements=[Payment.idempotency_key])
            .returning(Payment)
        )

        result = await self.session.execute(query)
        payment = result.scalar_one_or_none()

        if payment is None:
            result = await self.session.execute(
                select(Payment).where(Payment.idempotency_key == idempotency_key)
            )
            return result.scalar_one(), False

        return payment, True

    async def get_for_processing(self, payment_id: UUID) -> Payment | None:
        try:
            query = (
                select(Payment)
                .where(Payment.id == payment_id)
                .with_for_update()
            )
            result = await self.session.execute(query)
            return result.scalar_one_or_none()
        except Exception:
            await self.session.rollback()
            raise

    async def mark_webhook_sent(self, payment_id: UUID) -> None:
        query = (
            update(Payment)
            .where(Payment.id == payment_id, Payment.webhook_sent_at.is_(None))
            .values(webhook_sent_at=datetime.now(UTC))
        )
        try:
            await self.session.execute(query)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
