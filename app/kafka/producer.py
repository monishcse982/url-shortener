import logging

from confluent_kafka import KafkaException, Producer

from app.core.metrics import (
    kafka_publish_duration_seconds,
    kafka_publish_error,
    kafka_publish_requests,
    kafka_publish_success,
)
from app.kafka.config import kafka_producer_config

logger = logging.getLogger(__name__)


class KafkaProducer:
    def __init__(self) -> None:
        self._producer = Producer(kafka_producer_config())
        logger.info("Kafka producer initialized")

    def publish(
        self,
        *,
        topic: str,
        key: str,
        value: bytes,
    ) -> None:
        kafka_publish_requests.labels(topic=topic).inc()
        logger.info(
            "Kafka publish requested topic=%s key=%s value_bytes=%s",
            topic,
            key,
            len(value),
        )

        with kafka_publish_duration_seconds.labels(topic=topic).time():
            try:
                self._producer.produce(
                    topic=topic,
                    key=key,
                    value=value,
                    callback=self._delivery_report,
                )
            except BufferError:
                kafka_publish_error.labels(
                    topic=topic,
                    error_type="BufferError",
                ).inc()
                logger.exception(
                    "Kafka publish failed: local queue full topic=%s key=%s", topic, key
                )
                raise
            except KafkaException as error:
                kafka_publish_error.labels(
                    topic=topic,
                    error_type=type(error).__name__,
                ).inc()
                logger.exception("Kafka publish failed topic=%s key=%s", topic, key)
                raise

        self._producer.poll(0)

    def flush(self) -> None:
        logger.info("Kafka producer flush started")

        remaining = self._producer.flush()

        if remaining:
            logger.warning("Kafka flush incomplete remaining=%s", remaining)
            return

        logger.info("Kafka producer flush completed")

    @staticmethod
    def _delivery_report(error, message) -> None:
        key = message.key().decode("utf-8") if message.key() else None

        topic = message.topic()

        if error is not None:
            kafka_publish_error.labels(
                topic=topic,
                error_type=error.name(),
            ).inc()
            logger.error(
                "Kafka delivery failed topic=%s key=%s error=%s",
                topic,
                key,
                error,
            )
            return

        kafka_publish_success.labels(topic=topic).inc()
        logger.info(
            "Kafka message delivered topic=%s partition=%s offset=%s key=%s",
            topic,
            message.partition(),
            message.offset(),
            key,
        )


kafka_producer = KafkaProducer()
