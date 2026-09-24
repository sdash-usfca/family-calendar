"""Spotify integration — reads the currently-playing track for the lyric screen.

Uses the Authorization Code flow. Credentials live in ``.spotify_creds.json``
(0600, gitignored): ``{client_id, client_secret, redirect_uri, refresh_token}``.
The refresh_token is added once, after the user authorizes via ``authorize_url()``
and the returned code is passed to ``exchange_code()``. Access tokens are then
minted on demand and cached in memory.
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Optional

import requests

_CREDS_FILE = ".spotify_creds.json"
_SCOPES = "user-read-currently-playing user-read-playback-state user-modify-playback-state"
_AUTH_URL = "https://accounts.spotify.com/authorize"
_TOKEN_URL = "https://accounts.spotify.com/api/token"
_API = "https://api.spotify.com/v1"

_tok = {"access_token": None, "expires_at": 0.0}
# Shared cache so N open screens don't each hammer Spotify (dev-mode is rate-limited).
# Adaptive TTL: poll fast only while a song is actually playing; idle is lazy.
_np = {"data": None, "at": 0.0, "backoff_until": 0.0}
_NP_TTL_PLAYING = 5.0
_NP_TTL_IDLE = 15.0


def _read_creds() -> Optional[dict]:
    try:
        with open(_CREDS_FILE) as f:
            data = json.load(f)
        if data.get("client_id") and data.get("client_secret"):
            return data
    except Exception:  # noqa: BLE001
        pass
    return None


def _save_creds(data: dict) -> None:
    with open(_CREDS_FILE, "w") as f:
        json.dump(data, f)
    os.chmod(_CREDS_FILE, 0o600)


def configured() -> bool:
    """Client id/secret present (app created), auth may or may not be done yet."""
    return _read_creds() is not None


def enabled() -> bool:
    """Fully connected — a refresh token is stored, so we can read playback."""
    c = _read_creds()
    return bool(c and c.get("refresh_token"))


def authorize_url() -> str:
    c = _read_creds()
    params = {
        "client_id": c["client_id"],
        "response_type": "code",
        "redirect_uri": c["redirect_uri"],
        "scope": _SCOPES,
    }
    return _AUTH_URL + "?" + urllib.parse.urlencode(params)


def _post_token(data: dict) -> dict:
    c = _read_creds()
    r = requests.post(_TOKEN_URL, data=data, auth=(c["client_id"], c["client_secret"]), timeout=15)
    r.raise_for_status()
    return r.json()


def exchange_code(code: str) -> dict:
    """Trade an authorization code for tokens and persist the refresh token."""
    c = _read_creds()
    resp = _post_token({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": c["redirect_uri"],
    })
    if resp.get("refresh_token"):
        c["refresh_token"] = resp["refresh_token"]
        _save_creds(c)
    return resp


def _access_token() -> str:
    if _tok["access_token"] and time.time() < _tok["expires_at"] - 30:
        return _tok["access_token"]
    resp = _post_token({"grant_type": "refresh_token", "refresh_token": _read_creds()["refresh_token"]})
    _tok["access_token"] = resp["access_token"]
    _tok["expires_at"] = time.time() + resp.get("expires_in", 3600)
    if resp.get("refresh_token"):  # Spotify occasionally rotates it
        c = _read_creds()
        c["refresh_token"] = resp["refresh_token"]
        _save_creds(c)
    return _tok["access_token"]


def now_playing() -> dict:
    """The current track (or {'is_playing': False}); cached, never raises.

    Served from a shared cache for `_NP_TTL` seconds and during any 429 back-off,
    so many open screens hit Spotify at most once per TTL and we respect its
    Retry-After instead of hammering a rate-limited endpoint.
    """
    if not enabled():
        return {"enabled": False, "is_playing": False}
    now = time.time()
    if now < _np["backoff_until"]:   # honoring a 429 Retry-After — do NOT call Spotify at all
        return _np["data"] or {"enabled": True, "is_playing": False}
    ttl = _NP_TTL_PLAYING if (_np["data"] and _np["data"].get("is_playing")) else _NP_TTL_IDLE
    if _np["data"] is not None and now - _np["at"] < ttl:
        return _np["data"]
    try:
        tok = _access_token()
        r = requests.get(_API + "/me/player/currently-playing",
                         headers={"Authorization": "Bearer " + tok}, timeout=10)
        if r.status_code == 429:
            try:
                retry = int(r.headers.get("Retry-After", "10"))
            except Exception:  # noqa: BLE001
                retry = 10
            _np["backoff_until"] = now + max(5, retry)
            _np["at"] = now
            return _np["data"] or {"enabled": True, "is_playing": False}
        if r.status_code == 204 or not r.content:
            data = {"enabled": True, "is_playing": False}
        else:
            r.raise_for_status()
            j = r.json()
            item = j.get("item") or {}
            album = item.get("album") or {}
            data = {
                "enabled": True,
                "is_playing": bool(j.get("is_playing")),
                "progress_ms": j.get("progress_ms", 0),
                "id": item.get("id"),
                "track": item.get("name"),
                "artists": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "album": album.get("name"),
                "art": (album.get("images") or [{}])[0].get("url"),
                "duration_ms": item.get("duration_ms", 0),
            }
        _np["data"] = data
        _np["at"] = now
        return data
    except Exception as e:  # noqa: BLE001 — keep last good state; never break the wall
        _np["at"] = now
        return _np["data"] or {"enabled": True, "is_playing": False, "error": str(e)}
