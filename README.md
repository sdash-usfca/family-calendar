# 🗓️ Family Wall

A wall-mounted **family command center** built on a Raspberry Pi and a spare
monitor — a DIY, fully-owned alternative to the [Skylight Calendar](https://www.skylightframe.com/).

It runs full-screen as a kiosk on a portrait-mounted display and pulls the
household together in one place: shared **calendars**, **grocery / to-do / notes**
lists that sync to everyone's phone, **weekly meal planning**, a synced-lyric
**music screen**, a **photo gallery**, **news**, **YouTube**, and **countdowns**
to the things everyone's looking forward to — all steerable from a phone, and
built to quietly keep itself running.

Built as a single web app (Flask + vanilla JS, no build step) so every screen is
easy to read, tweak, and restyle.

> 🎯 **Why:** stop missing appointments, stop the "what's for dinner / did we run
> out of milk / whose turn is it" scramble — and have something warm and alive on
> the wall instead of a blank monitor.

---

## 📸 Screenshots

_Coming soon. The [`screenshots/`](screenshots/) folder has the shot list — a photo
of it running on the wall makes the best hero image. Drop images there (or drag them
into this file on GitHub) and they'll show up here._

---

## ✨ Features

### On the wall
- 📅 **Aggregated calendar** — Google + iCloud + any `.ics` feed, color-coded per calendar, recurring events expanded. No OAuth, just private iCal URLs.
- ⏰ **"What's Next"** — upcoming events as big cards with live countdowns, plus a bin/recycling reminder.
- 🎉 **Countdowns** — birthdays, trips, holidays (with yearly repeat) as chips on the Hub.
- 🛒 **Shared lists** — Grocery + Checklist on the Hub, Family Notes in the gallery rail, all synced to the Bring! app.
- 🌤️ Weather, big clock, a warm time-of-day greeting, and a word of the day.

### Entertainment modes
- 🎵 **Synced-lyric music screen** — live Spotify track with time-synced lyrics (LRCLIB), animated word-by-word. The **background matches the mood of the music** (read from the album art — dark/heavy covers get moody themes, bright ones get sunny themes) and varies every play.
- 🖼️ **Photo gallery** — a shuffled Ken-Burns slideshow of your uploaded photos (every photo gets equal time), with a side rail of **news, YouTube, and family notes**.
- ▶️ **Full-screen YouTube** — send a video by link *or* by name from your phone.
- 📰 **News** — rotating headlines with short TL;DR summaries (NPR + BBC).
- 🔊 **Audio anywhere** — wall sound plays through the monitor, or pair a Bluetooth speaker (e.g. a Google Home / Nest) to hear music across the room.
- 🔄 **Auto mode** — when nothing's playing, gently rotates between the calendar and the gallery.

### From your phone (any browser on the home network)
- 📱 **Remote** — switch what the wall shows, control Spotify (play / pause / skip), and send YouTube.
- 🛒 **Add to any list** — via the shared [Bring!](https://www.getbring.com/) app, so **both iPhone and Android** work.
- 🍳 **Meal planning** — set the week's dinners, get **suggestions built from what you actually buy**, and add a recipe's ingredients to the grocery list in one tap.
- 🖼️ Manage photos, 🎉 manage countdowns.

### Runs itself
- 🖥️ **Kiosk** — Chromium full-screen, autostarts on boot.
- 🌙 **Night dimming** — the ambient screens fade dark overnight and come back in the morning.
- 🛡️ **Self-healing watchdog** — reconnects WiFi, restarts the app, and reloads a frozen display automatically, so it doesn't need babysitting.

---

## 🧰 Hardware

- **Raspberry Pi 5** (a Pi 4 works too)
- Any HDMI monitor — **mounted portrait** here, but landscape works
- microSD card + power; that's it. No cloud, no subscription.

---

## 🏗️ How it works

A single Flask app (`calboard`) serves every screen and a small JSON API; the
wall's Chromium and your phone are both just browsers pointed at it.

| Piece | What it does |
|---|---|
| `web/app.py` | Flask routes + the JSON API for every screen |
| `web/templates/` | Each screen (hub, music, gallery, youtube, remote, meals, …) — vanilla JS, no framework |
| `bring.py` / `bring_sync.py` | Two-way sync of the three lists with **Bring!** |
| `spotify.py` | Now-playing + playback control (Spotify Web API) |
| `lyrics.py` | Time-synced lyrics (LRCLIB) |
| `widgets.py` | Weather, word/recipe of the day |
| `scripts/wall-watchdog.sh` | The self-healing watchdog (runs via a systemd timer) |

**Integrations — all optional, all free, most need no API key:**
Google/iCloud iCal · [Bring!](https://www.getbring.com/) · [Spotify](https://developer.spotify.com/) · [LRCLIB](https://lrclib.net/) · [TheMealDB](https://www.themealdb.com/) · NPR/BBC RSS.

On the Pi it runs as systemd services — `calboard` (web), `bring-sync` (list
sync), and `wall-watchdog` (the timer) — and updates deploy with a simple
`rsync` + service restart.

---

## 🚀 Quickstart (on a laptop, zero setup)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml     # ships with demo: true → sample events
calboard-web                           # → http://localhost:8000
```

Everything runs in **demo mode** out of the box — sample events, no accounts
needed — so you can see the whole thing before wiring up anything real.

## 🔧 Make it yours

Edit `config.yaml`, set `demo: false`, and add your calendars:
- **Google Calendar** → Settings → *your calendar* → **"Secret address in iCal format"**
- **iCloud** → share a calendar → make it **Public** → copy the link → change `webcal://` to `https://`

Give each a `name` and `color`. Every other integration (Bring!, Spotify, meals,
news, photos) is optional and layers on top — the wall works with just calendars.

## 🖥️ On the Raspberry Pi

Install the venv + dependencies, run `calboard-web` as a systemd service, and
launch Chromium in kiosk mode pointed at `http://localhost:8000`. Deploy updates
by `rsync`-ing the working tree to the Pi and restarting the service.

---

## 🔒 A note on privacy

This repo is public, but **no credentials or personal data are in it** — every
secret (calendar URLs, Bring!/Spotify logins, tokens) lives only on the device in
`0600`, git-ignored files, and all state (photos, lists, meals, countdowns) stays
local. Nothing is sent to any third party beyond the optional integrations you
choose to enable.

## License

MIT — build your own, make it yours.
