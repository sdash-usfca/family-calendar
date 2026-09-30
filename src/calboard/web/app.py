"""Flask app: renders the wall dashboard and serves the agenda as JSON."""
from __future__ import annotations

import html
import json
import os
import re
import secrets
import socket
import time
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Optional
from zoneinfo import ZoneInfo

import requests
from flask import Flask, jsonify, make_response, render_template, request, send_from_directory

from .. import bring, lyrics, spotify
from ..calendars import get_events
from ..config import Config, load_config
from ..widgets import get_recipe_of_day, get_weather, get_word_of_day

_CHORES_STATE_FILE = ".chores_state.json"
_GROCERY_STATE_FILE = ".grocery_state.json"
_CHECKLIST_STATE_FILE = ".checklist_state.json"
_NOTES_STATE_FILE = ".notes_state.json"
_MODE_STATE_FILE = ".mode_state.json"
_MODES = ("hub", "music", "gallery", "youtube", "auto")
_AUTO_ROTATE_SECS = 120  # in auto mode, seconds between Calendar <-> Photos
_PHOTOS_DIR = "photos"
_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
_YOUTUBE_STATE_FILE = ".youtube_state.json"
_YT_ID_RE = re.compile(
    r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/|live/|v/)|[?&]v=)([A-Za-z0-9_-]{11})")
_NEWS_FEEDS = [
    ("https://feeds.npr.org/1001/rss.xml", "NPR"),          # NPR top stories (US + world)
    ("http://feeds.bbci.co.uk/news/world/rss.xml", "BBC"),  # BBC world
]
_NEWS_TTL = 900  # seconds between refreshes
_news = {"items": [], "at": 0.0}


def _strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def _parse_feed(url: str, source: str) -> list:
    out = []
    try:
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=12)
        root = ET.fromstring(r.content)
        for it in root.iter("item"):
            title = _strip_html(it.findtext("title") or "")
            summary = _strip_html(it.findtext("description") or "")
            if len(summary) > 230:
                summary = summary[:227].rsplit(" ", 1)[0] + "…"
            if title:
                out.append({"title": title, "summary": summary, "source": source})
            if len(out) >= 12:
                break
    except Exception:  # noqa: BLE001
        pass
    return out


def _get_news() -> list:
    """Headlines + short publisher summaries from a couple of RSS feeds (cached; no key)."""
    now = time.time()
    if _news["items"] and now - _news["at"] < _NEWS_TTL:
        return _news["items"]
    feeds = [_parse_feed(u, name) for (u, name) in _NEWS_FEEDS]
    items, i = [], 0
    while any(i < len(f) for f in feeds):          # interleave so sources alternate
        for f in feeds:
            if i < len(f):
                items.append(f[i])
        i += 1
    items = items[:24]
    if items:
        _news["items"], _news["at"] = items, now
    return items or _news["items"]


def _youtube_id(text: str) -> str:
    """Extract an 11-char YouTube video id from a URL (or accept a bare id)."""
    text = (text or "").strip()
    m = _YT_ID_RE.search(text)
    if m:
        return m.group(1)
    return text if re.fullmatch(r"[A-Za-z0-9_-]{11}", text) else ""


def _get_youtube() -> str:
    try:
        with open(_YOUTUBE_STATE_FILE) as f:
            return str(json.load(f).get("id", ""))
    except Exception:  # noqa: BLE001
        return ""


def _youtube_search(query: str) -> str:
    """First video id for a search term (scrapes YouTube results; no API key)."""
    try:
        r = requests.get(
            "https://www.youtube.com/results", params={"search_query": query},
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 "
                                   "(KHTML, like Gecko) Chrome/120 Safari/537.36",
                     "Accept-Language": "en-US,en;q=0.9"},
            timeout=12)
        m = re.search(r'"videoId":"([A-Za-z0-9_-]{11})"', r.text)
        return m.group(1) if m else ""
    except Exception:  # noqa: BLE001
        return ""


