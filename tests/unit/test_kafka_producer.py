import unittest
from unittest.mock import MagicMock, patch

from confluent_kafka import KafkaException

with patch("confluent_kafka.Producer"):
    from app.kafka import producer as producer_module


class KafkaProducerTests(unittest.TestCase):
    def setUp(self):
        self.producer = producer_module.KafkaProducer.__new__(
            producer_module.KafkaProducer
        )
        self.producer._producer = MagicMock()

    def test_publish_enqueues_message_and_polls(self):
        with (
            patch.object(producer_module.kafka_publish_requests, "labels") as requests,
            patch.object(
                producer_module.kafka_publish_duration_seconds, "labels"
            ) as duration,
        ):
            duration.return_value.time.return_value.__enter__ = MagicMock()
            duration.return_value.time.return_value.__exit__ = MagicMock(
                return_value=False
            )
            self.producer.publish(topic="link.visited", key="code", value=b"payload")

        requests.assert_called_once_with(topic="link.visited")
        self.producer._producer.produce.assert_called_once()
        self.assertEqual(
            self.producer._producer.produce.call_args.kwargs["topic"], "link.visited"
        )
        self.assertEqual(
            self.producer._producer.produce.call_args.kwargs["key"], "code"
        )
        self.producer._producer.poll.assert_called_once_with(0)

    def test_publish_counts_and_reraises_queue_full_error(self):
        self.producer._producer.produce.side_effect = BufferError("queue full")
        with (
            patch.object(producer_module.kafka_publish_requests, "labels"),
            patch.object(
                producer_module.kafka_publish_duration_seconds, "labels"
            ) as duration,
            patch.object(producer_module.kafka_publish_error, "labels") as errors,
            patch.object(producer_module.logger, "exception"),
        ):
            duration.return_value.time.return_value.__enter__ = MagicMock()
            duration.return_value.time.return_value.__exit__ = MagicMock(
                return_value=False
            )
            with self.assertRaisesRegex(BufferError, "queue full"):
                self.producer.publish(
                    topic="link.visited", key="code", value=b"payload"
                )

        errors.assert_called_once_with(topic="link.visited", error_type="BufferError")
        self.producer._producer.poll.assert_not_called()

    def test_publish_counts_and_reraises_kafka_exception(self):
        self.producer._producer.produce.side_effect = KafkaException("broker error")
        with (
            patch.object(producer_module.kafka_publish_requests, "labels"),
            patch.object(
                producer_module.kafka_publish_duration_seconds, "labels"
            ) as duration,
            patch.object(producer_module.kafka_publish_error, "labels") as errors,
            patch.object(producer_module.logger, "exception"),
        ):
            duration.return_value.time.return_value.__enter__ = MagicMock()
            duration.return_value.time.return_value.__exit__ = MagicMock(
                return_value=False
            )
            with self.assertRaises(KafkaException):
                self.producer.publish(
                    topic="link.visited", key="code", value=b"payload"
                )

        errors.assert_called_once_with(
            topic="link.visited", error_type="KafkaException"
        )

    def test_flush_logs_remaining_messages(self):
        self.producer._producer.flush.return_value = 3
        with patch.object(producer_module.logger, "warning") as warning:
            self.producer.flush()

        warning.assert_called_once()

    def test_flush_logs_completion_when_queue_is_empty(self):
        self.producer._producer.flush.return_value = 0
        with patch.object(producer_module.logger, "info") as info:
            self.producer.flush()

        info.assert_any_call("Kafka producer flush completed")

    def test_delivery_report_updates_success_and_error_metrics(self):
        message = MagicMock()
        message.key.return_value = b"code"
        message.topic.return_value = "link.visited"
        message.partition.return_value = 1
        message.offset.return_value = 8
        kafka_error = MagicMock()
        kafka_error.name.return_value = "BROKER_ERROR"

        with (
            patch.object(producer_module.kafka_publish_success, "labels") as success,
            patch.object(producer_module.kafka_publish_error, "labels") as errors,
        ):
            producer_module.KafkaProducer._delivery_report(None, message)
            producer_module.KafkaProducer._delivery_report(kafka_error, message)

        success.assert_called_once_with(topic="link.visited")
        errors.assert_called_once_with(topic="link.visited", error_type="BROKER_ERROR")
