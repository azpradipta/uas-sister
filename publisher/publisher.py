from __future__ import annotations

import asyncio
import os
import random
import time
import uuid
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx


LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")
DEFAULT_TOPICS = ("auth.login", "payments", "inventory", "system.metrics")


def int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def parse_topics() -> tuple[str, ...]:
    raw = os.getenv("TOPICS")
    if not raw:
        return DEFAULT_TOPICS
    topics = tuple(item.strip() for item in raw.split(",") if item.strip())
    return topics or DEFAULT_TOPICS


def make_unique_event(
    index: int,
    source: str,
    topics: tuple[str, ...],
    rng: random.Random,
    seed: str | None,
) -> dict[str, Any]:
    topic = rng.choice(topics)
    if seed is None:
        event_id = f"{source}-{uuid.uuid4().hex}"
        timestamp = datetime.now(timezone.utc)
    else:
        event_id = f"{source}-{uuid.uuid5(uuid.NAMESPACE_URL, f'{source}-{seed}-{index}').hex}"
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=index)

    return {
        "topic": topic,
        "event_id": event_id,
        "timestamp": timestamp.isoformat(),
        "source": source,
        "payload": {
            "seq": index,
            "level": rng.choice(LEVELS),
            "message": f"log message {index}",
            "value": rng.randint(1, 1000),
        },
    }


def build_events(
    total: int,
    duplicate_rate: float,
    source: str,
    seed: str | None = None,
) -> list[dict[str, Any]]:
    duplicate_rate = min(max(duplicate_rate, 0.0), 0.95)
    topics = parse_topics()
    rng = random.Random(seed) if seed is not None else random.Random()
    unique_count = max(1, int(total * (1.0 - duplicate_rate)))
    duplicate_count = max(0, total - unique_count)

    unique_events = [
        make_unique_event(index, source, topics, rng, seed) for index in range(unique_count)
    ]
    duplicates = [deepcopy(rng.choice(unique_events)) for _ in range(duplicate_count)]
    events = unique_events + duplicates
    rng.shuffle(events)
    return events


def chunks(items: list[dict[str, Any]], size: int):
    for index in range(0, len(items), size):
        yield items[index : index + size]


async def post_batch(
    client: httpx.AsyncClient,
    url: str,
    batch: list[dict[str, Any]],
    batch_number: int,
    retries: int,
) -> int:
    delay = 0.25
    for attempt in range(1, retries + 1):
        try:
            response = await client.post(url, json=batch)
            response.raise_for_status()
            data = response.json()
            return int(data["queued"])
        except Exception as exc:
            if attempt == retries:
                raise RuntimeError(f"batch {batch_number} failed after {retries} attempts") from exc
            await asyncio.sleep(delay)
            delay = min(delay * 2, 4.0)
    return 0


async def run() -> None:
    target_url = os.getenv("TARGET_URL", "http://localhost:8080/publish")
    total_events = int_env("TOTAL_EVENTS", 20000)
    duplicate_rate = float_env("DUPLICATE_RATE", 0.30)
    batch_size = max(1, int_env("BATCH_SIZE", 500))
    concurrency = max(1, int_env("CONCURRENCY", 4))
    retries = max(1, int_env("RETRIES", 5))
    source = os.getenv("SOURCE", "publisher-1")
    seed = os.getenv("SEED")

    events = build_events(total_events, duplicate_rate, source, seed=seed)
    batches = list(chunks(events, batch_size))
    started = time.perf_counter()
    queued = 0

    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    timeout = httpx.Timeout(30.0)
    semaphore = asyncio.Semaphore(concurrency)

    async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
        async def guarded_post(batch_number: int, batch: list[dict[str, Any]]) -> int:
            async with semaphore:
                return await post_batch(client, target_url, batch, batch_number, retries)

        tasks = [
            asyncio.create_task(guarded_post(number, batch))
            for number, batch in enumerate(batches, start=1)
        ]
        for task in asyncio.as_completed(tasks):
            queued += await task

    elapsed = time.perf_counter() - started
    rate = queued / elapsed if elapsed else 0.0
    expected_unique = len({(event["topic"], event["event_id"]) for event in events})
    expected_duplicates = len(events) - expected_unique

    print("publisher finished")
    print(f"target_url={target_url}")
    print(f"seed={seed or '<random>'}")
    print(f"sent={len(events)} queued={queued}")
    print(f"expected_unique={expected_unique} expected_duplicates={expected_duplicates}")
    print(f"elapsed_seconds={elapsed:.3f} throughput_events_per_second={rate:.2f}")


if __name__ == "__main__":
    asyncio.run(run())
