import pytest
from sqlalchemy import func, select
from starlette import status

from app.infrastructure.database.models.outbox import Outbox
from app.infrastructure.database.models.payment import Payment
from tests.helpers import api_key_headers, auth_headers, payment_payload

pytestmark = pytest.mark.asyncio


async def test_create_payment(api_client, db_session):
    response = await api_client.post(
        "/api/v1/payments", json=payment_payload(), headers=auth_headers()
    )

    assert response.status_code == status.HTTP_202_ACCEPTED
    body = response.json()
    assert body["status"] == "pending"

    payment = await db_session.get(Payment, body["payment_id"])
    assert payment is not None
    assert payment.idempotency_key == "order-123"

    events_count = await db_session.scalar(
        select(func.count()).select_from(Outbox).where(
            Outbox.payment_id == payment.id
        )
    )
    assert events_count == 1


async def test_create_payment_replay(api_client, db_session):
    headers = auth_headers("order-123")

    first = await api_client.post(
        "/api/v1/payments", json=payment_payload(), headers=headers
    )
    second = await api_client.post(
        "/api/v1/payments", json=payment_payload(), headers=headers
    )

    assert second.status_code == status.HTTP_202_ACCEPTED
    assert second.json()["payment_id"] == first.json()["payment_id"]

    events_count = await db_session.scalar(select(func.count()).select_from(Outbox))
    assert events_count == 1


async def test_create_payment_without_idempotency_key(api_client):
    response = await api_client.post(
        "/api/v1/payments", json=payment_payload(), headers=api_key_headers()
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_create_payment_invalid_payload(api_client):
    response = await api_client.post(
        "/api/v1/payments",
        json=payment_payload(amount="not-a-number", currency="GBP"),
        headers=auth_headers(),
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


@pytest.mark.parametrize("headers", [{}, api_key_headers("wrong-key")])
async def test_create_payment_unauthorized(api_client, headers):
    response = await api_client.post(
        "/api/v1/payments", json=payment_payload(), headers=headers
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED


async def test_get_payment(api_client):
    created = await api_client.post(
        "/api/v1/payments", json=payment_payload(), headers=auth_headers()
    )
    payment_id = created.json()["payment_id"]

    response = await api_client.get(
        f"/api/v1/payments/{payment_id}", headers=api_key_headers()
    )

    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["payment_id"] == payment_id
    assert body["metadata"] == {"order_id": 123}
    assert body["processed_at"] is None


async def test_get_payment_not_found(api_client):
    response = await api_client.get(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000",
        headers=api_key_headers(),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


async def test_get_payment_invalid_uuid(api_client):
    response = await api_client.get(
        "/api/v1/payments/not-a-uuid", headers=api_key_headers()
    )

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY


async def test_get_payment_unauthorized(api_client):
    response = await api_client.get(
        "/api/v1/payments/00000000-0000-0000-0000-000000000000"
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
