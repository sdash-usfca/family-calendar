"""The one shared data type: a calendar Event."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    title: str
    start: datetime
    end: datetime
    all_day: bool
    calendar: str
    color: str
    location: str = ""

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "all_day": self.all_day,
            "calendar": self.calendar,
            "color": self.color,
            "location": self.location,
        }
