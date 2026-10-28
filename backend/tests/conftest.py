import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.config.config import DB_CONFIG
from app.infrastructure.database.adapters.pg_connection import DatabaseConnection
from app.infrastructure.database.models import Base
from app.main import app

TEST_DB_NAME = "payments_test"


@pytest.fixture(scope="session", autouse=True)
def database() -> AsyncGenerator[None, None]:
    DB_CONFIG.DB_NAME = TEST_DB_NAME
    engine = create_async_engine(DB_CONFIG.get_url(), poolclass=NullPool)

    async def create_tables() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def dispose() -> None:
        await engine.dispose()

    asyncio.run(create_tables())
    yield
    asyncio.run(dispose())


@pytest_asyncio.fixture(autouse=True)
async def clean_tables(database) -> AsyncGenerator[None, None]:
    engine = create_async_engine(DB_CONFIG.get_url(), poolclass=NullPool)
    async with engine.begin() as conn:
        for table in ("payments", "outbox"):
            await conn.execute(text(f"TRUNCATE TABLE {table} CASCADE"))
    await engine.dispose()


@pytest_asyncio.fixture
async def db_connection(clean_tables) -> AsyncGenerator[DatabaseConnection, None]:
    connection = DatabaseConnection()
    yield connection
    await connection.close()


@pytest_asyncio.fixture
async def db_session(db_connection) -> AsyncGenerator:
    async with await db_connection.get_session() as session:
        yield session


@pytest_asyncio.fixture
async def api_client(db_connection) -> AsyncGenerator[AsyncClient, None]:
    app.state.db_connection = db_connection
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        yield client
