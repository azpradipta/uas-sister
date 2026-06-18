from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    func,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from .models import EventIn, ProcessResult


metadata = MetaData()

json_payload = JSON().with_variant(JSONB, "postgresql")

processed_events = Table(
    "processed_events",
    metadata,
    Column(
        "id",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    Column("topic", String(128), nullable=False),
    Column("event_id", String(160), nullable=False),
    Column("event_timestamp", DateTime(timezone=True), nullable=False),
    Column("source", String(128), nullable=False),
    Column("payload", json_payload, nullable=False),
    Column("processed_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("topic", "event_id", name="uq_processed_topic_event_id"),
)

stats_counters = Table(
    "stats_counters",
    metadata,
    Column("name", String(64), primary_key=True),
    Column("value", BigInteger, nullable=False, default=0),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column(
        "id",
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        autoincrement=True,
    ),
    Column("topic", String(128), nullable=False),
    Column("event_id", String(160), nullable=False),
    Column("status", String(32), nullable=False),
    Column("detail", String(255), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)


COUNTERS = ("received", "unique_processed", "duplicate_dropped")


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.removeprefix("postgresql://")
    if url.startswith("sqlite:///"):
        return "sqlite+aiosqlite:///" + url.removeprefix("sqlite:///")
    return url


class EventStore:
    def __init__(self, database_url: str):
        self.database_url = normalize_database_url(database_url)
        self.backend = self.database_url.split(":", 1)[0].split("+", 1)[0]
        kwargs: dict[str, Any] = {"pool_pre_ping": True}
        if self.backend == "postgresql":
            kwargs["isolation_level"] = "READ COMMITTED"
        if self.backend == "sqlite":
            kwargs["connect_args"] = {"timeout": 30}
        self.engine: AsyncEngine = create_async_engine(self.database_url, **kwargs)

    async def init(self) -> None:
        async with self.engine.begin() as conn:
            if self.backend == "sqlite":
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA busy_timeout=30000"))
            await conn.run_sync(metadata.create_all)
            for name in COUNTERS:
                stmt = self._insert_ignore(stats_counters, {"name": name, "value": 0}, ["name"])
                await conn.execute(stmt)

    async def close(self) -> None:
        await self.engine.dispose()

    async def health(self) -> bool:
        async with self.engine.connect() as conn:
            await conn.execute(select(1))
        return True

    async def process_event(self, event: EventIn) -> ProcessResult:
        now = datetime.now(timezone.utc)
        async with self.engine.begin() as conn:
            await conn.execute(
                update(stats_counters)
                .where(stats_counters.c.name == "received")
                .values(value=stats_counters.c.value + 1)
            )

            stmt = self._insert_ignore(
                processed_events,
                {
                    "topic": event.topic,
                    "event_id": event.event_id,
                    "event_timestamp": event.timestamp,
                    "source": event.source,
                    "payload": event.payload,
                    "processed_at": now,
                },
                ["topic", "event_id"],
            ).returning(processed_events.c.id)

            result = await conn.execute(stmt)
            inserted = result.scalar_one_or_none() is not None
            counter = "unique_processed" if inserted else "duplicate_dropped"
            status = "processed" if inserted else "duplicate"
            detail = (
                "event inserted atomically"
                if inserted
                else "duplicate ignored by unique constraint"
            )

            await conn.execute(
                update(stats_counters)
                .where(stats_counters.c.name == counter)
                .values(value=stats_counters.c.value + 1)
            )
            await conn.execute(
                insert(audit_log).values(
                    topic=event.topic,
                    event_id=event.event_id,
                    status=status,
                    detail=detail,
                    created_at=now,
                )
            )
        return ProcessResult(inserted=inserted, status=status)

    async def list_events(
        self,
        topic: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = select(
            processed_events.c.id,
            processed_events.c.topic,
            processed_events.c.event_id,
            processed_events.c.event_timestamp,
            processed_events.c.source,
            processed_events.c.payload,
            processed_events.c.processed_at,
        ).order_by(processed_events.c.event_timestamp.asc(), processed_events.c.id.asc())
        if topic:
            query = query.where(processed_events.c.topic == topic)
        query = query.limit(limit).offset(offset)

        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()

        return [
            {
                "id": row["id"],
                "logical_seq": row["id"],
                "topic": row["topic"],
                "event_id": row["event_id"],
                "timestamp": row["event_timestamp"],
                "source": row["source"],
                "payload": row["payload"],
                "processed_at": row["processed_at"],
            }
            for row in rows
        ]

    async def stats(self, uptime_seconds: float) -> dict[str, Any]:
        async with self.engine.connect() as conn:
            counter_rows = (
                await conn.execute(select(stats_counters.c.name, stats_counters.c.value))
            ).all()
            topic_rows = (
                await conn.execute(
                    select(processed_events.c.topic, func.count().label("count"))
                    .group_by(processed_events.c.topic)
                    .order_by(processed_events.c.topic.asc())
                )
            ).all()

        counters = {name: int(value) for name, value in counter_rows}
        received = counters.get("received", 0)
        duplicate_dropped = counters.get("duplicate_dropped", 0)
        duplicate_rate = duplicate_dropped / received if received else 0.0
        return {
            "received": received,
            "unique_processed": counters.get("unique_processed", 0),
            "duplicate_dropped": duplicate_dropped,
            "duplicate_rate": round(duplicate_rate, 4),
            "topics": {topic: int(count) for topic, count in topic_rows},
            "uptime_seconds": round(uptime_seconds, 3),
        }

    async def list_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        query = (
            select(
                audit_log.c.id,
                audit_log.c.topic,
                audit_log.c.event_id,
                audit_log.c.status,
                audit_log.c.detail,
                audit_log.c.created_at,
            )
            .order_by(audit_log.c.id.desc())
            .limit(limit)
        )
        async with self.engine.connect() as conn:
            rows = (await conn.execute(query)).mappings().all()
        return [dict(row) for row in rows]

    def _insert_ignore(
        self,
        table: Table,
        values: dict[str, Any],
        index_elements: list[str],
    ):
        if self.backend == "postgresql":
            return pg_insert(table).values(**values).on_conflict_do_nothing(
                index_elements=index_elements
            )
        if self.backend == "sqlite":
            return sqlite_insert(table).values(**values).on_conflict_do_nothing(
                index_elements=index_elements
            )
        return insert(table).values(**values)
