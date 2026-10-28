from unittest.mock import AsyncMock, MagicMock

from app.core.dto.payment import CreatePaymentSchema

TEST_API_KEY = "test-api-key"


def auth_headers(idempotency_key: str = "order-123") -> dict[str, str]:
    return {"X-API-Key": TEST_API_KEY, "Idempotency-Key": idempotency_key}


def api_key_headers(api_key: str = TEST_API_KEY) -> dict[str, str]:
    return {"X-API-Key": api_key}


def payment_data(**overrides) -> CreatePaymentSchema:
    return CreatePaymentSchema(**payment_payload(**overrides))


def payment_payload(**overrides) -> dict:
    payload = {
        "amount": "1500.50",
        "currency": "RUB",
        "description": "Заказ 123",
        "metadata": {"order_id": 123},
        "webhook_url": "https://example.com/webhook",
    }
    payload.update(overrides)
    return payload


def fake_http_client(fail: bool = False) -> MagicMock:
    response = MagicMock()
    if fail:
        response.raise_for_status = MagicMock(
            side_effect=RuntimeError("webhook receiver returned 5xx")
        )
    client = MagicMock()
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=response)
    context.__aexit__ = AsyncMock(return_value=False)
    client.post = MagicMock(return_value=context)
    return client


def fake_broker() -> MagicMock:
    broker = MagicMock()
    broker.publish = AsyncMock()
    broker.PAYMENTS_QUEUE = "payments.new"
    return broker


def fake_message(payment_id) -> MagicMock:
    message = MagicMock()
    message.decode = AsyncMock(return_value={"payment_id": str(payment_id)})
    message.ack = AsyncMock()
    message.reject = AsyncMock()
    return message
