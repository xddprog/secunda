from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database.models.base import Base
from app.utils.enums import Currency, PaymentStatus


class Payment(Base):
    __tablename__ = "payments"

    amount: Mapped[Decimal]
    currency: Mapped[Currency]
    status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(
            PaymentStatus,
            name="payment_status",
            values_callable=lambda items: [item.value for item in items],
        ),
        server_default=PaymentStatus.PENDING.value,
    )
    description: Mapped[str]
    payment_metadata: Mapped[dict] = mapped_column("metadata", JSONB)
    idempotency_key: Mapped[str] = mapped_column(unique=True)
    webhook_url: Mapped[str]
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    webhook_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
