from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EventIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(
        ...,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description="Topic name, e.g. auth.login or payments",
    )
    event_id: str = Field(
        ...,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9_.:-]+$",
        description="Unique id per topic.",
    )
    timestamp: datetime
    source: str = Field(..., min_length=1, max_length=128)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def to_queue_payload(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class PublishResponse(BaseModel):
    accepted: int
    queued: int


class EventOut(BaseModel):
    id: int
    logical_seq: int
    topic: str
    event_id: str
    timestamp: datetime
    source: str
    payload: dict[str, Any]
    processed_at: datetime


class StatsResponse(BaseModel):
    received: int
    unique_processed: int
    duplicate_dropped: int
    duplicate_rate: float
    topics: dict[str, int]
    uptime_seconds: float


class ProcessResult(BaseModel):
    inserted: bool
    status: str
