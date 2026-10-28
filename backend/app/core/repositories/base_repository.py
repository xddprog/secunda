from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.interfaces.repository import RepositoryInterface


class SqlAlchemyRepository[ModelType](RepositoryInterface[ModelType]):
    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

    async def get_item(self, item_id: UUID) -> ModelType | None:
        return await self.session.get(self.model, item_id)

    async def update_item(self, item_id: UUID, **update_values: Any) -> None:
        try:
            query = (
                update(self.model)
                .where(self.model.id == item_id)
                .values(**update_values)
            )
            await self.session.execute(query)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def get_by_filter(
        self, 
        *, 
        one_or_none: bool = False, 
        **filter_by: Any
    ) -> list[ModelType] | ModelType | None:
        query = select(self.model)
        
        for key, value in filter_by.items():
            query = query.where(getattr(self.model, key) == value)

        items = await self.session.execute(query)
        
        if one_or_none:
            return items.scalars().one_or_none()
        return items.scalars().all()

    async def add_item(self, **kwargs: Any) -> ModelType:
        item = self.model(**kwargs)
        self.session.add(item)
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def delete_item(self, item: ModelType) -> None:
        await self.session.delete(item)
        await self.session.commit()
