from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.base_repository import SqlAlchemyRepository
from app.infrastructure.database.models.outbox import Outbox


class OutboxRepository(SqlAlchemyRepository[Outbox]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Outbox)

    async def add_event(self, payment_id: UUID) -> None:
        query = (
            insert(Outbox)
            .values(payment_id=payment_id, payload={"payment_id": str(payment_id)})
            .on_conflict_do_nothing(index_elements=["payment_id"])
        )
        try:
            await self.session.execute(query)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def get_by_payment(self, payment_id: UUID) -> Outbox | None:
        query = select(Outbox).where(Outbox.payment_id == payment_id)
        result = await self.session.execute(query)
        return result.scalars().one_or_none()

    async def get_pending(self) -> list[Outbox]:
        query = (
            select(Outbox)
            .where(Outbox.published_at.is_(None))
            .order_by(Outbox.created_at)
            .with_for_update(skip_locked=True)
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def mark_published(self, event_ids: list[UUID]) -> None:
        query = (
            update(Outbox)
            .where(Outbox.id.in_(event_ids))
            .values(published_at=datetime.now(UTC))
        )
        await self.session.execute(query)
        await self.session.commit()
