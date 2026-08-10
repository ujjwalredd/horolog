"""A malformed database URL should fail with an actionable message, not a
bare SQLAlchemy/asyncpg traceback."""

from __future__ import annotations

import os

import pytest

from horolog import db
from horolog.settings import settings


@pytest.mark.asyncio
async def test_init_db_reports_an_actionable_error_for_a_bad_url() -> None:
    old = os.environ.get("HOROLOG_DATABASE_URL")
    os.environ["HOROLOG_DATABASE_URL"] = "postgresql+asyncpg://bad:bad@127.0.0.1:1/nope"
    settings.cache_clear()
    db._engine.cache_clear()
    db._session_factory.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="HOROLOG_DATABASE_URL"):
            await db.init_db()
    finally:
        if old is not None:
            os.environ["HOROLOG_DATABASE_URL"] = old
        else:
            del os.environ["HOROLOG_DATABASE_URL"]
        settings.cache_clear()
        db._engine.cache_clear()
        db._session_factory.cache_clear()
