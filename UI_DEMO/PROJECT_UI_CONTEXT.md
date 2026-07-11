# Project UI Context

This document summarizes the current UI context of the project so the demo screenshots stay aligned with the real app.

## Product summary

VisionDesk is a Raspberry Pi 5 AI vision desk assistant that turns a webcam capture into a readable answer through a shared pipeline:

```text
Camera capture -> OpenCV preprocess -> OpenAI Vision -> Result screen
```

The repository currently supports three control surfaces:

- CLI
- Flask touchscreen UI
- GPIO hardware buttons

## Current screen model

The kiosk UI currently uses these major user-facing screens:

- `home`
- `camera`
- `processing`
- `result`
- `error`
- `history`
- `history_detail`
- `setup`

For the screenshot pack in `UI_DEMO`, the most important flow is:

```text
home -> camera -> processing -> result
```

## Current UI modes

Touchscreen mode options defined in [`app.py`](../app.py):

- `read_text` -> `Read Text` -> internal mode `document_reader`
- `summarize_document` -> `Summarize Document` -> internal mode `document_reader`
- `analyze_image` -> `Analyze Image` -> internal mode `general_vision`
- `professional_assistant` -> `Professional Assistant` -> internal mode `general_vision`
- `solve_problem` -> `Solve Problem` -> internal mode `math_solver`

## Current device profile

The committed kiosk profile is currently:

- Raspberry Pi 5
- 11-inch HDMI touchscreen
- `1200x800` landscape layout
- local-only host at `127.0.0.1:5000`
- live preview through `/camera/live-stream.mjpg`

## UI implementation notes

- The current app renders the kiosk through [`templates/index.html`](../templates/index.html).
- Styling lives mainly in [`static/style.css`](../static/style.css).
- Public UI synchronization happens through `/api/ui-state`.
- Header health pills are driven by `/api/health`.
- The current result preview image is served from `/result-preview/latest.jpg`.

## State and persistence

The UI is backed by local JSON and text artifacts, not large browser session state.

Important runtime files:

- `data/ui_state.json`
- `data/latest_result.txt`
- `data/result_history.json`
- `data/health_status.json`

Private working media stays under:

- `data/private/current/`
- `data/private/retry/`
- `data/private/retry_queue.json`

## Privacy and demo constraints

- The app is intentionally local-only.
- Captured working images should not be exposed under `static/`.
- Recent history is text-first, not a public image gallery.
- Retryable OpenAI failures can be queued for later retry instead of being lost.
- Demo screenshots should represent real UI state, not fake status badges.

## Useful source references

- [`README.md`](../README.md)
- [`PROJECT_CONTEXT.md`](../PROJECT_CONTEXT.md)
- [`docs/architecture.md`](../docs/architecture.md)
- [`docs/demo_checklist.md`](../docs/demo_checklist.md)
