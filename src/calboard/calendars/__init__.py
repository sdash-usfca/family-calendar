"""Calendar sources: turn config into a sorted list of upcoming Events."""
from __future__ import annotations

from datetime import datetime
from typing import List, Tuple

from ..config import Config
from ..model import Event
from .mock import mock_events


def get_events(config: Config, now: datetime) -> List[Event]:
    """Upcoming events for the agenda window. Falls back to sample data in demo
    mode (or if no calendars are configured) so it runs with zero setup."""
    if config.demo or not config.calendars:
        return mock_events(now, config.agenda_days)
    # Imported lazily so the demo/laptop path doesn't need the .ics libraries.
    from .ics_source import fetch_events
    return fetch_events(config.calendars, now, config.agenda_days, config.timezone)
