from __future__ import annotations

import asyncio
import logging
import uuid

from .database import EventStore
from .queue import RedisEventQueue

logger = logging.getLogger(__name__)


class ConsumerService:
    def __init__(
        self,
        store: EventStore,
        queue: RedisEventQueue,
        worker_count: int,
        batch_size: int,
        stale_message_ms: int,
    ):
        self.store = store
        self.queue = queue
        self.worker_count = worker_count
        self.batch_size = batch_size
        self.stale_message_ms = stale_message_ms
        self._stop = asyncio.Event()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._stop.clear()
        for index in range(self.worker_count):
            task = asyncio.create_task(self._worker(index), name=f"consumer-{index}")
            self._tasks.append(task)
        logger.info("started %s consumer workers", self.worker_count)

    async def stop(self) -> None:
        self._stop.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _worker(self, index: int) -> None:
        consumer_name = f"worker-{index}-{uuid.uuid4().hex[:8]}"
        backoff = 0.25
        while not self._stop.is_set():
            try:
                claimed = await self.queue.claim_stale(
                    consumer_name,
                    min_idle_ms=self.stale_message_ms,
                    count=self.batch_size,
                )
                if claimed:
                    await self._process_messages(claimed)

                messages = await self.queue.read_new(
                    consumer_name,
                    count=self.batch_size,
                    block_ms=1000,
                )
                if messages:
                    await self._process_messages(messages)
                backoff = 0.25
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("consumer worker failed; retrying")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 5.0)

    async def _process_messages(self, messages) -> None:
        for message_id, event in messages:
            result = await self.store.process_event(event)
            if result.inserted:
                logger.info("processed topic=%s event_id=%s", event.topic, event.event_id)
            else:
                logger.info("duplicate dropped topic=%s event_id=%s", event.topic, event.event_id)
            await self.queue.ack(message_id)
