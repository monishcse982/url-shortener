from app.core.config import settings


def kafka_common_config() -> dict[str, str]:
    config = {"bootstrap.servers": settings.kafka_bootstrap_servers}

    if settings.kafka_security_protocol:
        config["security.protocol"] = settings.kafka_security_protocol

    if settings.kafka_sasl_mechanism:
        config["sasl.mechanism"] = settings.kafka_sasl_mechanism

    if settings.kafka_username:
        config["sasl.username"] = settings.kafka_username

    if settings.kafka_password:
        config["sasl.password"] = settings.kafka_password

    return config


def kafka_producer_config() -> dict[str, str]:
    return {**kafka_common_config(), "client.id": settings.kafka_client_id}


def kafka_consumer_config() -> dict[str, str]:
    return {
        **kafka_common_config(),
        "group.id": settings.kafka_consumer_group_id,
        "auto.offset.reset": "earliest",
        "enable.auto.commit": "false",
    }
