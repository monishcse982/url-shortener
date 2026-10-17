import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

with patch("confluent_kafka.Producer"):
    from app.kafka.consumers import visit_consumer
    from app.kafka.events import DeadLetterEvent, LinkVisitedEvent
    from app.kafka.topics import LINK_VISITED_DLQ_TOPIC, LINK_VISITED_TOPIC


def make_message(value=b'{"link_id":42}', *, key=b"example-code"):
    return SimpleNamespace(
        topic=MagicMock(return_value=LINK_VISITED_TOPIC),
        partition=MagicMock(return_value=2),
        offset=MagicMock(return_value=19),
        key=MagicMock(return_value=key),
        value=MagicMock(return_value=value),
        error=MagicMock(return_value=None),
    )


class VisitConsumerMessageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.consumer = MagicMock()
        self.message = make_message()

    async def test_valid_event_is_processed_then_committed(self):
        event = LinkVisitedEvent(
            link_id=42,
            short_code="example-code",
            visited_at=datetime.now(UTC),
        )
        with patch.object(
            visit_consumer, "process_visit_event", new_callable=AsyncMock
        ) as process:
            self.message.value.return_value = event.model_dump_json().encode()
            await visit_consumer._handle_message(self.consumer, self.message)

        process.assert_awaited_once()
        self.consumer.commit.assert_called_once_with(
            message=self.message,
            asynchronous=False,
        )

    async def test_empty_value_is_committed_without_processing_or_dlq(self):
        self.message.value.return_value = None
        with (
            patch.object(
                visit_consumer, "process_visit_event", new_callable=AsyncMock
            ) as process,
            patch.object(visit_consumer.kafka_producer, "publish") as publish,
        ):
            await visit_consumer._handle_message(self.consumer, self.message)

        process.assert_not_awaited()
        publish.assert_not_called()
        self.consumer.commit.assert_called_once()

    async def test_invalid_json_and_invalid_utf8_are_sent_to_dlq_then_committed(self):
        for value in (b"not-json", b"\xff"):
            with self.subTest(value=value):
                self.consumer.reset_mock()
                self.message = make_message(value=value)
                with (
                    patch.object(visit_consumer.logger, "exception"),
                    patch.object(visit_consumer.kafka_producer, "publish") as publish,
                ):
                    await visit_consumer._handle_message(self.consumer, self.message)

                publish.assert_called_once()
                call = publish.call_args.kwargs
                self.assertEqual(call["topic"], LINK_VISITED_DLQ_TOPIC)
                event = DeadLetterEvent.model_validate_json(call["value"])
                self.assertEqual(event.original_topic, LINK_VISITED_TOPIC)
                self.assertEqual(event.original_partition, "2")
                self.assertEqual(event.original_offset, "19")
                self.assertEqual(event.original_key, "example-code")
                self.consumer.commit.assert_called_once()

    async def test_processing_failure_is_not_committed_or_sent_to_dlq(self):
        event = LinkVisitedEvent(
            link_id=42,
            short_code="example-code",
            visited_at=datetime.now(UTC),
        )
        self.message.value.return_value = event.model_dump_json().encode()
        with (
            patch.object(
                visit_consumer,
                "process_visit_event",
                new_callable=AsyncMock,
                side_effect=RuntimeError("database unavailable"),
            ),
            patch.object(visit_consumer.logger, "exception"),
            patch.object(visit_consumer.kafka_producer, "publish") as publish,
        ):
            await visit_consumer._handle_message(self.consumer, self.message)

        self.consumer.commit.assert_not_called()
        publish.assert_not_called()

    async def test_dlq_publish_failure_does_not_commit_invalid_message(self):
        self.message.value.return_value = b"not-json"
        with (
            patch.object(visit_consumer.logger, "exception"),
            patch.object(
                visit_consumer.kafka_producer,
                "publish",
                side_effect=RuntimeError("broker unavailable"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "broker unavailable"):
                await visit_consumer._handle_message(self.consumer, self.message)

        self.consumer.commit.assert_not_called()

    async def test_process_visit_event_persists_event_metadata(self):
        event = LinkVisitedEvent(
            link_id=42,
            short_code="example-code",
            visited_at=datetime.now(UTC),
            user_agent="unit-test-agent",
            referrer="https://example.com/referrer",
            ip_address="192.0.2.5",
        )
        repository = SimpleNamespace(create=AsyncMock())
        with patch.object(visit_consumer, "VisitsRepository", return_value=repository):
            await visit_consumer.process_visit_event(event)

        repository.create.assert_awaited_once_with(
            link_id=42,
            user_agent="unit-test-agent",
            referrer="https://example.com/referrer",
            ip_address="192.0.2.5",
        )

    async def test_consumer_polls_and_closes_after_shutdown_signal(self):
        fake_consumer = MagicMock()

        def stop_during_poll(_timeout):
            visit_consumer.running = False
            return None

        fake_consumer.poll.side_effect = stop_during_poll
        with patch.object(visit_consumer, "Consumer", return_value=fake_consumer):
            visit_consumer.running = True
            await visit_consumer.consume_visits()

        fake_consumer.subscribe.assert_called_once_with([LINK_VISITED_TOPIC])
        fake_consumer.close.assert_called_once()
        visit_consumer.running = True

    async def test_consumer_dispatches_polled_message(self):
        fake_consumer = MagicMock()
        message = make_message()
        poll_count = 0

        async def poll_in_thread(*_args):
            nonlocal poll_count
            poll_count += 1
            if poll_count == 1:
                return message
            visit_consumer.running = False
            return None

        with (
            patch.object(visit_consumer, "Consumer", return_value=fake_consumer),
            patch.object(
                visit_consumer.asyncio, "to_thread", side_effect=poll_in_thread
            ),
            patch.object(
                visit_consumer, "_handle_message", new_callable=AsyncMock
            ) as handle,
        ):
            visit_consumer.running = True
            await visit_consumer.consume_visits()

        handle.assert_awaited_once_with(fake_consumer, message)
        fake_consumer.close.assert_called_once()
        visit_consumer.running = True

    async def test_consumer_error_closes_consumer_and_reraises(self):
        fake_consumer = MagicMock()
        message = make_message()
        message.error.return_value = "broker failure"
        with (
            patch.object(visit_consumer, "Consumer", return_value=fake_consumer),
            patch.object(
                visit_consumer.asyncio,
                "to_thread",
                new_callable=AsyncMock,
                return_value=message,
            ),
            patch.object(
                visit_consumer, "KafkaException", side_effect=RuntimeError("broker")
            ),
            patch.object(visit_consumer.logger, "error"),
        ):
            visit_consumer.running = True
            with self.assertRaisesRegex(RuntimeError, "broker"):
                await visit_consumer.consume_visits()

        fake_consumer.close.assert_called_once()
        visit_consumer.running = True


class VisitConsumerHelpersTests(unittest.TestCase):
    def test_stop_consumer_clears_running_flag(self):
        visit_consumer.running = True

        visit_consumer.stop_consumer()

        self.assertFalse(visit_consumer.running)
        visit_consumer.running = True

    def test_decode_key_handles_missing_and_invalid_utf8_keys(self):
        self.assertIsNone(visit_consumer._decode_key(make_message(key=None)))
        self.assertEqual(
            visit_consumer._decode_key(make_message(key=b"\xff")), "\ufffd"
        )

    def test_dlq_metadata_defaults_missing_partition_and_offset(self):
        with patch.object(visit_consumer.kafka_producer, "publish") as publish:
            from asyncio import run

            run(
                visit_consumer._publish_to_dlq(
                    topic=LINK_VISITED_TOPIC,
                    partition=None,
                    offset=None,
                    key=None,
                    value=b"not-json",
                    error=ValueError("invalid event"),
                )
            )

        event = DeadLetterEvent.model_validate_json(publish.call_args.kwargs["value"])
        self.assertEqual(event.original_partition, "-1")
        self.assertEqual(event.original_offset, "-1")
        self.assertEqual(publish.call_args.kwargs["key"], "unknown")

    def test_dead_letter_payload_retains_non_utf8_data_safely(self):
        value = b"broken:\xff"
        with patch.object(visit_consumer.kafka_producer, "publish") as publish:
            from asyncio import run

            run(
                visit_consumer._publish_to_dlq(
                    topic=LINK_VISITED_TOPIC,
                    partition=1,
                    offset=2,
                    key="code",
                    value=value,
                    error=ValueError("bad payload"),
                )
            )

        payload = json.loads(publish.call_args.kwargs["value"])
        self.assertEqual(payload["original_value"], "broken:\ufffd")
