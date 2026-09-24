"""Bring! shopping-list integration.

Bring! is the single source of truth for the grocery list. A background service
(``calboard.bring_sync``) mirrors the Bring! "purchase" (to-buy) items into the
local ``.grocery_state.json`` so the wall can read them cheaply, and the Flask
write endpoints push changes (add / complete / remove) straight to Bring!. That
keeps one list in sync across the wall, the phone page, the Bring! app, and
"Hey Google, add X to my shopping list".

Bring!'s API is async (bring_api / aiohttp), so these are thin synchronous
wrappers the sync Flask app can call. Writes are infrequent, so each one logs in
fresh. Note: Bring! puts the item's display name in ``BringItem.itemId`` (its
``.name`` is empty), with any extra detail in ``.specification``.

aiohttp / bring_api are imported lazily inside the functions so a machine without
them (or without credentials) still runs the app with the local grocery list.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

_CREDS_FILE = ".bring_creds.json"
_DEFAULT_KEY = "grocery"


def _read_creds() -> Optional[dict]:
    try:
        with open(_CREDS_FILE) as f:
            data = json.load(f)
        if data.get("email") and data.get("password"):
            return data
    except Exception:  # noqa: BLE001 — missing/broken creds simply disables Bring!
        pass
    return None


def list_uuid(key: str = _DEFAULT_KEY) -> Optional[str]:
    """The Bring! list UUID mapped to a wall panel ('grocery'/'checklist'/'notes')."""
    creds = _read_creds() or {}
    lists = creds.get("lists") or {}
    if lists.get(key):
        return lists[key]
    if key == _DEFAULT_KEY:
        return creds.get("list_uuid")  # backward compat with single-list setup
    return None


def enabled(key: str = _DEFAULT_KEY) -> bool:
    """True when this list is backed by a configured Bring! list."""
    return _read_creds() is not None and list_uuid(key) is not None


def _item_name(item) -> str:
    # Bring! puts the display name in itemId; .name is None.
    return getattr(item, "itemId", None) or getattr(item, "name", None) or ""


def _item_spec(item) -> str:
    return getattr(item, "specification", "") or ""


def to_mirror_items(pairs: list) -> list:
    """Convert Bring! [{name, spec}] into wall list items the frontend renders."""
    items = []
    for p in pairs:
        name = p.get("name", "")
        if not name:
            continue
        spec = p.get("spec", "")
        items.append({
            "id": name,                                   # Bring! keys items by name
            "text": f"{name} · {spec}" if spec else name,
            "checked": False,
            "name": name,
            "spec": spec,
            "source": "bring",
        })
    return items


async def _run(action, key=_DEFAULT_KEY):
    import aiohttp
    from bring_api import Bring

    creds = _read_creds()
    if not creds:
        raise RuntimeError("Bring! not configured")
    uuid = list_uuid(key)
    if not uuid:
        raise RuntimeError(f"No Bring! list mapped for '{key}'")
    async with aiohttp.ClientSession() as session:
        bring = Bring(session, creds["email"], creds["password"])
        await bring.login()
        return await action(bring, uuid)


def _sync(action, key=_DEFAULT_KEY):
    return asyncio.run(_run(action, key))


def fetch_items(key: str = _DEFAULT_KEY) -> list:
    """Current 'to buy' items of a list as [{name, spec}]."""
    async def act(bring, uuid):
        resp = await bring.get_list(uuid)
        purchase = getattr(resp.items, "purchase", []) or []
        return [{"name": _item_name(i), "spec": _item_spec(i)} for i in purchase if _item_name(i)]
    return _sync(act, key)


def add_item(name: str, key: str = _DEFAULT_KEY, spec: str = "") -> None:
    async def act(bring, uuid):
        await bring.save_item(uuid, name, spec)
    _sync(act, key)


def complete_item(name: str, key: str = _DEFAULT_KEY) -> None:
    """Mark an item done — it leaves the active (purchase) list."""
    async def act(bring, uuid):
        await bring.complete_item(uuid, name)
    _sync(act, key)


def remove_item(name: str, key: str = _DEFAULT_KEY) -> None:
    async def act(bring, uuid):
        await bring.remove_item(uuid, name)
    _sync(act, key)
