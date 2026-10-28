from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.infrastructure.config.config import DB_CONFIG


class DatabaseConnection:
    def __init__(self):
        self._engine = create_async_engine(DB_CONFIG.get_url())

    async def get_session(self) -> AsyncSession:
        return AsyncSession(self._engine, expire_on_commit=False)

    async def close(self) -> None:
        await self._engine.dispose()
