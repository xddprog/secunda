from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.repositories.outbox_repository import OutboxRepository
from app.core.repositories.payment_repository import PaymentRepository
from app.core.services.payment_service import PaymentService
from app.infrastructure.config.config import APP_CONFIG


async def require_api_key(
    api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> None:
    if api_key != APP_CONFIG.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with await request.app.state.db_connection.get_session() as session:
        yield session


def get_payment_service(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentService:
    return PaymentService(
        repository=PaymentRepository(session),
        outbox_repository=OutboxRepository(session),
    )
