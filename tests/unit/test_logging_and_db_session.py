import json
import logging
import sys
import unittest
from unittest.mock import AsyncMock, patch

from app.core.logging import JsonFormatter, setup_logging
from app.db.session import close_db, init_db


class JsonFormatterTests(unittest.TestCase):
    def test_format_includes_context_and_exception(self):
        try:
            raise ValueError("bad input")
        except ValueError:
            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname=__file__,
                lineno=10,
                msg="Failed for %s",
                args=("example",),
                exc_info=sys.exc_info(),
            )
        record.correlation_id = "request-123"

        formatted = json.loads(JsonFormatter().format(record))

        self.assertEqual(formatted["logger"], "test.logger")
        self.assertEqual(formatted["level"], "ERROR")
        self.assertEqual(formatted["message"], "Failed for example")
        self.assertEqual(formatted["correlation_id"], "request-123")
        self.assertIn("ValueError: bad input", formatted["exception"])

    def test_format_without_optional_context(self):
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="Ready",
            args=(),
            exc_info=None,
        )

        formatted = json.loads(JsonFormatter().format(record))

        self.assertIsNone(formatted["correlation_id"])
        self.assertNotIn("exception", formatted)

    def test_setup_logging_selects_json_formatter_and_uppercase_level(self):
        with (
            patch("app.core.logging.settings.log_level", "debug"),
            patch("app.core.logging.settings.log_format", "json"),
            patch("app.core.logging.dictConfig") as dict_config,
        ):
            setup_logging()

        config = dict_config.call_args.args[0]
        self.assertEqual(config["root"]["level"], "DEBUG")
        self.assertEqual(config["handlers"]["console"]["formatter"], "json")

    def test_setup_logging_falls_back_to_plain_formatter(self):
        with (
            patch("app.core.logging.settings.log_level", "warning"),
            patch("app.core.logging.settings.log_format", "unknown"),
            patch("app.core.logging.dictConfig") as dict_config,
        ):
            setup_logging()

        config = dict_config.call_args.args[0]
        self.assertEqual(config["root"]["level"], "WARNING")
        self.assertEqual(config["handlers"]["console"]["formatter"], "plain")


class DatabaseSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_init_db_configures_tortoise(self):
        with (
            patch("app.db.session.settings.database_url", "sqlite://:memory:"),
            patch("app.db.session.Tortoise.init", new_callable=AsyncMock) as init,
        ):
            await init_db()

        init.assert_awaited_once_with(
            db_url="sqlite://:memory:",
            modules={"models": ["app.db.models"]},
            use_tz=True,
            timezone="UTC",
            _enable_global_fallback=True,
        )

    async def test_close_db_closes_tortoise_connections(self):
        with patch(
            "app.db.session.Tortoise.close_connections", new_callable=AsyncMock
        ) as close_connections:
            await close_db()

        close_connections.assert_awaited_once()
