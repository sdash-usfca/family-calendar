"""Configuration loaded from config.yaml (see config.example.yaml)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

import yaml


@dataclass
class CalendarSource:
    name: str
    color: str = "#4c8dff"
    ics: str = ""


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 8000


@dataclass
class LocationConfig:
    name: str = "Auburn, WA"
    lat: float = 47.3073
    lon: float = -122.2285


@dataclass
class Chore:
    person: str
    task: str
    color: str = "#4c8dff"


@dataclass
class Config:
    demo: bool = True
    timezone: str = "America/Los_Angeles"
    calendars: List[CalendarSource] = field(default_factory=list)
    whats_next_count: int = 6
    agenda_days: int = 14
    board_days: int = 5          # how many day-columns the week board shows
    location: LocationConfig = field(default_factory=LocationConfig)
    chores: List[Chore] = field(default_factory=list)
    meal_tonight: str = ""
    web: WebConfig = field(default_factory=WebConfig)


def load_config(path: Optional[str] = None) -> Config:
    path = path or os.environ.get("CALBOARD_CONFIG", "config.yaml")
    data = {}
    if os.path.exists(path):
        with open(path) as f:
            data = yaml.safe_load(f) or {}
    calendars = [CalendarSource(**c) for c in data.get("calendars", []) or []]
    web = WebConfig(**(data.get("web", {}) or {}))
    location = LocationConfig(**(data.get("location", {}) or {}))
    chores = [Chore(**c) for c in data.get("chores", []) or []]
    return Config(
        demo=data.get("demo", True),
        timezone=data.get("timezone", "America/Los_Angeles"),
        calendars=calendars,
        whats_next_count=data.get("whats_next_count", 6),
        agenda_days=data.get("agenda_days", 14),
        board_days=data.get("board_days", 5),
        location=location,
        chores=chores,
        meal_tonight=data.get("meal_tonight", ""),
        web=web,
    )
