import unittest
from unittest.mock import AsyncMock, MagicMock, patch

with patch("confluent_kafka.Producer"):
    from app import main


class AppLifespanTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_and_shutdown_manage_dependencies(self):
        cache = MagicMock()
        cache.ping = AsyncMock()
        cache.aclose = AsyncMock()
        application = MagicMock()

        with (
            patch.object(main, "init_db", new_callable=AsyncMock) as init_db,
            patch.object(main.Redis, "from_url", return_value=cache) as from_url,
            patch.object(main, "consume_visits", new_callable=AsyncMock) as consume,
            patch.object(main, "stop_consumer") as stop_consumer,
            patch.object(main, "close_db", new_callable=AsyncMock) as close_db,
            patch.object(main.kafka_producer, "flush") as flush,
        ):
            async with main.lifespan(application):
                self.assertIs(application.state.cache, cache)

        init_db.assert_awaited_once()
        from_url.assert_called_once_with(main.settings.cache_url, decode_responses=True)
        cache.ping.assert_awaited_once()
        consume.assert_awaited_once()
        stop_consumer.assert_called_once()
        cache.aclose.assert_awaited_once()
        close_db.assert_awaited_once()
        flush.assert_called_once()

    async def test_cache_startup_failure_still_closes_initialized_resources(self):
        cache = MagicMock()
        cache.ping = AsyncMock(side_effect=ConnectionError("cache unavailable"))
        cache.aclose = AsyncMock()
        application = MagicMock()

        with (
            patch.object(main, "init_db", new_callable=AsyncMock),
            patch.object(main.Redis, "from_url", return_value=cache),
            patch.object(main, "consume_visits", new_callable=AsyncMock) as consume,
            patch.object(main, "stop_consumer") as stop_consumer,
            patch.object(main, "close_db", new_callable=AsyncMock) as close_db,
            patch.object(main.kafka_producer, "flush") as flush,
        ):
            with self.assertRaisesRegex(ConnectionError, "cache unavailable"):
                async with main.lifespan(application):
                    self.fail("startup must not yield when cache ping fails")

        consume.assert_not_awaited()
        stop_consumer.assert_called_once()
        cache.aclose.assert_awaited_once()
        close_db.assert_awaited_once()
        flush.assert_called_once()
