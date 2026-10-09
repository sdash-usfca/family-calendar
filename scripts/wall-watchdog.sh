#!/usr/bin/env bash
# wall-watchdog — keep the family wall alive.
#
# Runs every 60s as root (wall-watchdog.timer) and, only when something is
# actually wrong, recovers it:
#   1. Network down          -> bounce WiFi (the drop that once needed a reboot)
#   2. App server not healthy -> restart calboard
#   3. Display frozen         -> reload Chromium (labwc's lwrespawn brings it back)
#   4. BT speaker dropped     -> reconnect the Nest so wall audio has an output
#
# It only speaks up when it acts, so `journalctl -u wall-watchdog` stays quiet
# until something needed fixing.

WIFI_CONN="preconfigured"     # NetworkManager connection name for the built-in WiFi
URL="http://127.0.0.1:8000"
STALE=150                     # seconds with no wall heartbeat = frozen display
MIN_UP=90                     # leave Chromium alone for its first 90s (still loading)

say(){ echo "wall-watchdog: $*"; }

# 1) Internet reachable?
if ! ping -c1 -W2 1.1.1.1 >/dev/null 2>&1 && ! ping -c1 -W2 8.8.8.8 >/dev/null 2>&1; then
  say "no network — bringing WiFi back up"
  nmcli radio wifi on >/dev/null 2>&1
  nmcli connection up "$WIFI_CONN" >/dev/null 2>&1 || nmcli device connect wlan0 >/dev/null 2>&1
  sleep 8
fi

# 2) App server healthy?
HEALTHY=1
if ! curl -fs -m5 "$URL/healthz" >/dev/null 2>&1; then
  say "calboard not responding — restarting service"
  systemctl restart calboard
  HEALTHY=0
  sleep 6
fi

# 3) Is the wall actually rendering? (only judge this once the server is healthy)
if [ "$HEALTHY" = 1 ]; then
  pid=$(pgrep -f -o chromium 2>/dev/null | head -1)
  if [ -n "$pid" ]; then
    up=$(ps -o etimes= -p "$pid" 2>/dev/null | tr -d ' ')
    age=$(curl -fs -m5 "$URL/api/wall_status" 2>/dev/null | grep -o '"age":[-0-9]*' | grep -o '[-0-9]*')
    if [ -n "$up" ] && [ "$up" -ge "$MIN_UP" ] 2>/dev/null; then
      if [ -z "$age" ] || [ "$age" -lt 0 ] 2>/dev/null || [ "$age" -gt "$STALE" ] 2>/dev/null; then
        say "wall frozen (heartbeat age=${age:-none}, chromium up ${up}s) — reloading"
        pkill -f chromium
      fi
    fi
  fi
fi

# 4) Keep the Bluetooth speaker (Nest "Kitchen speaker") connected so the wall's
#    audio has somewhere to go — reconnect if it dropped (idle power-save / reboot).
NEST="48:D6:D5:DD:38:4C"
if ! bluetoothctl info "$NEST" 2>/dev/null | grep -q "Connected: yes"; then
  bluetoothctl connect "$NEST" >/dev/null 2>&1 && say "reconnected Bluetooth speaker"
fi

exit 0
