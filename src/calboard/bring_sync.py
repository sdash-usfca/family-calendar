"""Background service: mirror the Bring! lists into the wall's local state files.

Runs on the Pi as ``bring-sync.service`` from the app's working directory
(``~/family-calendar``). It logs into Bring! once, then every
``BRING_POLL_SECONDS`` (default 30) writes each mapped Bring! list's to-buy items
to its local mirror the wall reads (grocery / checklist / notes). On any error
(network blip, token expiry) it backs off and logs in again, so the service
stays alive indefinitely.

Run with:  python -m calboard.bring_sync
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time

from . import bring as bring_mod

_STATE_FILES = {
    "grocery": ".grocery_state.json",
    "checklist": ".checklist_state.json",
    "notes": ".notes_state.json",
}
_GROCERY_HISTORY_FILE = ".grocery_history.json"
_POLL = int(os.environ.get("BRING_POLL_SECONDS", "30"))


def _log_grocery(names: list) -> None:
    """Record bought/added grocery items over time (name -> count, last) so the
    meal-suggestion feature can learn what the family actually buys."""
    if not names:
        return
    try:
        hist = {}
        if os.path.exists(_GROCERY_HISTORY_FILE):
            with open(_GROCERY_HISTORY_FILE) as f:
                hist = json.load(f)
        now = time.time()
        for n in names:
            k = n.strip().lower()
            if not k:
                continue
            e = hist.get(k) or {"name": n.strip(), "count": 0, "last": 0}
            e["count"] = int(e.get("count", 0)) + 1
            e["last"] = now
            e["name"] = n.strip()
            hist[k] = e
        tmp = _GROCERY_HISTORY_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(hist, f)
        os.replace(tmp, _GROCERY_HISTORY_FILE)
    except Exception:  # noqa: BLE001
        pass


def _write_mirror(state_file: str, items: list) -> None:
    tmp = state_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"items": items}, f)
    os.replace(tmp, state_file)   # atomic, so a reader never sees half a file


def _targets(creds: dict) -> list:
    """[(key, uuid, state_file)] for every wall list mapped to a Bring! list."""
    lists = dict(creds.get("lists") or {})
    if "grocery" not in lists and creds.get("list_uuid"):
        lists["grocery"] = creds["list_uuid"]   # backward compat
    return [(k, lists[k], _STATE_FILES[k]) for k in _STATE_FILES if lists.get(k)]


async def _main() -> int:
    import aiohttp
    from bring_api import Bring

    creds = bring_mod._read_creds()
    if not creds:
        print("bring_sync: no .bring_creds.json — nothing to mirror", flush=True)
        return 0
    targets = _targets(creds)
    if not targets:
        print("bring_sync: no Bring! lists mapped — nothing to mirror", flush=True)
        return 0

    print(f"bring_sync: mirroring {[k for k, _, _ in targets]} every {_POLL}s", flush=True)
    while True:
        try:
            async with aiohttp.ClientSession() as session:
                bring = Bring(session, creds["email"], creds["password"])
                await bring.login()
                prev_grocery = set()   # grocery names seen last cycle (for history logging)
                # Reuse this logged-in session for polling until something fails.
                while True:
                    for _key, uuid, state_file in targets:
                        resp = await bring.get_list(uuid)
                        purchase = getattr(resp.items, "purchase", []) or []
                        pairs = [{"name": bring_mod._item_name(i), "spec": bring_mod._item_spec(i)}
                                 for i in purchase if bring_mod._item_name(i)]
                        _write_mirror(state_file, bring_mod.to_mirror_items(pairs))
                        if _key == "grocery":
                            names = [p["name"] for p in pairs if p.get("name")]
                            new = [n for n in names if n.lower() not in prev_grocery]
                            _log_grocery(new)
                            prev_grocery = {n.lower() for n in names}
                    await asyncio.sleep(_POLL)
        except Exception as e:  # noqa: BLE001 — keep the service alive across hiccups
            print(f"bring_sync: {type(e).__name__}: {e} — re-login in 60s", flush=True)
            await asyncio.sleep(60)


def main() -> int:
    return asyncio.run(_main())


if __name__ == "__main__":
    sys.exit(main())
