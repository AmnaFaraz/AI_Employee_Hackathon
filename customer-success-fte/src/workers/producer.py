"""
Kafka Producer — Customer Success Digital FTE

Publishes normalised message events from channel intake handlers
to the 'customer-messages' Kafka topic.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaProducer

from src.workers.schemas import KafkaIncomingMessage

logger = logging.getLogger(__name__)


def _make_kafka_url() -> str:
    return os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


TOPICS = {
    "incoming": os.environ.get("KAFKA_TOPIC_INCOMING", "customer-messages"),
    "responses": os.environ.get("KAFKA_TOPIC_RESPONSES", "agent-responses"),
    "errors": os.environ.get("KAFKA_TOPIC_ERRORS", "agent-errors"),
}


class MessageProducer:
    """Async Kafka producer for intake messages."""

    def __init__(self):
        self._producer: AIOKafkaProducer | None = None

    async def start(self) -> None:
        self._producer = AIOKafkaProducer(
            bootstrap_servers=_make_kafka_url(),
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            compression_type="gzip",
            acks="all",                  # wait for all replicas
            max_batch_size=32768,
            linger_ms=5,                 # slight batching for throughput
        )
        await self._producer.start()
        logger.info("Kafka producer started → %s", _make_kafka_url())

    async def stop(self) -> None:
        if self._producer:
            await self._producer.stop()
            logger.info("Kafka producer stopped")

    async def publish_incoming_message(
        self,
        channel: str,
        sender_id: str,
        content: str,
        sender_name: str = "",
        channel_thread_id: str = "",
        channel_message_id: str = "",
        channel_context: dict[str, Any] | None = None,
    ) -> str:
        """
        Publish a normalised incoming message to 'customer-messages'.
        Returns the generated event_id.
        """
        event_id = str(uuid.uuid4())
        event = KafkaIncomingMessage(
            event_id=event_id,
            channel=channel,
            sender_id=sender_id,
            sender_name=sender_name,
            content=content,
            channel_thread_id=channel_thread_id,
            channel_message_id=channel_message_id,
            channel_context=channel_context or {},
            received_at=datetime.now(timezone.utc),
        )

        await self._producer.send_and_wait(
            topic=TOPICS["incoming"],
            key=sender_id,              # partition by sender for ordering
            value=event.model_dump(),
        )

        logger.info(
            "Published incoming | event_id=%s | channel=%s | sender=%s",
            event_id, channel, sender_id,
        )
        return event_id

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, *_):
        await self.stop()


# Module-level singleton
_producer: MessageProducer | None = None


async def get_producer() -> MessageProducer:
    global _producer
    if _producer is None:
        _producer = MessageProducer()
        await _producer.start()
    return _producer


async def close_producer() -> None:
    global _producer
    if _producer:
        await _producer.stop()
        _producer = None
