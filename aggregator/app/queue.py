from __future__ import annotations

import json
import logging
from typing import Iterable

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from .models import EventIn

logger = logging.getLogger(__name__)


class RedisEventQueue:
    def __init__(
        self,
        redis_url: str,
        stream: str = "log-events",
        group: str = "aggregator-workers",
        maxlen: int = 200000,
    ):
        self.redis_url = redis_url
        self.stream = stream
        self.group = group
        self.maxlen = maxlen
        self.redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    async def connect(self) -> None:
        await self.redis.ping()
        try:
            await self.redis.xgroup_create(self.stream, self.group, id="0", mkstream=True)
            logger.info("created redis consumer group stream=%s group=%s", self.stream, self.group)
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def close(self) -> None:
        await self.redis.aclose()

    async def health(self) -> bool:
        return bool(await self.redis.ping())

    async def publish_many(self, events: Iterable[EventIn]) -> int:
        pipe = self.redis.pipeline(transaction=False)
        count = 0
        for event in events:
            payload = json.dumps(event.to_queue_payload(), separators=(",", ":"))
            pipe.xadd(
                self.stream,
                {"event": payload},
                maxlen=self.maxlen,
                approximate=True,
            )
            count += 1
        if count:
            await pipe.execute()
        return count

    async def read_new(
        self,
        consumer_name: str,
        count: int,
        block_ms: int,
    ) -> list[tuple[str, EventIn]]:
        response = await self.redis.xreadgroup(
            self.group,
            consumer_name,
            {self.stream: ">"},
            count=count,
            block=block_ms,
        )
        return self._parse_stream_response(response)

    async def claim_stale(
        self,
        consumer_name: str,
        min_idle_ms: int,
        count: int,
    ) -> list[tuple[str, EventIn]]:
        result = await self.redis.xautoclaim(
            self.stream,
            self.group,
            consumer_name,
            min_idle_time=min_idle_ms,
            start_id="0-0",
            count=count,
        )
        messages = result[1] if len(result) > 1 else []
        return self._parse_message_list(messages)

    async def ack(self, message_id: str) -> None:
        await self.redis.xack(self.stream, self.group, message_id)

    def _parse_stream_response(self, response) -> list[tuple[str, EventIn]]:
        parsed: list[tuple[str, EventIn]] = []
        for _stream_name, messages in response:
            parsed.extend(self._parse_message_list(messages))
        return parsed

    def _parse_message_list(self, messages) -> list[tuple[str, EventIn]]:
        parsed: list[tuple[str, EventIn]] = []
        for message_id, fields in messages:
            raw = fields.get("event")
            if not raw:
                logger.warning("redis message without event field id=%s", message_id)
                continue
            parsed.append((message_id, EventIn.model_validate_json(raw)))
        return parsed
