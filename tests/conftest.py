from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio

from app.database import EventStore
from app.models import EventIn


def sqlite_url(path: Path) -> str:
    return "sqlite+aiosqlite:///" + str(path).replace("\\", "/")


@pytest_asyncio.fixture
async def store(tmp_path):
    event_store = EventStore(sqlite_url(tmp_path / "aggregator.db"))
    await event_store.init()
    yield event_store
    await event_store.close()


@pytest.fixture
def event_factory():
    def factory(
        index: int = 0,
        *,
        topic: str = "auth.login",
        event_id: str | None = None,
        source: str = "pytest",
        payload: dict | None = None,
        timestamp: datetime | None = None,
    ) -> EventIn:
        return EventIn(
            topic=topic,
            event_id=event_id or f"event-{index}",
            timestamp=timestamp
            or datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index),
            source=source,
            payload=payload if payload is not None else {"seq": index, "message": "test"},
        )

    return factory
