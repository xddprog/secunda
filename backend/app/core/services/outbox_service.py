from app.core.repositories.outbox_repository import OutboxRepository
from app.infrastructure.broker.rabbit_broker import PaymentBroker


class OutboxService:
    def __init__(self, repository: OutboxRepository, broker: PaymentBroker):
        self.repository = repository
        self.broker = broker

    async def publish_pending(self) -> None:
        events = await self.repository.get_pending()
        for event in events:
            try:
                await self.broker.publish(
                    event.payload,
                    queue=self.broker.PAYMENTS_QUEUE,
                    persist=True,
                    mandatory=True,
                    timeout=10,
                )
            except Exception as error:
                error.add_note(
                    f"Outbox event_id={event.id}, "
                    f"payment_id={event.payload.get('payment_id')}"
                )
                raise
        await self.repository.mark_published([event.id for event in events])
