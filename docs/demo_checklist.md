# Demo Checklist

## Before the demo

- Install dependencies with `pip install -r requirements.txt`
- Start the native app with `python -m qt_app.main --windowed --mock-hardware` for desktop demoing or `python -m qt_app.main` on device
- Confirm `data/latest_result.txt`, `data/result_history.json`, and `data/private/retry_queue.json` are writable
- Confirm the header metrics render and the main window loads at the expected display size

## Core flow to show

- Open `Home`
- Select a mode
- Show the camera preview
- Trigger a capture
- Wait through `Processing`
- Show the final `Result`
- Open `Recent Results`
- Open one `History Detail` item

## Setup flow to show

- Scan nearby Wi-Fi networks
- Connect to Wi-Fi
- Verify an OpenAI key
- Finish setup and explain that the app restarts into the native kiosk flow

## Privacy and reliability talking points

- History is text-only by default
- Retry media stays private under `data/private/`
- `Clear History` and `Delete All Data` are separate actions
- Corrupt persisted history is quarantined and recovered safely
