"""Sample events so the whole board runs on a laptop with no calendars set up.

Events are placed relative to "now" so the What's-Next panel always has something
to show (including a doctor's appointment a few days out — the headline use case)."""
from __future__ import annotations

from datetime import timedelta
from typing import List

from ..model import Event

_PERSONAL = "#4c8dff"   # blue
_FAMILY = "#22c55e"     # green
_BILLS = "#f59e0b"      # amber


def mock_events(now, days: int) -> List[Event]:
    base = now.replace(minute=0, second=0, microsecond=0)

    def mk(title, day, hour, dur_h, cal, color, all_day=False, loc=""):
        start = (base + timedelta(days=day)).replace(hour=hour)
        end = start + timedelta(hours=dur_h)
        return Event(title, start, end, all_day, cal, color, loc)

    events = [
        mk("Team standup", 0, 9, 1, "Personal", _PERSONAL),
        mk("Lunch with Sam", 0, 12, 1, "Personal", _PERSONAL, loc="Cafe Verona"),
        mk("Soccer practice", 1, 17, 2, "Family", _FAMILY, loc="City Park"),
        mk("Grocery run", 2, 18, 1, "Family", _FAMILY),
        mk("🩺 Dr. Lee — annual checkup", 3, 14, 1, "Personal", _PERSONAL, loc="Downtown Clinic"),
        mk("Movie night", 5, 20, 2, "Family", _FAMILY),
        mk("🦷 Dentist cleaning", 6, 10, 1, "Personal", _PERSONAL, loc="Bright Smiles Dental"),
        mk("Pay rent", 9, 0, 0, "Bills", _BILLS, all_day=True),
        mk("Mom's birthday", 11, 0, 0, "Family", _FAMILY, all_day=True),
    ]
    horizon = now + timedelta(days=days)
    upcoming = [e for e in events if e.end >= now and e.start <= horizon]
    upcoming.sort(key=lambda e: e.start)
    return upcoming