def _list_photos() -> list:
    """Uploaded photo filenames, oldest first."""
    try:
        os.makedirs(_PHOTOS_DIR, exist_ok=True)
        files = [f for f in os.listdir(_PHOTOS_DIR)
                 if os.path.splitext(f)[1].lower() in _PHOTO_EXTS]
        files.sort(key=lambda f: os.path.getmtime(os.path.join(_PHOTOS_DIR, f)))
        return files
    except Exception:  # noqa: BLE001
        return []


def _load_chores_state(n: int) -> list:
    """Which chores are checked off today. Resets automatically on a new day."""
    today = date.today().isoformat()
    if os.path.exists(_CHORES_STATE_FILE):
        try:
            with open(_CHORES_STATE_FILE) as f:
                saved = json.load(f)
            if saved.get("date") == today and len(saved.get("checked", [])) == n:
                return saved["checked"]
        except Exception:  # noqa: BLE001 — a corrupt state file just resets
            pass
    return [False] * n


def _save_chores_state(checked: list) -> None:
    with open(_CHORES_STATE_FILE, "w") as f:
        json.dump({"date": date.today().isoformat(), "checked": checked}, f)


def _load_list(path: str) -> list:
    """A shared, persistent list of {id, text, checked, source} items (grocery / checklist)."""
    if os.path.exists(path):
        try:
            with open(path) as f:
                items = json.load(f).get("items", [])
            if isinstance(items, list):
                return items
        except Exception:  # noqa: BLE001 — a corrupt state file just resets
            pass
    return []


def _save_list(path: str, items: list) -> None:
    with open(path, "w") as f:
        json.dump({"items": items}, f)


def _add_list_items(path: str, text: str, source: str = "web", split: bool = True) -> list:
    """Add item(s). With split=True, 'milk, eggs' (or newlines) adds several; with
    split=False the whole text is one item (used for notes, so sentences stay intact)."""
    items = _load_list(path)
    existing = {i.get("text", "").strip().lower() for i in items}
    parts = (p.strip() for p in text.replace("\n", ",").split(",")) if split else [text.strip()]
    for part in parts:
        if part and part.lower() not in existing:
            items.append({"id": uuid.uuid4().hex[:8], "text": part, "checked": False, "source": source})
            existing.add(part.lower())
    _save_list(path, items)
    return items


def _toggle_list_item(path: str, item_id: str) -> list:
    items = _load_list(path)
    for it in items:
        if it.get("id") == item_id:
            it["checked"] = not it.get("checked", False)
            break
    _save_list(path, items)
    return items


def _remove_list_item(path: str, item_id: str) -> list:
    items = [it for it in _load_list(path) if it.get("id") != item_id]
    _save_list(path, items)
    return items


def _clear_checked(path: str) -> list:
    items = [it for it in _load_list(path) if not it.get("checked")]
    _save_list(path, items)
    return items


def _hook_token() -> str:
    """A stable secret guarding the public voice webhook. Generated once, kept in
    .hook_token (0600, gitignored) so the same token survives restarts."""
    path = ".hook_token"
    try:
        with open(path) as f:
            tok = f.read().strip()
        if tok:
            return tok
    except Exception:  # noqa: BLE001
        pass
    tok = secrets.token_urlsafe(18)
    try:
        with open(path, "w") as f:
            f.write(tok)
        os.chmod(path, 0o600)
    except Exception:  # noqa: BLE001
        pass
    return tok


