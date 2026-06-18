from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest

from app.database import EventStore
from tests.conftest import sqlite_url


async def test_initial_stats_are_zero(store):
    stats = await store.stats(uptime_seconds=1.25)

    assert stats["received"] == 0
    assert stats["unique_processed"] == 0
    assert stats["duplicate_dropped"] == 0
    assert stats["topics"] == {}


async def test_process_unique_event_increments_unique_counter(store, event_factory):
    result = await store.process_event(event_factory(1))
    stats = await store.stats(uptime_seconds=0)

    assert result.inserted is True
    assert stats["received"] == 1
    assert stats["unique_processed"] == 1
    assert stats["duplicate_dropped"] == 0


async def test_duplicate_event_is_dropped_idempotently(store, event_factory):
    event = event_factory(2)

    first = await store.process_event(event)
    second = await store.process_event(event)
    stats = await store.stats(uptime_seconds=0)
    events = await store.list_events()

    assert first.inserted is True
    assert second.inserted is False
    assert stats["received"] == 2
    assert stats["unique_processed"] == 1
    assert stats["duplicate_dropped"] == 1
    assert len(events) == 1


async def test_same_event_id_on_different_topics_is_allowed(store, event_factory):
    event_a = event_factory(3, topic="auth.login", event_id="shared-id")
    event_b = event_factory(4, topic="payments", event_id="shared-id")

    await store.process_event(event_a)
    await store.process_event(event_b)
    events = await store.list_events()

    assert len(events) == 2
    assert {event["topic"] for event in events} == {"auth.login", "payments"}


async def test_list_events_can_filter_by_topic(store, event_factory):
    await store.process_event(event_factory(5, topic="auth.login"))
    await store.process_event(event_factory(6, topic="payments"))

    auth_events = await store.list_events(topic="auth.login")

    assert len(auth_events) == 1
    assert auth_events[0]["topic"] == "auth.login"


async def test_events_are_ordered_by_timestamp_then_logical_sequence(store, event_factory):
    late = event_factory(
        7,
        event_id="late",
        timestamp=datetime(2026, 1, 1, 0, 0, 10, tzinfo=timezone.utc),
    )
    early = event_factory(
        8,
        event_id="early",
        timestamp=datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc),
    )

    await store.process_event(late)
    await store.process_event(early)
    events = await store.list_events()

    assert [event["event_id"] for event in events] == ["early", "late"]
    assert all(event["logical_seq"] >= 1 for event in events)


async def test_audit_log_records_processed_and_duplicate(store, event_factory):
    event = event_factory(9)

    await store.process_event(event)
    await store.process_event(event)
    audit = await store.list_audit(limit=10)

    assert [row["status"] for row in audit[:2]] == ["duplicate", "processed"]


async def test_concurrent_duplicate_processing_inserts_once(store, event_factory):
    event = event_factory(10, event_id="race-same-id")

    results = await asyncio.gather(*(store.process_event(event) for _ in range(50)))
    stats = await store.stats(uptime_seconds=0)
    events = await store.list_events()

    assert sum(result.inserted for result in results) == 1
    assert stats["received"] == 50
    assert stats["unique_processed"] == 1
    assert stats["duplicate_dropped"] == 49
    assert len(events) == 1


async def test_concurrent_unique_processing_keeps_all_events(store, event_factory):
    events = [event_factory(index, topic="system.metrics") for index in range(30)]

    results = await asyncio.gather(*(store.process_event(event) for event in events))
    stats = await store.stats(uptime_seconds=0)

    assert all(result.inserted for result in results)
    assert stats["received"] == 30
    assert stats["unique_processed"] == 30
    assert stats["topics"] == {"system.metrics": 30}


async def test_store_persists_dedup_state_after_reopen(tmp_path, event_factory):
    db_path = tmp_path / "persistent.db"
    url = sqlite_url(db_path)
    event = event_factory(11, event_id="persisted")

    first_store = EventStore(url)
    await first_store.init()
    await first_store.process_event(event)
    await first_store.close()

    second_store = EventStore(url)
    await second_store.init()
    result = await second_store.process_event(event)
    stats = await second_store.stats(uptime_seconds=0)
    await second_store.close()

    assert result.inserted is False
    assert stats["received"] == 2
    assert stats["unique_processed"] == 1
    assert stats["duplicate_dropped"] == 1


async def test_small_stress_batch_has_consistent_counts(store, event_factory):
    unique_events = [event_factory(index, topic="stress") for index in range(200)]
    duplicate_events = [unique_events[index % len(unique_events)] for index in range(100)]
    all_events = unique_events + duplicate_events

    started = time.perf_counter()
    await asyncio.gather(*(store.process_event(event) for event in all_events))
    elapsed = time.perf_counter() - started
    stats = await store.stats(uptime_seconds=0)

    assert elapsed < 30
    assert stats["received"] == 300
    assert stats["unique_processed"] == 200
    assert stats["duplicate_dropped"] == 100
    assert stats["duplicate_rate"] == pytest.approx(0.3333, abs=0.001)
