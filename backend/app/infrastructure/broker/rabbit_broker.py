from faststream.rabbit import Channel, RabbitBroker, RabbitQueue

from app.infrastructure.config.config import RABBITMQ_CONFIG


class PaymentBroker(RabbitBroker):
    DLQ_QUEUE = RabbitQueue("payments.dlq", durable=True)
    PAYMENTS_QUEUE = RabbitQueue(
        "payments.new",
        durable=True,
        arguments={
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": DLQ_QUEUE.name,
        },
    )

    def __init__(self):
        super().__init__(
            RABBITMQ_CONFIG.URL,
            default_channel=Channel(
                prefetch_count=1,
                on_return_raises=True,
            ),
        )

    async def declare_queues(self) -> None:
        await self.declare_queue(self.DLQ_QUEUE)
        await self.declare_queue(self.PAYMENTS_QUEUE)
