"""
Kafka Consumer Worker — Customer Success Digital FTE

Reads from 'customer-messages', runs the AI agent,
and publishes results to 'agent-responses'.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer

from src.agent.agent import CustomerSuccessAgent, IncomingMessage
from src.database.connection import init_db, close_db, get_session
from src.database.models import ChannelType
from src.workers.schemas import KafkaIncomingMessage, KafkaAgentResponse, KafkaErrorEvent
from src.workers.producer import TOPICS

logger = logging.getLogger(__name__)

CONSUMER_GROUP = os.environ.get("KAFKA_CONSUMER_GROUP", "agent-workers")
BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Maximum concurrent tasks per worker instance
MAX_CONCURRENT = int(os.environ.get("WORKER_MAX_CONCURRENT", "5"))


class AgentWorker:
    """Kafka consumer that runs the AI agent on each incoming message."""

    def __init__(self):
        self._consumer: AIOKafkaConsumer | None = None
        self._producer: AIOKafkaProducer | None = None
        self._agent = CustomerSuccessAgent()
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        self._running = False

    async def start(self) -> None:
        self._consumer = AIOKafkaConsumer(
            TOPICS["incoming"],
            bootstrap_servers=BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP,
            auto_offset_reset="earliest",
            enable_auto_commit=False,       # Manual commit for at-least-once
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            max_poll_records=10,
            session_timeout_ms=30000,
            heartbeat_interval_ms=10000,
        )

        self._producer = AIOKafkaProducer(
            bootstrap_servers=BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
        )

        await self._consumer.start()
        await self._producer.start()
        self._running = True
        logger.info("Worker started | group=%s | topic=%s", CONSUMER_GROUP, TOPICS["incoming"])

    async def stop(self) -> None:
        self._running = False
        if self._consumer:
            await self._consumer.stop()
        if self._producer:
            await self._producer.stop()
        await close_db()
        logger.info("Worker stopped")

    async def _handle_message(self, raw: dict) -> None:
        """Process a single Kafka message through the agent pipeline."""
        async with self._semaphore:
            try:
                event = KafkaIncomingMessage(**raw)
                channel = ChannelType(event.channel)

                incoming = IncomingMessage(
                    channel=channel,
                    content=event.content,
                    sender_id=event.sender_id,
                    sender_name=event.sender_name,
                    channel_thread_id=event.channel_thread_id,
                    channel_message_id=event.channel_message_id,
                    channel_context=event.channel_context,
                )

                async with get_session() as session:
                    response = await self._agent.process(incoming, session)

                # Publish response event
                response_event = KafkaAgentResponse(
                    event_id=str(uuid.uuid4()),
                    original_event_id=event.event_id,
                    channel=event.channel,
                    sender_id=event.sender_id,
                    response_content=response.content,
                    ticket_id=str(response.ticket_id) if response.ticket_id else None,
                    ticket_number=response.ticket_number,
                    was_escalated=response.was_escalated,
                    escalation_reason=response.escalation_reason,
                    processing_ms=response.processing_ms,
                )

                await self._producer.send_and_wait(
                    topic=TOPICS["responses"],
                    key=event.sender_id,
                    value=response_event.model_dump(),
                )

                logger.info(
                    "Message processed | event=%s | ms=%d | escalated=%s",
                    event.event_id,
                    response.processing_ms,
                    response.was_escalated,
                )

            except Exception as exc:
                logger.error("Error processing message: %s", exc, exc_info=True)
                # Publish error event
                try:
                    error_event = KafkaErrorEvent(
                        event_id=str(uuid.uuid4()),
                        original_event_id=raw.get("event_id", "unknown"),
                        channel=raw.get("channel", "UNKNOWN"),
                        error_type=type(exc).__name__,
                        error_message=str(exc)[:500],
                    )
                    await self._producer.send_and_wait(
                        topic=TOPICS["errors"],
                        value=error_event.model_dump(),
                    )
                except Exception as pub_exc:
                    logger.error("Failed to publish error event: %s", pub_exc)

    async def run(self) -> None:
        """Main consumer loop — processes messages until stopped."""
        tasks: set[asyncio.Task] = set()

        try:
            async for msg in self._consumer:
                if not self._running:
                    break

                task = asyncio.create_task(self._handle_message(msg.value))
                tasks.add(task)

                # Commit offset after spawning task
                await self._consumer.commit()

                # Clean up completed tasks
                tasks = {t for t in tasks if not t.done()}

        finally:
            # Wait for all in-flight tasks to complete
            if tasks:
                logger.info("Waiting for %d in-flight tasks to complete...", len(tasks))
                await asyncio.gather(*tasks, return_exceptions=True)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
    )

    # Initialise database
    init_db()

    worker = AgentWorker()
    await worker.start()

    # Graceful shutdown on SIGTERM/SIGINT
    loop = asyncio.get_running_loop()

    def _shutdown():
        logger.info("Shutdown signal received")
        asyncio.create_task(worker.stop())

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _shutdown)

    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