def _lan_ip() -> str:
    """Best-effort LAN IP so the phone QR points at a reachable address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:  # noqa: BLE001
        return "localhost"


_MEALS_STATE_FILE = ".meals_state.json"
_GROCERY_HISTORY_FILE = ".grocery_history.json"
_MEAL_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_MEAL_SUG = {"data": None, "at": 0.0, "ings": None}
_MEAL_SUG_TTL = 3600
_MEAL_STOP = {"salt", "water", "sugar", "oil", "butter"}   # too generic to narrow meals


def _get_meals() -> dict:
    try:
        with open(_MEALS_STATE_FILE) as f:
            d = json.load(f)
        return {k: str(d.get(k, "")) for k in _MEAL_DAYS}
    except Exception:  # noqa: BLE001
        return {k: "" for k in _MEAL_DAYS}


_ING_DROP = {"oil", "fresh", "organic", "powder", "ground", "whole", "large", "small",
             "boneless", "skinless", "raw", "dried", "chopped", "sliced", "canned", "frozen",
             "low", "fat", "free", "of", "the", "a", "pack", "bottle", "box", "bag", "extra", "virgin"}


def _norm_ing(name: str) -> str:
    """Reduce a grocery product name to a recipe-style ingredient (e.g. 'Avocado
    Oil' -> 'avocado', 'Chicken Breasts' -> 'chicken breast')."""
    words = [w for w in re.sub(r"[^a-z ]", " ", (name or "").lower()).split() if w not in _ING_DROP]
    if not words:
        return ""
    s = " ".join(words)
    return s[:-1] if s.endswith("s") and not s.endswith("ss") else s


def _grocery_ingredients(n: int = 6) -> list:
    """Most-relevant (normalized) ingredients from the current grocery list + history."""
    ings: dict = {}

    def add(name, w):
        k = _norm_ing(name)
        if k and k not in _MEAL_STOP and len(k) > 1:
            ings[k] = ings.get(k, 0) + w

    for it in _load_list(_GROCERY_STATE_FILE):
        add(it.get("name") or it.get("text") or "", 3)   # weight what's on the list now
    try:
        with open(_GROCERY_HISTORY_FILE) as f:
            hist = json.load(f)
        for _k, e in hist.items():
            add(e.get("name", ""), min(int(e.get("count", 1)), 5))
    except Exception:  # noqa: BLE001
        pass
    return [k for k, _ in sorted(ings.items(), key=lambda kv: -kv[1])][:n]


def _meal_suggestions() -> dict:
    """Meals (TheMealDB, free) that use the most of the family's ingredients."""
    ings = _grocery_ingredients(6)
    now = time.time()
    if _MEAL_SUG["data"] and _MEAL_SUG["ings"] == ings and now - _MEAL_SUG["at"] < _MEAL_SUG_TTL:
        return _MEAL_SUG["data"]
    hits: dict = {}
    for ing in ings:
        for q in dict.fromkeys([ing, ing.split()[0]]):     # full term, then main noun
            try:
                r = requests.get("https://www.themealdb.com/api/json/v1/1/filter.php",
                                 params={"i": q}, timeout=10)
                for m in (r.json().get("meals") or [])[:20]:
                    mid = m.get("idMeal")
                    e = hits.get(mid) or {"id": mid, "name": m.get("strMeal"),
                                          "thumb": m.get("strMealThumb"), "matched": set()}
                    e["matched"].add(ing)
                    hits[mid] = e
            except Exception:  # noqa: BLE001
                pass
    ranked = sorted(hits.values(), key=lambda e: (-len(e["matched"]), e["name"] or ""))[:8]
    data = {"ingredients": ings, "suggestions": [
        {"id": e["id"], "name": e["name"], "thumb": e["thumb"], "matched": sorted(e["matched"])}
        for e in ranked]}
    _MEAL_SUG.update(data=data, at=now, ings=ings)
    return data


def _meal_ingredients(meal_id: str) -> list:
    """Ingredient names for one meal (TheMealDB lookup) — for one-tap 'add to grocery'."""
    try:
        r = requests.get("https://www.themealdb.com/api/json/v1/1/lookup.php",
                         params={"i": meal_id}, timeout=10)
        meals = r.json().get("meals") or []
    except Exception:  # noqa: BLE001
        return []
    if not meals:
        return []
    m = meals[0]
    out = []
    for i in range(1, 21):
        name = (m.get(f"strIngredient{i}") or "").strip()
        if name and name.lower() not in {n.lower() for n in out}:
            out.append(name)
    return out


def create_app(config: Optional[Config] = None) -> Flask:
    config = config or load_config()
    app = Flask(__name__)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["MAX_CONTENT_LENGTH"] = 40 * 1024 * 1024  # 40 MB photo uploads
    tz = ZoneInfo(config.timezone)

    @app.route("/")
    def index():
        resp = make_response(render_template("index.html"))
        resp.headers["Cache-Control"] = "no-store"   # kiosk always loads the latest UI
        return resp

    @app.route("/api/agenda")
    def api_agenda():
        now = datetime.now(tz)
        events = get_events(config, now)
        legend = [{"name": c.name, "color": c.color} for c in config.calendars]
        return jsonify({
            "now": now.isoformat(),
            "timezone": config.timezone,
            "whats_next_count": config.whats_next_count,
            "board_days": config.board_days,
            "legend": legend,
            "events": [e.to_dict() for e in events],
        })

    @app.route("/api/board")
    def api_board():
        checked = _load_chores_state(len(config.chores))
        chores = [
            {"person": c.person, "task": c.task, "color": c.color, "checked": checked[i]}
            for i, c in enumerate(config.chores)
        ]
        # A manually-set meal_tonight always wins (family knows what's already planned);
        # otherwise auto-suggest a real recipe for the day.
        recipe = None if config.meal_tonight else get_recipe_of_day()
        return jsonify({
            "location": config.location.name,
            "weather": get_weather(config.location.lat, config.location.lon),
            "word_of_day": get_word_of_day(),
            "chores": chores,
            "meal_tonight": config.meal_tonight,
            "recipe": recipe,
        })

    @app.route("/api/chores/toggle", methods=["POST"])
    def api_chores_toggle():
        idx = int(request.get_json(force=True).get("index", -1))
        checked = _load_chores_state(len(config.chores))
        if 0 <= idx < len(checked):
            checked[idx] = not checked[idx]
            _save_chores_state(checked)
        return jsonify({"checked": checked})

    @app.route("/list")
    def lists_page():
        resp = make_response(render_template("list.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    # ---- Shared lists (grocery / checklist / notes), backed by Bring! ----
    # When a list is mapped to a Bring! list, Bring! is the source of truth: the
    # wall reads the local mirror (kept fresh by calboard.bring_sync) and every
    # write is pushed to Bring!, then applied to the mirror optimistically so the
    # UI feels instant. Without a Bring! mapping it falls back to a local list.
    _STATE_FILES = {
        "grocery": _GROCERY_STATE_FILE,
        "checklist": _CHECKLIST_STATE_FILE,
        "notes": _NOTES_STATE_FILE,
    }

    def _list_optimistic(state_file, update):
        items = update(_load_list(state_file))
        _save_list(state_file, items)
        return items

    def _bring_add(key, text, source="web", split=True):
        state_file = _STATE_FILES[key]
        if not bring.enabled(key):
            return _add_list_items(state_file, text, source=source, split=split)
        parts = ([p.strip() for p in str(text).replace("\n", ",").split(",")]
                 if split else [str(text).strip()])
        added = []
        for name in parts:
            if not name:
                continue
            try:
                bring.add_item(name, key)
                added.append(name)
            except Exception:  # noqa: BLE001 — a failed push just isn't mirrored
                pass

        def upd(items):
            have = {i.get("id") for i in items}
            for name in added:
                if name not in have:
                    items.append({"id": name, "text": name, "checked": False,
                                  "name": name, "spec": "", "source": source})
                    have.add(name)
            return items
        return _list_optimistic(state_file, upd)

    def _bring_toggle(key, gid):
        """Check off = 'done' → complete it in Bring! (leaves the active list)."""
        state_file = _STATE_FILES[key]
        if not bring.enabled(key):
            return _toggle_list_item(state_file, gid)
        try:
            bring.complete_item(gid, key)
        except Exception:  # noqa: BLE001
            pass
        return _list_optimistic(state_file, lambda items: [i for i in items if i.get("id") != gid])

    def _bring_remove(key, gid):
        state_file = _STATE_FILES[key]
        if not bring.enabled(key):
            return _remove_list_item(state_file, gid)
        try:
            bring.remove_item(gid, key)
        except Exception:  # noqa: BLE001
            pass
        return _list_optimistic(state_file, lambda items: [i for i in items if i.get("id") != gid])

    def _bring_clear(key, remove_all=False):
        """Grocery/checklist 'clear checked' is a no-op with Bring! (checked items
        already left the list). Notes 'clear all' deletes every item."""
        state_file = _STATE_FILES[key]
        if not bring.enabled(key):
            if remove_all:
                _save_list(state_file, [])
                return []
            return _clear_checked(state_file)
        if remove_all:
            for it in _load_list(state_file):
                try:
                    bring.remove_item(it.get("id", ""), key)
                except Exception:  # noqa: BLE001
                    pass
            _save_list(state_file, [])
            return []
        return _load_list(state_file)

    @app.route("/api/grocery")
    def api_grocery():
        return jsonify({
            "items": _load_list(_GROCERY_STATE_FILE),
            "add_url": f"http://{_lan_ip()}:{config.web.port}/list",
        })

    @app.route("/api/grocery/add", methods=["POST"])
    def api_grocery_add():
        text = str(request.get_json(force=True).get("text", "") or "")
        return jsonify({"items": _bring_add("grocery", text)})

    @app.route("/api/grocery/toggle", methods=["POST"])
    def api_grocery_toggle():
        gid = str(request.get_json(force=True).get("id", ""))
        return jsonify({"items": _bring_toggle("grocery", gid)})

    @app.route("/api/grocery/remove", methods=["POST"])
    def api_grocery_remove():
        gid = str(request.get_json(force=True).get("id", ""))
        return jsonify({"items": _bring_remove("grocery", gid)})

    @app.route("/api/grocery/clear", methods=["POST"])
    def api_grocery_clear():
        return jsonify({"items": _bring_clear("grocery")})

    # ---- Today's checklist (to-dos) ----
    @app.route("/api/checklist")
    def api_checklist():
        return jsonify({
            "items": _load_list(_CHECKLIST_STATE_FILE),
            "add_url": f"http://{_lan_ip()}:{config.web.port}/list",
        })

    @app.route("/api/checklist/add", methods=["POST"])
    def api_checklist_add():
        text = str(request.get_json(force=True).get("text", "") or "")
        return jsonify({"items": _bring_add("checklist", text)})

    @app.route("/api/checklist/toggle", methods=["POST"])
    def api_checklist_toggle():
        gid = str(request.get_json(force=True).get("id", ""))
        return jsonify({"items": _bring_toggle("checklist", gid)})

    @app.route("/api/checklist/remove", methods=["POST"])
    def api_checklist_remove():
        gid = str(request.get_json(force=True).get("id", ""))
        return jsonify({"items": _bring_remove("checklist", gid)})

    @app.route("/api/checklist/clear", methods=["POST"])
    def api_checklist_clear():
        return jsonify({"items": _bring_clear("checklist")})

    # ---- Family notes (message board) ----
    @app.route("/api/notes")
    def api_notes():
        return jsonify({"items": _load_list(_NOTES_STATE_FILE)})

    @app.route("/api/notes/add", methods=["POST"])
    def api_notes_add():
        text = str(request.get_json(force=True).get("text", "") or "")
        return jsonify({"items": _bring_add("notes", text, split=False)})

    @app.route("/api/notes/remove", methods=["POST"])
    def api_notes_remove():
        gid = str(request.get_json(force=True).get("id", ""))
        return jsonify({"items": _bring_remove("notes", gid)})

    @app.route("/api/notes/clear", methods=["POST"])
    def api_notes_clear():
        return jsonify({"items": _bring_clear("notes", remove_all=True)})

    # ---- Public voice webhook ----
    # The one route deliberately reachable from the internet (via Tailscale
    # Funnel), for a phone shortcut (e.g. a Siri Shortcut) to add by voice.
    # Guarded by a secret token. Registered at two paths so it works whether the
    # tunnel strips a path prefix or not. Body: {"token","item","list"}.
    hook_token = _hook_token()

    @app.route("/hooks/add", methods=["POST", "GET"])
    @app.route("/add", methods=["POST", "GET"])
    def hook_add():
        # Accept fields from JSON body OR query string / form, so a simple phone
        # shortcut can just hit a URL (…/hooks/add?token=…&list=grocery&item=milk).
        data = request.get_json(force=True, silent=True) or {}

        def field(key, default=""):
            val = data.get(key)
            return request.values.get(key, default) if val is None else val

        if not secrets.compare_digest(str(field("token", "")), hook_token):
            return jsonify({"error": "unauthorized"}), 403
        item = str(field("item", "") or "").strip()
        which = str(field("list", "grocery") or "grocery").strip().lower()
        if not item:
            return jsonify({"error": "no item"}), 400
        if which not in _STATE_FILES:
            return jsonify({"error": "unknown list"}), 400
        items = _bring_add(which, item, source="voice", split=(which != "notes"))
        return jsonify({"ok": True, "added": item, "list": which, "count": len(items)})

    # ---- Spotify + lyric screen ----
    @app.route("/music")
    def music_page():
        resp = make_response(render_template("music.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/nowplaying")
    def api_nowplaying():
        return jsonify(spotify.now_playing())

    @app.route("/api/spotify/control", methods=["POST"])
    def api_spotify_control():
        action = str(request.get_json(force=True).get("action", "") or "")
        return jsonify(spotify.control(action))

    @app.route("/api/lyrics")
    def api_lyrics():
        return jsonify(lyrics.get_synced(
            request.args.get("track", ""),
            request.args.get("artist", ""),
            request.args.get("album", ""),
            request.args.get("duration_ms", type=int) or 0,
        ))

    @app.route("/spotify/callback")
    def spotify_callback():
        code = request.args.get("code", "")
        if not code:
            return ("No authorization code found. Copy this page's full URL "
                    "and send it back to finish setup."), 400
        try:
            spotify.exchange_code(code)
            return "<h2>✅ Spotify connected! You can close this tab.</h2>", 200
        except Exception as e:  # noqa: BLE001
            return (f"Token exchange failed ({e}). Copy this page's full URL "
                    "and send it back."), 500

    # ---- Wall mode / phone remote (Hub <-> Music) ----
    def _get_mode() -> str:
        try:
            with open(_MODE_STATE_FILE) as f:
                m = json.load(f).get("mode", "hub")
            return m if m in _MODES else "hub"
        except Exception:  # noqa: BLE001
            return "hub"

    @app.route("/remote")
    def remote_page():
        resp = make_response(render_template("remote.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/mode")
    def api_mode():
        # Returns the raw mode plus the "view" the wall should show. For explicit
        # modes view==mode and we never touch Spotify (polled every 2s). Only in
        # "auto" do we resolve: a set YouTube video wins, else live Spotify shows
        # lyrics, else it rotates Calendar <-> Photos on a timer.
        mode = _get_mode()
        view = mode
        if mode == "auto":
            if _get_youtube():
                view = "youtube"
            elif spotify.now_playing().get("is_playing"):   # cached; only hit in auto
                view = "music"
            else:
                view = "gallery" if int(time.time() // _AUTO_ROTATE_SECS) % 2 else "hub"
        return jsonify({"mode": mode, "view": view})

    @app.route("/api/mode/set", methods=["POST"])
    def api_mode_set():
        m = str(request.get_json(force=True).get("mode", "hub")).lower()
        if m not in _MODES:
            m = "hub"
        with open(_MODE_STATE_FILE, "w") as f:
            json.dump({"mode": m}, f)
        return jsonify({"mode": m})

    # ---- Gallery mode: photo slideshow + phone upload ----
    @app.route("/gallery")
    def gallery_page():
        resp = make_response(render_template("gallery.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/photos")
    def photos_page():
        resp = make_response(render_template("photos.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/youtube")
    def youtube_page():
        resp = make_response(render_template("youtube.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/photos")
    def api_photos():
        return jsonify({
            "photos": _list_photos(),
            "add_url": f"http://{_lan_ip()}:{config.web.port}/photos",
        })

    @app.route("/media/<path:name>")
    def media(name):
        return send_from_directory(os.path.abspath(_PHOTOS_DIR), name)

    @app.route("/api/photos/upload", methods=["POST"])
    def api_photos_upload():
        os.makedirs(_PHOTOS_DIR, exist_ok=True)
        saved = []
        for f in request.files.getlist("photos"):
            if not f or not f.filename:
                continue
            ext = os.path.splitext(f.filename)[1].lower()
            if ext not in _PHOTO_EXTS:
                continue
            name = uuid.uuid4().hex[:12] + ext
            f.save(os.path.join(_PHOTOS_DIR, name))
            saved.append(name)
        return jsonify({"saved": saved, "photos": _list_photos()})

    @app.route("/api/photos/delete", methods=["POST"])
    def api_photos_delete():
        safe = os.path.basename(str(request.get_json(force=True).get("name", "")))
        if safe and os.path.splitext(safe)[1].lower() in _PHOTO_EXTS:
            try:
                os.remove(os.path.join(_PHOTOS_DIR, safe))
            except Exception:  # noqa: BLE001
                pass
        return jsonify({"photos": _list_photos()})

    # ---- News feed (gallery rail) ----
    @app.route("/api/news")
    def api_news():
        return jsonify({"items": _get_news()})

    # ---- YouTube corner (set from the remote) ----
    @app.route("/api/youtube")
    def api_youtube():
        return jsonify({
            "id": _get_youtube(),
            "remote_url": f"http://{_lan_ip()}:{config.web.port}/remote",
        })

    @app.route("/api/youtube/set", methods=["POST"])
    def api_youtube_set():
        raw = str(request.get_json(force=True).get("url", "")).strip()
        vid = _youtube_id(raw)
        if not vid and raw:                 # not a link/id → treat as a search term
            vid = _youtube_search(raw)
        with open(_YOUTUBE_STATE_FILE, "w") as f:
            json.dump({"id": vid}, f)
        return jsonify({"id": vid, "ok": bool(vid)})

    @app.route("/api/youtube/clear", methods=["POST"])
    def api_youtube_clear():
        with open(_YOUTUBE_STATE_FILE, "w") as f:
            json.dump({"id": ""}, f)
        # If we were in explicit full-screen YouTube mode, drop back to Gallery so
        # the wall doesn't get stuck on an empty player.
        if _get_mode() == "youtube":
            with open(_MODE_STATE_FILE, "w") as f:
                json.dump({"mode": "gallery"}, f)
        return jsonify({"id": ""})

    # ---- Weekly meals + grocery-based suggestions ----
    @app.route("/meals")
    def meals_page():
        resp = make_response(render_template("meals.html"))
        resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.route("/api/meals")
    def api_meals():
        today = _MEAL_DAYS[datetime.now(tz).weekday()]
        return jsonify({
            "meals": _get_meals(), "today": today, "days": _MEAL_DAYS,
            "add_url": f"http://{_lan_ip()}:{config.web.port}/meals",
        })

    @app.route("/api/meals/set", methods=["POST"])
    def api_meals_set():
        body = request.get_json(force=True)
        day = str(body.get("day", "")).lower()
        meal = str(body.get("meal", "") or "").strip()
        if day in _MEAL_DAYS:
            m = _get_meals()
            m[day] = meal
            with open(_MEALS_STATE_FILE, "w") as f:
                json.dump(m, f)
        return jsonify({"meals": _get_meals()})

    @app.route("/api/meals/suggest")
    def api_meals_suggest():
        return jsonify(_meal_suggestions())

    @app.route("/api/meals/to_grocery", methods=["POST"])
    def api_meals_to_grocery():
        """One tap: add a suggested meal's ingredients to the Bring! grocery list,
        skipping anything already on it."""
        mid = str(request.get_json(force=True).get("id", "") or "")
        ings = _meal_ingredients(mid)
        if not ings:
            return jsonify({"added": [], "skipped": []})
        have = {(it.get("name") or it.get("text") or "").strip().lower()
                for it in _load_list(_GROCERY_STATE_FILE)}
        added, skipped = [], []
        for name in ings:
            if name.strip().lower() in have:
                skipped.append(name)
            else:
                _bring_add("grocery", name, split=False)
                added.append(name)
        return jsonify({"added": added, "skipped": skipped})

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True})

    return app
