"""Runtime configuration. Validated at import — a missing or malformed value
fails the process on boot rather than at the first request that needs it."""

from __future__ import annotations

import os
from contextlib import suppress
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def host_timezone() -> str:
    """The machine's IANA zone, falling back to UTC.

    Defaulting to UTC instead looks harmless and is not: the workday window is
    interpreted in the server's zone while the browser renders in the viewer's,
    so a 9-to-5 goal silently lands at 5am for anyone east or west of Greenwich.
    Since this is a self-hosted, single-user app, the host's own zone is very
    nearly always the right answer — and `HOROLOG_TIMEZONE` overrides it.

    Read from `$TZ` when set, otherwise from the `/etc/localtime` symlink, which
    is how the zone is recorded on macOS and every mainstream Linux. A whole
    dependency (`tzlocal`) for these eight lines is not worth carrying.
    """
    env = os.environ.get("TZ")
    if env:
        with suppress(ZoneInfoNotFoundError, ValueError):
            ZoneInfo(env)
            return env
    with suppress(OSError, ValueError):
        link = Path("/etc/localtime").resolve()
        parts = link.parts
        if "zoneinfo" in parts:
            candidate = "/".join(parts[parts.index("zoneinfo") + 1 :])
            with suppress(ZoneInfoNotFoundError, ValueError):
                ZoneInfo(candidate)
                return candidate
    return "UTC"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HOROLOG_", env_file=".env", extra="ignore")

    database_url: str = "sqlite+aiosqlite:///./horolog.db"
    """Any SQLAlchemy async URL. SQLite for a single-user self-host, Postgres
    (`postgresql+asyncpg://...`) when more than one process needs the data."""

    timezone: str = Field(default_factory=lambda: host_timezone())
    horizon_days: int = Field(default=21, ge=1, le=84)

    workday_start_min: int = Field(default=9 * 60, ge=0, le=24 * 60)
    workday_end_min: int = Field(default=17 * 60, ge=0, le=24 * 60)

    auto_buffer_enabled: bool = Field(default=False)
    """Hold recovery time after every substantial meeting.

    Off by default: it is capacity that stops being schedulable, so switching it
    on legitimately makes a full week start reporting unmet demand."""

    auto_buffer_minutes: int = Field(default=15, ge=5, le=60)

    llm_provider: Literal["openai", "anthropic"] = "openai"
    """`openai` covers every OpenAI-compatible server — Ollama, vLLM, SGLang,
    llama.cpp, OpenAI itself. `anthropic` uses the official Claude SDK, which
    spells structured output differently and needs its own path."""

    llm_base_url: str = "http://localhost:11434/v1"
    """Ignored when llm_provider is `anthropic`."""

    llm_model: str = "qwen3:8b"
    """Local default. Use e.g. `claude-opus-5` for Anthropic, `gpt-4.1` for OpenAI."""

    llm_api_key: str = ""
    llm_timeout_s: float = 60.0

    cors_origins: list[str] = ["http://localhost:3000"]

    public_api_url: str = "http://localhost:8000"
    """Where the browser can reach this API directly — not through the Next.js
    proxy. Only used to build OAuth redirect URLs: the provider's consent
    screen redirects the browser straight back here, bypassing the frontend
    entirely, so this has to be a real address rather than an internal Docker
    hostname. The default matches `docker-compose`'s published port; set it to
    your real domain for anything beyond one machine."""

    public_web_url: str = "http://localhost:3000"
    """Where the browser reaches the web app, for the same reason: once an
    OAuth round trip finishes here on the API, the user has to be sent back to
    a page that exists."""

    google_client_id: str = ""
    google_client_secret: str = ""
    outlook_client_id: str = ""
    outlook_client_secret: str = ""
    linear_client_id: str = ""
    linear_client_secret: str = ""
    todoist_client_id: str = ""
    todoist_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    @field_validator("timezone")
    @classmethod
    def _known_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone {value!r}") from exc
        return value

    @field_validator("workday_end_min")
    @classmethod
    def _workday_ordered(cls, value: int, info: object) -> int:
        start = getattr(info, "data", {}).get("workday_start_min")
        if start is not None and value <= start:
            raise ValueError(f"workday_end_min {value} must exceed workday_start_min {start}")
        return value

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def settings() -> Settings:
    return Settings()
