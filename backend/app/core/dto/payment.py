from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_serializer

from app.utils.enums import Currency, PaymentStatus


class CreatePaymentSchema(BaseModel):
    amount: Decimal
    currency: Currency
    description: str
    metadata: dict = Field(default_factory=dict)
    webhook_url: HttpUrl

    @field_serializer("webhook_url")
    def serialize_webhook_url(self, value: HttpUrl) -> str:
        return str(value)


class PaymentAcceptedSchema(BaseModel):
    payment_id: UUID = Field(validation_alias="id")
    status: PaymentStatus
    created_at: datetime


class PaymentSchema(BaseModel):
    payment_id: UUID = Field(validation_alias="id")
    amount: Decimal
    currency: Currency
    status: PaymentStatus
    description: str
    metadata: dict = Field(validation_alias="payment_metadata")
    webhook_url: str
    created_at: datetime
    processed_at: datetime | None
