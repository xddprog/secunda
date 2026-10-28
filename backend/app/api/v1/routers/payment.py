from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status

from app.api.dependencies import get_payment_service
from app.core.dto.payment import (
    CreatePaymentSchema,
    PaymentAcceptedSchema,
    PaymentSchema,
)
from app.core.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_payment(
    data: CreatePaymentSchema,
    service: Annotated[PaymentService, Depends(get_payment_service)],
    idempotency_key: Annotated[str, Header()],
) -> PaymentAcceptedSchema:
    return await service.create_payment(data, idempotency_key)


@router.get("/{payment_id}")
async def get_payment(
    payment_id: UUID,
    service: Annotated[PaymentService, Depends(get_payment_service)],
) -> PaymentSchema:
    return await service.get_payment(payment_id)
