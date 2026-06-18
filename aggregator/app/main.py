from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query

from .config import Settings, get_settings
from .consumer import ConsumerService
from .database import EventStore
from .models import EventIn, EventOut, PublishResponse, StatsResponse
from .queue import RedisEventQueue

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


def create_app(
    store: EventStore | None = None,
    queue: RedisEventQueue | None = None,
    settings: Settings | None = None,
    start_workers: bool = True,
) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.started_monotonic = time.monotonic()
        app.state.store = store or EventStore(settings.database_url)
        app.state.queue = queue or RedisEventQueue(
            settings.redis_url,
            stream=settings.redis_stream,
            group=settings.redis_group,
        )
        app.state.consumer = None

        await app.state.store.init()
        await app.state.queue.connect()

        if start_workers:
            app.state.consumer = ConsumerService(
                app.state.store,
                app.state.queue,
                worker_count=settings.worker_count,
                batch_size=settings.worker_batch_size,
                stale_message_ms=settings.stale_message_ms,
            )
            await app.state.consumer.start()

        try:
            yield
        finally:
            if app.state.consumer is not None:
                await app.state.consumer.stop()
            await app.state.queue.close()
            await app.state.store.close()

    app = FastAPI(
        title="Pub-Sub Log Aggregator",
        version="1.0.0",
        summary="Distributed log aggregator with persistent idempotency and deduplication.",
        lifespan=lifespan,
    )

    @app.post("/publish", response_model=PublishResponse)
    async def publish(events: EventIn | list[EventIn]) -> PublishResponse:
        batch = events if isinstance(events, list) else [events]
        if not batch:
            raise HTTPException(status_code=400, detail="batch must contain at least one event")
        queued = await app.state.queue.publish_many(batch)
        return PublishResponse(accepted=len(batch), queued=queued)

    @app.get("/events", response_model=list[EventOut])
    async def get_events(
        topic: str | None = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> list[dict]:
        return await app.state.store.list_events(topic=topic, limit=limit, offset=offset)

    @app.get("/stats", response_model=StatsResponse)
    async def get_stats() -> dict:
        uptime = time.monotonic() - app.state.started_monotonic
        return await app.state.store.stats(uptime)

    @app.get("/audit")
    async def get_audit(limit: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict]:
        return await app.state.store.list_audit(limit=limit)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        await app.state.store.health()
        await app.state.queue.health()
        return {"status": "ready"}

    return app


app = create_app()
