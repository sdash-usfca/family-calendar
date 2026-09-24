"""Time-synced lyrics via LRCLIB (free, no key) for the lyric screen.

LRCLIB returns LRC-format synced lyrics ([mm:ss.xx] per line). We search by
track + artist, prefer a result that has synced lyrics and the closest duration,
parse it to [{t_ms, text}], and cache per track so the wall can poll cheaply.
Not every song has synced lyrics (community-sourced, mostly popular tracks) —
callers fall back to a "now playing" card when `synced` is empty.
"""
from __future__ import annotations

import re

import requests

_SEARCH_URL = "https://lrclib.net/api/search"
_LINE_TS = re.compile(r"\[(\d+):(\d+)(?:[.:](\d+))?\]")
_cache: dict = {}


def _parse_lrc(lrc: str) -> list:
    lines = []
    for raw in (lrc or "").splitlines():
        stamps = list(_LINE_TS.finditer(raw))
        if not stamps:
            continue
        text = raw[stamps[-1].end():].strip()
        for m in stamps:
            mm, ss = int(m.group(1)), int(m.group(2))
            frac = (m.group(3) or "0").ljust(3, "0")[:3]
            t = (mm * 60 + ss) * 1000 + int(frac)
            lines.append({"t": t, "text": text})
    lines.sort(key=lambda x: x["t"])
    return lines


def _clean_track(t: str) -> str:
    t = re.sub(r"\s*[\(\[].*?[\)\]]", "", t or "")      # drop (From ...), [Remix] …
    t = re.split(r"\s+-\s+", t)[0]                       # drop "- Radio Edit" etc.
    return t.strip()


def _search(track: str, artist: str) -> list:
    params = {"track_name": track} if not artist else {"track_name": track, "artist_name": artist}
    try:
        r = requests.get(_SEARCH_URL, params=params,
                         headers={"User-Agent": "calboard-lyric-wall/1.0"}, timeout=10)
        if r.status_code == 200:
            return r.json() or []
    except Exception:  # noqa: BLE001
        pass
    return []


def get_synced(track: str, artist: str, album: str = "", duration_ms: int = 0) -> dict:
    """{'synced': [{t,text}], 'plain': str, 'found': bool} — never raises.

    Real Spotify names often carry extra bits ("(From ...)", multiple artists), so
    we try the exact query, then a cleaned track + primary artist, then track-only.
    Prefer synced lyrics with the closest duration; fall back to plain text.
    """
    if not track:
        return {"synced": [], "plain": "", "found": False}
    key = f"{track.lower()}|{artist.lower()}"
    if key in _cache:
        return _cache[key]

    first_artist = (artist or "").split(",")[0].strip()
    clean = _clean_track(track)
    tried, queries = set(), []
    for t, a in [(track, artist), (clean, first_artist), (clean, "")]:
        sig = (t.lower(), a.lower())
        if t and sig not in tried:
            tried.add(sig)
            queries.append((t, a))

    result = {"synced": [], "plain": "", "found": False}
    plain_fallback = ""
    for t, a in queries:
        items = _search(t, a)
        best, best_score = None, None
        for it in items:
            if not it.get("syncedLyrics"):
                if not plain_fallback and it.get("plainLyrics"):
                    plain_fallback = it["plainLyrics"]
                continue
            dur = (it.get("duration") or 0) * 1000
            score = abs(dur - duration_ms) if duration_ms else 0
            if best is None or score < best_score:
                best, best_score = it, score
        if best:
            result = {"synced": _parse_lrc(best["syncedLyrics"]),
                      "plain": best.get("plainLyrics") or "", "found": True}
            _cache[key] = result
            return result

    if plain_fallback:
        result = {"synced": [], "plain": plain_fallback, "found": True}
    _cache[key] = result
    return result
