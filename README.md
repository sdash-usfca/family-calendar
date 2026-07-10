# 🗓️ family-calendar

A colorful **wall calendar / family command center** for a Raspberry Pi + a spare
monitor — a DIY take on the [Skylight Calendar](https://www.skylightframe.com/).
It aggregates your Google + iCloud calendars, leads with a big **"What's Next"**
panel (so you *never miss an appointment*), and runs full-screen as a kiosk.

Built as a custom web app (Flask + vanilla JS) — the same clean, layered pattern
as its sibling [air-quality-monitor](../air-quality-monitor), so it's easy to
understand and to restyle exactly how you want.

> 🎯 **Design goal:** stop missing doctor's appointments. The board leads with
> upcoming events + countdowns, and (planned) **speaks reminders to a Google Nest**.

## Features

- 📅 **Aggregated calendar** — Google + iCloud (and any `.ics` feed), color-coded per calendar, **no OAuth** (just private iCal URLs). Recurring events expanded correctly.
- ⏰ **"What's Next"** — your next appointments as big color cards with live countdowns ("in 3 days").
- 🕐 Big clock + date, week agenda grouped by day.
- 🖥️ Runs as a Chromium **kiosk** on the wall; reachable from any phone on your LAN.
- 🧪 **Demo mode** — sample events out of the box, so it runs on a laptop with zero setup.

### Planned (layered in over time)
Nest **voice reminders** for appointments · weather · quote of the day ·
recipe of the day (TheMealDB) · Spotify now-playing · photo slideshow · chores.

## Quickstart (laptop, no setup)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml     # demo: true — sample events
calboard-web                           # → http://localhost:8000
```

## Add your real calendars

Edit `config.yaml`, set `demo: false`, and paste your private iCal URLs:
- **Google Calendar** → Settings → *your calendar* → **"Secret address in iCal format"**
- **iCloud** → share a calendar → make it **Public** → copy the link → change `webcal://` to `https://`

Give each a `name` and `color`.

## On the Raspberry Pi

Install the venv + deps, run `calboard-web` as a service, and point Chromium
(kiosk) at `http://localhost:8000`. (Deploy notes coming as we set it up.)

## License

MIT
