from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.repositories.base_repository import SqlAlchemyRepository
from app.infrastructure.database.models.payment import Payment
from tests.helpers import payment_data

pytestmark = pytest.mark.asyncio


def make_session(execute_result: MagicMock | None = None) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(return_value=execute_result)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


def make_execute_result(items: list) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    result.scalars.return_value.one_or_none.return_value = (
        items[0] if items else None
    )
    return result


@pytest.fixture
def repository() -> SqlAlchemyRepository[Payment]:
    return SqlAlchemyRepository(make_session(), Payment)


async def test_get_item(repository):
    repository.session.get = AsyncMock(return_value="payment")

    assert await repository.get_item("id") == "payment"
    repository.session.get.assert_awaited_once_with(Payment, "id")


async def test_update_item(repository):
    await repository.update_item("id", status="succeeded")

    repository.session.execute.assert_awaited_once()
    repository.session.commit.assert_awaited_once()


async def test_update_item_rolls_back_on_error(repository):
    repository.session.execute = AsyncMock(side_effect=RuntimeError("db down"))

    with pytest.raises(RuntimeError, match="db down"):
        await repository.update_item("id", status="succeeded")

    repository.session.rollback.assert_awaited_once()


async def test_add_item(repository):
    item = await repository.add_item(description="Заказ 123")

    assert isinstance(item, Payment)
    assert item.description == "Заказ 123"
    repository.session.add.assert_called_once()
    repository.session.commit.assert_awaited_once()
    repository.session.refresh.assert_awaited_once()


async def test_delete_item(repository):
    item = Payment(**payment_data().model_dump(exclude={"metadata"}))

    await repository.delete_item(item)

    repository.session.delete.assert_awaited_once_with(item)
    repository.session.commit.assert_awaited_once()


async def test_get_by_filter_all(repository):
    repository.session.execute = AsyncMock(return_value=make_execute_result(["a", "b"]))

    items = await repository.get_by_filter(status="pending")

    assert items == ["a", "b"]


async def test_get_by_filter_one_or_none(repository):
    execute_result = make_execute_result(["a"])
    repository.session.execute = AsyncMock(return_value=execute_result)

    item = await repository.get_by_filter(one_or_none=True, status="pending")

    assert item == "a"
