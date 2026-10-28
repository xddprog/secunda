from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.routers import api_v1_router
from app.infrastructure.database.adapters.pg_connection import DatabaseConnection


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_connection = DatabaseConnection()
    yield
    await app.state.db_connection.close()


app = FastAPI(lifespan=lifespan)
app.include_router(api_v1_router)
