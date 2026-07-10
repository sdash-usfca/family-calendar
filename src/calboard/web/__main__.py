"""Entry point: `calboard-web` (or `python -m calboard.web`)."""
from __future__ import annotations

from ..config import load_config
from .app import create_app


def main() -> None:
    config = load_config()
    app = create_app(config)
    app.run(host=config.web.host, port=config.web.port, threaded=True)


if __name__ == "__main__":
    main()
