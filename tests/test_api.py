from __future__ import annotations

from fastapi.testclient import TestClient

from app.database import EventStore
from app.main import create_app
from tests.conftest import sqlite_url


class FakeQueue:
    def __init__(self):
        self.events = []
        self.connected = False
        self.closed = False

    async def connect(self):
        self.connected = True

    async def close(self):
        self.closed = True

    async def health(self):
        return True

    async def publish_many(self, events):
        self.events.extend(events)
        return len(events)


def make_payload(event_id: str = "api-1"):
    return {
        "topic": "auth.login",
        "event_id": event_id,
        "timestamp": "2026-01-01T00:00:00Z",
        "source": "api-test",
        "payload": {"message": "hello"},
    }


def test_publish_single_event_queues_one(tmp_path):
    queue = FakeQueue()
    store = EventStore(sqlite_url(tmp_path / "api-single.db"))
    app = create_app(store=store, queue=queue, start_workers=False)

    with TestClient(app) as client:
        response = client.post("/publish", json=make_payload())

    assert response.status_code == 200
    assert response.json() == {"accepted": 1, "queued": 1}
    assert len(queue.events) == 1
    assert queue.connected is True
    assert queue.closed is True


def test_publish_batch_queues_all_events(tmp_path):
    queue = FakeQueue()
    store = EventStore(sqlite_url(tmp_path / "api-batch.db"))
    app = create_app(store=store, queue=queue, start_workers=False)
    payload = [make_payload("api-1"), make_payload("api-2"), make_payload("api-3")]

    with TestClient(app) as client:
        response = client.post("/publish", json=payload)

    assert response.status_code == 200
    assert response.json() == {"accepted": 3, "queued": 3}
    assert [event.event_id for event in queue.events] == ["api-1", "api-2", "api-3"]


def test_publish_empty_batch_is_rejected(tmp_path):
    queue = FakeQueue()
    store = EventStore(sqlite_url(tmp_path / "api-empty.db"))
    app = create_app(store=store, queue=queue, start_workers=False)

    with TestClient(app) as client:
        response = client.post("/publish", json=[])

    assert response.status_code == 400
    assert queue.events == []


def test_publish_invalid_event_returns_422(tmp_path):
    queue = FakeQueue()
    store = EventStore(sqlite_url(tmp_path / "api-invalid.db"))
    app = create_app(store=store, queue=queue, start_workers=False)
    payload = make_payload()
    payload["topic"] = "invalid topic"

    with TestClient(app) as client:
        response = client.post("/publish", json=payload)

    assert response.status_code == 422
    assert queue.events == []


def test_stats_endpoint_returns_initial_shape(tmp_path):
    queue = FakeQueue()
    store = EventStore(sqlite_url(tmp_path / "api-stats.db"))
    app = create_app(store=store, queue=queue, start_workers=False)

    with TestClient(app) as client:
        response = client.get("/stats")

    assert response.status_code == 200
    body = response.json()
    assert body["received"] == 0
    assert body["unique_processed"] == 0
    assert body["duplicate_dropped"] == 0
    assert body["topics"] == {}
    assert body["uptime_seconds"] >= 0

