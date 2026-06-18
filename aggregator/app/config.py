from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    redis_url: str
    redis_stream: str
    redis_group: str
    worker_count: int
    worker_batch_size: int
    stale_message_ms: int


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_settings() -> Settings:
    return Settings(
        database_url=os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./data/aggregator.db",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        redis_stream=os.getenv("REDIS_STREAM", "log-events"),
        redis_group=os.getenv("REDIS_GROUP", "aggregator-workers"),
        worker_count=max(1, _int_env("WORKER_COUNT", 4)),
        worker_batch_size=max(1, _int_env("WORKER_BATCH_SIZE", 100)),
        stale_message_ms=max(1000, _int_env("STALE_MESSAGE_MS", 60000)),
    )
