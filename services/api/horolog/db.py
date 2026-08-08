"""Persistence.

Three tables. Plans are not one of them in the usual sense: a plan is derived,
and deriving it costs single-digit milliseconds, so it is recomputed rather than
stored as rows. The previous plan *is* kept — as one JSON blob — because the
placement engine needs it to stay stable across re-solves.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from horolog.domain.intent import Intent
from horolog.domain.plan import Plan
from horolog.settings import settings


class Base(DeclarativeBase):
    pass


class IntentRow(Base):
    __tablename__ = "intents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    """The full validated Intent. Stored whole rather than shredded into columns:
    the Pydantic model is the schema of record, and a second copy of it in DDL
    would be a second thing to keep in sync."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    def to_domain(self) -> Intent:
        return Intent.model_validate(self.payload)


class BusyRow(Base):
    __tablename__ = "busy_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    """Which provider supplied it: `manual`, `caldav`, `google`."""
    label: Mapped[str] = mapped_column(String(256), default="")
    start_slot: Mapped[int] = mapped_column(Integer, index=True)
    end_slot: Mapped[int] = mapped_column(Integer)


class PlanRow(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payload: Mapped[str] = mapped_column(Text)
    saved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


_engine = create_async_engine(settings().database_url, future=True)
_session_factory = async_sessionmaker(_engine, expire_on_commit=False)

LATEST_PLAN_ID = 1
"""Single-user deployment: one current plan. Becomes a user foreign key when
multi-tenancy arrives; nothing else in the schema has to change."""


async def init_db() -> None:
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def session() -> AsyncIterator[AsyncSession]:
    async with _session_factory() as db:
        yield db


async def load_intents(db: AsyncSession) -> list[Intent]:
    rows = (await db.execute(select(IntentRow))).scalars().all()
    return [row.to_domain() for row in rows]


async def load_previous_plan(db: AsyncSession) -> Plan | None:
    row = await db.get(PlanRow, LATEST_PLAN_ID)
    return Plan.model_validate(json.loads(row.payload)) if row else None


async def save_plan(db: AsyncSession, plan: Plan) -> None:
    row = await db.get(PlanRow, LATEST_PLAN_ID)
    if row is None:
        db.add(PlanRow(id=LATEST_PLAN_ID, payload=plan.model_dump_json()))
    else:
        row.payload = plan.model_dump_json()
        row.saved_at = datetime.now(UTC)
    await db.commit()
