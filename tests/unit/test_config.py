import unittest
from unittest.mock import patch

from app.core.config import Settings, tortoise_database_url
from app.kafka.config import kafka_consumer_config, kafka_producer_config


class SettingsTests(unittest.TestCase):
    def test_base_url_omits_default_scheme_ports(self):
        self.assertEqual(
            Settings(app_scheme="http", app_host="example.test", app_port=80).base_url,
            "http://example.test",
        )
        self.assertEqual(
            Settings(
                app_scheme="https", app_host="example.test", app_port=443
            ).base_url,
            "https://example.test",
        )

    def test_base_url_includes_non_default_port(self):
        self.assertEqual(
            Settings(
                app_scheme="http", app_host="example.test", app_port=8080
            ).base_url,
            "http://example.test:8080",
        )

    def test_database_url_conversion_only_rewrites_asyncpg_scheme(self):
        self.assertEqual(
            tortoise_database_url("postgresql+asyncpg://user@db/app"),
            "postgres://user@db/app",
        )
        self.assertEqual(
            tortoise_database_url("sqlite://:memory:"), "sqlite://:memory:"
        )

    def test_kafka_configs_include_optional_security_settings_when_set(self):
        with (
            patch("app.kafka.config.settings.kafka_bootstrap_servers", "broker:9092"),
            patch("app.kafka.config.settings.kafka_security_protocol", "SASL_SSL"),
            patch("app.kafka.config.settings.kafka_sasl_mechanism", "PLAIN"),
            patch("app.kafka.config.settings.kafka_username", "worker"),
            patch("app.kafka.config.settings.kafka_password", "secret"),
            patch("app.kafka.config.settings.kafka_client_id", "api"),
            patch("app.kafka.config.settings.kafka_consumer_group_id", "visits"),
        ):
            producer = kafka_producer_config()
            consumer = kafka_consumer_config()

        expected_common = {
            "bootstrap.servers": "broker:9092",
            "security.protocol": "SASL_SSL",
            "sasl.mechanism": "PLAIN",
            "sasl.username": "worker",
            "sasl.password": "secret",
        }
        self.assertEqual(producer, {**expected_common, "client.id": "api"})
        self.assertEqual(
            consumer,
            {
                **expected_common,
                "group.id": "visits",
                "auto.offset.reset": "earliest",
                "enable.auto.commit": "false",
            },
        )

    def test_kafka_config_omits_empty_optional_security_settings(self):
        with (
            patch(
                "app.kafka.config.settings.kafka_bootstrap_servers", "localhost:9092"
            ),
            patch("app.kafka.config.settings.kafka_client_id", "url-visit-tracker-api"),
            patch("app.kafka.config.settings.kafka_security_protocol", ""),
            patch("app.kafka.config.settings.kafka_sasl_mechanism", ""),
            patch("app.kafka.config.settings.kafka_username", ""),
            patch("app.kafka.config.settings.kafka_password", ""),
        ):
            config = kafka_producer_config()

        self.assertEqual(config["bootstrap.servers"], "localhost:9092")
        self.assertEqual(config["client.id"], "url-visit-tracker-api")
        self.assertNotIn("security.protocol", config)
        self.assertNotIn("sasl.mechanism", config)
        self.assertNotIn("sasl.username", config)
        self.assertNotIn("sasl.password", config)
