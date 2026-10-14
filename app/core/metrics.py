from prometheus_client import Counter, Histogram

short_links_creation_requests = Counter(
    "short_links_creation_requests", "Total number of short links creation requests"
)

short_links_created = Counter(
    "short_links_created", "Total number of short links created"
)

short_links_creation_error = Counter(
    "short_links_creation_error",
    "Total number of short link creation errors",
    ["error_type"],
)

short_links_create_duration_seconds = Histogram(
    "short_links_create_duration_seconds", "Time spent creating short links"
)

short_link_access_request_count = Counter(
    "short_link_access_request_count",
    "Total number of short link access requests",
)


kafka_publish_requests = Counter(
    "kafka_publish_requests",
    "Total number of Kafka publish requests",
    ["topic"],
)

kafka_publish_success = Counter(
    "kafka_publish_success",
    "Total number of Kafka messages delivered successfully",
    ["topic"],
)

kafka_publish_error = Counter(
    "kafka_publish_error",
    "Total number of Kafka publish or delivery errors",
    ["topic", "error_type"],
)

kafka_publish_duration_seconds = Histogram(
    "kafka_publish_duration_seconds",
    "Time spent enqueueing Kafka messages for publish",
    ["topic"],
)

kafka_messages_received = Counter(
    "kafka_messages_received",
    "Total number of Kafka messages received by consumers",
    ["topic"],
)

kafka_messages_processed = Counter(
    "kafka_messages_processed",
    "Total number of Kafka messages processed successfully",
    ["topic"],
)

kafka_message_processing_error = Counter(
    "kafka_message_processing_error",
    "Total number of Kafka message processing errors",
    ["topic", "error_type"],
)

kafka_messages_committed = Counter(
    "kafka_messages_committed",
    "Total number of Kafka messages committed by consumers",
    ["topic"],
)

kafka_messages_dlq = Counter(
    "kafka_messages_dlq",
    "Total number of Kafka messages sent to DLQ",
    ["topic"],
)

kafka_message_processing_duration_seconds = Histogram(
    "kafka_message_processing_duration_seconds",
    "Time spent processing Kafka messages",
    ["topic"],
)

time_limited_link_cache_hits = Counter(
    "time_limited_link_cache_hits",
    "Total number of time-limited links successfully served from cache",
)

time_limited_link_cache_misses = Counter(
    "time_limited_link_cache_misses",
    "Total number of time-limited links successfully served from"
    "the database after a cache miss",
)

__all__ = [
    "kafka_message_processing_duration_seconds",
    "kafka_message_processing_error",
    "kafka_messages_committed",
    "kafka_messages_dlq",
    "kafka_messages_processed",
    "kafka_messages_received",
    "kafka_publish_duration_seconds",
    "kafka_publish_error",
    "kafka_publish_requests",
    "kafka_publish_success",
    "short_link_access_request_count",
    "short_links_create_duration_seconds",
    "short_links_created",
    "short_links_creation_error",
    "short_links_creation_requests",
    "time_limited_link_cache_hits",
    "time_limited_link_cache_misses",
]
