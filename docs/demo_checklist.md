# Demo Checklist

## Before the demo

- create and activate `.venv`, then install dependencies with `python -m pip install -r requirements.txt`
- set `OPENAI_API_KEY` in the ignored `.env` only when demonstrating live analysis; `OPENAI_MODEL` and `DEVICE_CONFIG_PATH` are optional in development
- start the native app with `python -m qt_app.main --windowed --mock-hardware` for desktop demoing or use `visiondesk.service` on an installed device
- confirm `data/latest_result.txt`, `data/result_history.json`, and `data/private/retry_queue.json` are writable in development
- if demoing an installed appliance, confirm `/var/lib/visiondesk/latest_result.txt`, `/var/lib/visiondesk/result_history.json`, and `/var/lib/visiondesk/private/retry_queue.json` are writable
- confirm the header metrics render and the main window loads at the expected display size

## Core flow to show

- open `Home`
- select a mode
- show the camera preview
- trigger a capture
- wait through `Processing`
- show the final `Result`
- open `Recent Results`
- open one `History Detail` item

## Setup flow to show

- show the welcome/device-check step
- scan nearby Wi-Fi networks
- connect to Wi-Fi
- verify an OpenAI key
- run the camera test
- run the GPIO test
- finish setup and explain that the app restarts directly into the native kiosk flow
- explain that a candidate OpenAI key is verified before it is saved and no raw or masked key is exposed to QML

## Privacy and reliability talking points

- history is text-only by default
- retry media stays private under the shared private storage tree
- `Clear History`, `User-Data Reset`, `Configuration Reset`, and `Full Factory Reset` are separate actions
- corrupt persisted setup or history state is quarantined and recovered safely
- production secrets live in `/etc/visiondesk/visiondesk.env`; user data lives under `/var/lib/visiondesk/`
- an appliance update succeeds only after a fresh readiness marker matches the release and its service stays stable; otherwise it rolls back
