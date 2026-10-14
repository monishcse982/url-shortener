from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    log_level: str = "INFO"
    log_format: str = "plain"
    app_host: str = Field(default="localhost")
    app_port: int = Field(default=8000)
    app_scheme: str = Field(default="http")
    database_url: str = Field(default="sqlite://:memory:")
    migration_database_url: str = Field(default="sqlite://")
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_security_protocol: str = "SASL_PLAINTEXT"
    kafka_sasl_mechanism: str = "PLAIN"
    kafka_username: str = "url_tracker_user"
    kafka_password: str = ""
    kafka_client_id: str = "url-visit-tracker-api"
    kafka_consumer_group_id: str = "url-visit-tracker-visits"
    kafka_visit_topic: str = "link.visited"
    kafka_visit_dlq_topic: str = "link.visited.dlq"
    cache_url: str = "redis://redis:6379"
    cache_ttl: int = 600

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def base_url(self) -> str:
        default_port = (self.app_scheme == "http" and self.app_port == 80) or (
            self.app_scheme == "https" and self.app_port == 443
        )
        if default_port:
            return f"{self.app_scheme}://{self.app_host}"
        return f"{self.app_scheme}://{self.app_host}:{self.app_port}"


settings = Settings()


def tortoise_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgres://", 1)
    return database_url


TORTOISE_ORM = {
    "connections": {"default": tortoise_database_url(settings.migration_database_url)},
    "apps": {
        "models": {
            "models": ["app.db.models"],
            "default_connection": "default",
            "migrations": "app.migrations",
        }
    },
    "use_tz": True,
    "timezone": "UTC",
}
