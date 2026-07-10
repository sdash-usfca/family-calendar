#!/usr/bin/env bash
# Run the wall calendar locally with sample events. Ctrl-C stops it.
set -euo pipefail
[ -f config.yaml ] || cp config.example.yaml config.yaml
calboard-web
# open http://localhost:8000
