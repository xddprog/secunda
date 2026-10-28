from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID


class RepositoryInterface[ModelType](ABC):
    @abstractmethod
    async def get_item(self, item_id: UUID) -> ModelType | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_filter(
        self,
        *,
        one_or_none: bool = False,
        **filter_by: Any,
    ) -> list[ModelType] | ModelType | None:
        raise NotImplementedError

    @abstractmethod
    async def add_item(self, **kwargs: Any) -> ModelType:
        raise NotImplementedError

    @abstractmethod
    async def delete_item(self, item: ModelType) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update_item(self, item_id: UUID, **update_values: Any) -> None:
        raise NotImplementedError
