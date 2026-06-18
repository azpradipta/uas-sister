from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.models import EventIn


def test_valid_event_is_accepted():
    event = EventIn(
        topic="auth.login",
        event_id="evt-1",
        timestamp="2026-01-01T00:00:00Z",
        source="unit-test",
        payload={"level": "INFO"},
    )

    assert event.topic == "auth.login"
    assert event.timestamp.tzinfo is not None


def test_naive_timestamp_is_normalized_to_utc():
    event = EventIn(
        topic="auth.login",
        event_id="evt-2",
        timestamp=datetime(2026, 1, 1, 0, 0, 0),
        source="unit-test",
        payload={},
    )

    assert event.timestamp.tzinfo == timezone.utc


def test_invalid_topic_is_rejected():
    with pytest.raises(ValidationError):
        EventIn(
            topic="auth login",
            event_id="evt-3",
            timestamp="2026-01-01T00:00:00Z",
            source="unit-test",
            payload={},
        )


def test_payload_must_be_json_object():
    with pytest.raises(ValidationError):
        EventIn(
            topic="auth.login",
            event_id="evt-5",
            timestamp="2026-01-01T00:00:00Z",
            source="unit-test",
            payload=["not", "an", "object"],
        )
