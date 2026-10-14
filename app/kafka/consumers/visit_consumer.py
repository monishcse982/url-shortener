import asyncio
import json
import logging
import signal
from datetime import UTC, datetime

from confluent_kafka import Consumer, KafkaException, Message

from app.core.metrics import (
    kafka_message_processing_duration_seconds,
    kafka_message_processing_error,
    kafka_messages_committed,
    kafka_messages_dlq,
    kafka_messages_processed,
    kafka_messages_received,
)
from app.db.repositories.visits import VisitsRepository
from app.db.session import close_db, init_db
from app.kafka.config import kafka_consumer_config
from app.kafka.events import DeadLetterEvent, LinkVisitedEvent, event_to_bytes
from app.kafka.producer import kafka_producer
from app.kafka.topics import LINK_VISITED_DLQ_TOPIC, LINK_VISITED_TOPIC

running = True
logger = logging.getLogger(__name__)


def stop_consumer(*_: object) -> None:
    global running
    running = False
    logger.info("Visit consumer shutdown requested")


async def process_visit_event(event: LinkVisitedEvent) -> None:
    logger.info(
        "Processing visit event event_id=%s link_id=%s short_code=%s",
        event.event_id,
        event.link_id,
        event.short_code,
    )

    visits_repository = VisitsRepository()
    await visits_repository.create(
        link_id=event.link_id,
        user_agent=event.user_agent,
        referrer=event.referrer,
        ip_address=event.ip_address,
    )

    logger.info(
        "Visit event processed event_id=%s link_id=%s short_code=%s",
        event.event_id,
        event.link_id,
        event.short_code,
    )


async def consume_visits() -> None:
    consumer = Consumer(kafka_consumer_config())
    consumer.subscribe([LINK_VISITED_TOPIC])

    logger.info("Visit consumer started topic=%s", LINK_VISITED_TOPIC)

    try:
        while running:
            message = await asyncio.to_thread(consumer.poll, 1.0)

            if message is None:
                continue

            if message.error():
                logger.error("Kafka consumer error error=%s", message.error())
                raise KafkaException(message.error())

            await _handle_message(consumer, message)
    finally:
        consumer.close()
        logger.info("Visit consumer stopped")


async def _handle_message(consumer: Consumer, message: Message) -> None:
    topic = message.topic() or LINK_VISITED_TOPIC
    partition = message.partition()
    offset = message.offset()
    key = _decode_key(message)

    kafka_messages_received.labels(topic=topic).inc()
    logger.debug(
        "Kafka message received topic=%s partition=%s offset=%s key=%s",
        topic,
        partition,
        offset,
        key,
    )

    value = message.value()

    if value is None:
        logger.warning(
            "Kafka message ignored: empty value topic=%s partition=%s offset=%s key=%s",
            topic,
            partition,
            offset,
            key,
        )
        await _commit_message(consumer, message)
        return

    try:
        payload = json.loads(value.decode("utf-8"))
        event = LinkVisitedEvent.model_validate(payload)
    except Exception as error:
        kafka_message_processing_error.labels(
            topic=topic,
            error_type=type(error).__name__,
        ).inc()
        logger.exception(
            "Kafka message ignored: invalid payload topic=%s partition=%s "
            "offset=%s key=%s",
            topic,
            partition,
            offset,
            key,
        )
        await _publish_to_dlq(
            topic=topic,
            partition=partition,
            offset=offset,
            key=key,
            value=value,
            error=error,
        )
        await _commit_message(consumer, message)
        return

    try:
        with kafka_message_processing_duration_seconds.labels(topic=topic).time():
            await process_visit_event(event)
    except Exception as error:
        kafka_message_processing_error.labels(
            topic=topic,
            error_type=type(error).__name__,
        ).inc()
        logger.exception(
            "Kafka message processing failed topic=%s partition=%s offset=%s key=%s"
            " event_id=%s link_id=%s short_code=%s",
            topic,
            partition,
            offset,
            key,
            event.event_id,
            event.link_id,
            event.short_code,
        )
        return

    kafka_messages_processed.labels(topic=topic).inc()
    await _commit_message(consumer, message)


async def _publish_to_dlq(
    *,
    topic: str,
    partition: int | None,
    offset: int | None,
    key: str | None,
    value: bytes,
    error: Exception,
) -> None:
    dlq_event = DeadLetterEvent(
        original_topic=topic,
        original_partition=str(partition) if partition is not None else "-1",
        original_offset=str(offset) if offset is not None else "-1",
        original_key=key,
        original_value=value.decode("utf-8", errors="replace"),
        error=str(error),
        failed_at=datetime.now(UTC),
    )

    kafka_producer.publish(
        topic=LINK_VISITED_DLQ_TOPIC,
        key=key or "unknown",
        value=event_to_bytes(dlq_event),
    )

    kafka_messages_dlq.labels(topic=topic).inc()
    logger.warning(
        "Kafka message sent to DLQ original_topic=%s original_partition=%s"
        "original_offset=%s dlq_topic=%s key=%s",
        topic,
        partition,
        offset,
        LINK_VISITED_DLQ_TOPIC,
        key,
    )


async def _commit_message(consumer: Consumer, message: Message) -> None:
    await asyncio.to_thread(
        consumer.commit,
        message=message,
        asynchronous=False,
    )

    topic = message.topic() or LINK_VISITED_TOPIC
    kafka_messages_committed.labels(topic=topic).inc()
    logger.info(
        "Kafka message committed topic=%s partition=%s offset=%s key=%s",
        topic,
        message.partition(),
        message.offset(),
        _decode_key(message),
    )


def _decode_key(message: Message) -> str | None:
    key = message.key()

    if key is None:
        return None

    return key.decode("utf-8", errors="replace")


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop_consumer)
    signal.signal(signal.SIGTERM, stop_consumer)

    async def main() -> None:
        await init_db()
        try:
            await consume_visits()
        finally:
            await close_db()

    asyncio.run(main())
