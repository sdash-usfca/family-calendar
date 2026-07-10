"""Fetch + parse iCal (.ics) feeds from Google / iCloud / anywhere, expanding
recurring events into concrete occurrences within the agenda window.

Recurring events (weekly standups, birthdays) are the tricky part of any calendar
app — `recurring_ical_events` expands RRULEs for us so we don't have to."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import List
from zoneinfo import ZoneInfo

import icalendar
import recurring_ical_events
import requests

from ..config import CalendarSource
from ..model import Event


def fetch_events(sources: List[CalendarSource], now: datetime, days: int, tzname: str) -> List[Event]:
    tz = ZoneInfo(tzname)
    horizon = now + timedelta(days=days)
    out: List[Event] = []
    for src in sources:
        try:
            resp = requests.get(src.ics, timeout=15)
            resp.raise_for_status()
            cal = icalendar.Calendar.from_ical(resp.text)
            for comp in recurring_ical_events.of(cal).between(now, horizon):
                out.append(_to_event(comp, src, tz))
        except Exception as exc:  # noqa: BLE001 — one bad feed shouldn't blank the board
            print(f"calboard: failed to load calendar {src.name!r}: {exc}")
    out.sort(key=lambda e: e.start)
    return out


def _to_event(comp, src: CalendarSource, tz: ZoneInfo) -> Event:
    dtstart = comp.get("DTSTART").dt
    dtend_prop = comp.get("DTEND")
    all_day = isinstance(dtstart, date) and not isinstance(dtstart, datetime)

    def norm(d) -> datetime:
        if isinstance(d, datetime):
            return d.astimezone(tz) if d.tzinfo else d.replace(tzinfo=tz)
        return datetime(d.year, d.month, d.day, tzinfo=tz)  # all-day date -> local midnight

    start = norm(dtstart)
    end = norm(dtend_prop.dt) if dtend_prop is not None else start + timedelta(hours=1)
    title = str(comp.get("SUMMARY", "(no title)"))
    location = str(comp.get("LOCATION", "") or "")
    return Event(title, start, end, all_day, src.name, src.color, location)
