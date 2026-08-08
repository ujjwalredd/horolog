"""Analytics figures and calendar mirroring."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from horolog.analytics import analyse
from horolog.domain.events import BusyInterval
from horolog.domain.intent import DailyWindow, Intent, IntentKind, Priority
from horolog.domain.time import SLOTS_PER_DAY, SLOTS_PER_HOUR
from horolog.providers import SyncError, parse_ics, to_ics
from horolog.solver.solve import solve

TZ = ZoneInfo("UTC")
WEEK = 7 * SLOTS_PER_DAY


def at(day: int, hour: int) -> int:
    return day * SLOTS_PER_DAY + hour * SLOTS_PER_HOUR


def intent(ident: str, minutes: int, kind: IntentKind = IntentKind.TASK, **kw: object) -> Intent:
    return Intent(
        id=ident,
        kind=kind,
        title=ident,
        priority=kw.pop("priority", Priority.P3),  # type: ignore[arg-type]
        minutes_per_period=minutes,
        min_chunk_minutes=kw.pop("min_chunk", 60),  # type: ignore[arg-type]
        max_chunk_minutes=kw.pop("max_chunk", 120),  # type: ignore[arg-type]
        daily_windows=[DailyWindow(start_min=9 * 60, end_min=17 * 60)],
        **kw,  # type: ignore[arg-type]
    )


# --------------------------------------------------------------------- analytics


def test_analytics_separates_meeting_load_from_scheduled_work() -> None:
    intents = [intent("deep", 240, IntentKind.FOCUS, min_chunk=120, max_chunk=120)]
    busy = [
        BusyInterval(source_id=f"m{d}", start_slot=at(d, 9), end_slot=at(d, 11), label="Sync")
        for d in range(5)
    ]
    plan = solve(intents, busy, WEEK)

    report = analyse(plan, intents, busy, 7, 9 * 60, 17 * 60)

    assert report.meeting_minutes == 5 * 120
    assert report.scheduled_minutes == 240
    # 10h of meetings against 7 days x 8h of window.
    assert 0.15 < report.meeting_load < 0.20
    assert report.by_kind[0].label == "focus"


def test_fragmentation_reports_mean_block_length() -> None:
    """Two hours delivered as one block and as four half-hours are the same
    total and very different days. This is the number that tells them apart."""
    chunky = [intent("a", 120, min_chunk=120, max_chunk=120)]
    diced = [intent("b", 120, min_chunk=30, max_chunk=30)]

    whole = analyse(solve(chunky, [], WEEK), chunky, [], 7, 9 * 60, 17 * 60)
    split = analyse(solve(diced, [], WEEK), diced, [], 7, 9 * 60, 17 * 60)

    assert whole.fragmentation == 120
    assert split.fragmentation == 30
    assert whole.focus_minutes == 120
    assert split.focus_minutes == 0, "half-hour slivers are not focus time"


def test_longest_free_run_shrinks_as_the_day_is_diced() -> None:
    """A day can be mostly empty and still have no usable stretch in it."""
    clear = analyse(solve([], [], WEEK), [], [], 7, 9 * 60, 17 * 60)
    assert clear.days[0].longest_free_run_minutes == 8 * 60

    diced = [
        BusyInterval(source_id=f"m{h}", start_slot=at(0, h), end_slot=at(0, h) + 2, label="ping")
        for h in (10, 12, 14)
    ]
    chopped = analyse(solve([], diced, WEEK), [], diced, 7, 9 * 60, 17 * 60)
    assert chopped.days[0].longest_free_run_minutes < 8 * 60
    assert chopped.days[0].meeting_minutes == 90


def test_after_hours_counts_only_meetings_outside_the_workday() -> None:
    busy = [
        BusyInterval(source_id="late", start_slot=at(0, 20), end_slot=at(0, 21), label="Late call"),
        BusyInterval(source_id="ok", start_slot=at(0, 10), end_slot=at(0, 11), label="Standup"),
    ]
    report = analyse(solve([], busy, WEEK), [], busy, 7, 9 * 60, 17 * 60)
    assert report.after_hours_minutes == 60


def test_analytics_reports_unmet_demand() -> None:
    intents = [intent(f"t{i}", 480, max_chunk=480) for i in range(30)]
    plan = solve(intents, [], WEEK)
    report = analyse(plan, intents, [], 7, 9 * 60, 17 * 60)
    assert report.unmet_minutes > 0


# ------------------------------------------------------------------ ics parsing


def _calendar(body: str) -> str:
    return f"BEGIN:VCALENDAR\r\nVERSION:2.0\r\nPRODID:-//t//EN\r\n{body}\r\nEND:VCALENDAR"


def test_ics_expands_a_recurring_meeting() -> None:
    """A weekly standup is one VEVENT and many occupied hours. Treating it as
    one event would let the scheduler book straight through every instance
    after the first."""
    origin = datetime(2026, 3, 2, tzinfo=TZ)
    ics = _calendar(
        "BEGIN:VEVENT\r\nUID:s@t\r\nDTSTART:20260302T090000Z\r\nDTEND:20260302T093000Z\r\n"
        "RRULE:FREQ=DAILY;COUNT=5\r\nSUMMARY:Standup\r\nEND:VEVENT"
    )
    assert len(parse_ics(ics, origin, 14, TZ)) == 5


def test_ics_honours_transparent_and_cancelled() -> None:
    """TRANSP:TRANSPARENT means "I am free during this" — holidays, focus
    placeholders, other tools' blocks. Mirroring them would import a to-do
    list rather than a calendar."""
    origin = datetime(2026, 3, 2, tzinfo=TZ)
    ics = _calendar(
        "BEGIN:VEVENT\r\nUID:a@t\r\nDTSTART:20260302T090000Z\r\nDTEND:20260302T100000Z\r\n"
        "TRANSP:TRANSPARENT\r\nSUMMARY:Free\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:b@t\r\nDTSTART:20260302T110000Z\r\nDTEND:20260302T120000Z\r\n"
        "STATUS:CANCELLED\r\nSUMMARY:Called off\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:c@t\r\nDTSTART:20260302T140000Z\r\nDTEND:20260302T150000Z\r\n"
        "SUMMARY:Real\r\nEND:VEVENT"
    )
    labels = [i.label for i in parse_ics(ics, origin, 14, TZ)]
    assert labels == ["Real"]


def test_ics_handles_all_day_events() -> None:
    """All-day events arrive as `date`, not `datetime` — comparing the two
    raises, so they have to be normalised rather than assumed."""
    origin = datetime(2026, 3, 2, tzinfo=TZ)
    ics = _calendar(
        "BEGIN:VEVENT\r\nUID:h@t\r\nDTSTART;VALUE=DATE:20260303\r\n"
        "DTEND;VALUE=DATE:20260304\r\nSUMMARY:Public holiday\r\nEND:VEVENT"
    )
    out = parse_ics(ics, origin, 14, TZ)
    assert len(out) == 1
    assert out[0].end_slot - out[0].start_slot == SLOTS_PER_DAY


def test_ics_clips_events_to_the_horizon() -> None:
    origin = datetime(2026, 3, 2, tzinfo=TZ)
    ics = _calendar(
        "BEGIN:VEVENT\r\nUID:past@t\r\nDTSTART:20260201T090000Z\r\nDTEND:20260201T100000Z\r\n"
        "SUMMARY:Last month\r\nEND:VEVENT\r\n"
        "BEGIN:VEVENT\r\nUID:far@t\r\nDTSTART:20270101T090000Z\r\nDTEND:20270101T100000Z\r\n"
        "SUMMARY:Next year\r\nEND:VEVENT"
    )
    assert parse_ics(ics, origin, 14, TZ) == []


def test_malformed_ics_raises_a_readable_error() -> None:
    with pytest.raises(SyncError, match="could not parse"):
        parse_ics("this is not a calendar", datetime(2026, 3, 2, tzinfo=TZ), 14, TZ)


def test_export_escapes_special_characters() -> None:
    """An unescaped comma silently truncates SUMMARY in most clients."""
    start = datetime(2026, 3, 2, 9, tzinfo=TZ)
    body = to_ics([("Deep work, focus; phase 1", start, start + timedelta(hours=2))])
    assert "SUMMARY:Deep work\\, focus\\; phase 1" in body
    assert body.startswith("BEGIN:VCALENDAR")
    assert body.rstrip().endswith("END:VCALENDAR")


def test_export_round_trips_through_the_parser() -> None:
    origin = datetime(2026, 3, 2, tzinfo=TZ)
    start = origin + timedelta(hours=9)
    body = to_ics([("Deep work", start, start + timedelta(hours=2))])

    back = parse_ics(body, origin, 14, TZ)
    assert len(back) == 1
    assert back[0].label == "Deep work"
    assert back[0].end_slot - back[0].start_slot == 2 * SLOTS_PER_HOUR
