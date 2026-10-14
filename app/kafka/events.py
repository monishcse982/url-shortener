import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class LinkVisitedEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    link_id: int
    short_code: str = Field(min_length=3, max_length=32)
    visited_at: datetime
    user_agent: str | None = Field(default=None, max_length=512)
    referrer: str | None = Field(default=None, max_length=2048)
    ip_address: str | None = Field(default=None, max_length=64)


class DeadLetterEvent(BaseModel):
    original_topic: str
    original_partition: str
    original_offset: str
    original_key: str | None
    original_value: str | None
    error: str
    failed_at: datetime


def event_to_bytes(event: BaseModel) -> bytes:
    return event.model_dump_json().encode("utf-8")
