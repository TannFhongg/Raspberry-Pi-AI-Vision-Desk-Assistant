#!/usr/bin/env bash
set -eu

APP_URL="${STARTUP_URL:-http://localhost:5000}"
WAIT_TIMEOUT_SECONDS="${KIOSK_WAIT_TIMEOUT_SECONDS:-60}"

if command -v chromium >/dev/null 2>&1; then
  BROWSER_BIN="chromium"
elif command -v chromium-browser >/dev/null 2>&1; then
  BROWSER_BIN="chromium-browser"
else
  echo "Chromium was not found in PATH." >&2
  exit 1
fi

if ! python3 - "$APP_URL" "$WAIT_TIMEOUT_SECONDS" <<'PY'
import sys
import time
import urllib.error
import urllib.request

url = sys.argv[1]
timeout_seconds = float(sys.argv[2])
deadline = time.monotonic() + timeout_seconds

while time.monotonic() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            if 200 <= response.status < 500:
                sys.exit(0)
    except (urllib.error.URLError, TimeoutError):
        time.sleep(1)

sys.exit(1)
PY
then
  echo "Timed out waiting for $APP_URL before launching Chromium." >&2
  exit 1
fi

exec "$BROWSER_BIN" \
  --kiosk \
  --app="$APP_URL" \
  --noerrdialogs \
  --disable-infobars \
  --no-first-run \
  --start-maximized
