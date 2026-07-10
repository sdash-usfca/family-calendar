"""Flask app: renders the wall dashboard and serves the agenda as JSON."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, make_response, render_template

from ..calendars import get_events
from ..config import Config, load_config


def create_app(config: Optional[Config] = None) -> Flask:
    config = config or load_config()
    app = Flask(__name__)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
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
        return jsonify({
            "now": now.isoformat(),
            "timezone": config.timezone,
            "whats_next_count": config.whats_next_count,
            "events": [e.to_dict() for e in events],
        })

    @app.route("/healthz")
    def healthz():
        return jsonify({"ok": True})

    return app
