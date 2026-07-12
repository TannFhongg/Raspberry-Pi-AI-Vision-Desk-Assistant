# Project Context

Updated on: 2026-07-12
Project root: `C:\Users\Admin\Desktop\Raspberry Pi AI Vision Desk Assistant`

## Purpose

This repository is a portfolio-ready Raspberry Pi 5 AI vision desk assistant. It is no longer just a single script demo. The codebase now behaves like a small capture appliance with four main control surfaces:

```text
CLI -> shared pipeline
Flask kiosk UI -> shared pipeline
Qt kiosk UI -> shared pipeline
GPIO buttons -> shared pipeline
```

The core flow is:

```text
Camera capture -> OpenCV preprocess / screen optimization -> OpenAI Vision -> readable result
```

## Repo Snapshot

Main top-level areas:

- `ai/`: canonical assistant modes, hidden OpenAI context builder, and the vision client wrapper
- `camera/`: still capture and persistent live-preview helpers
- `config/`: typed YAML-backed device settings loader
- `hardware/`: button, LED, camera-request, state-machine, and diagnostics helpers
- `pipeline/`: shared capture, preprocess, analyze, and latest-result orchestration
- `qt_app/`: native `PySide6 + Qt Quick/QML` frontend runtime, controllers, models, image providers, and QML screens
- `system/`: logging, storage helpers, health monitor, and offline retry queue
- `templates/` and `static/`: touchscreen-first Flask UI
- `vision/`: preprocess pipeline, screen detection, perspective correction, and text enhancement
- `tests/`: automated regression coverage

Main entrypoints:

- `main.py`: full terminal pipeline
- `app.py`: local touchscreen/kiosk UI
- `python -m qt_app.main`: native Qt frontend for the setup/capture/result workflow
- `check_hardware.py`: standalone device diagnostics
- `test_ai_vision.py`: one-off existing-image OpenAI test
- `test_camera_capture.py`: one-off camera capture test
- `test_preprocess.py`: one-off preprocess test
- `test_screen_vision.py`: one-off screen/document optimization test
- `test_gpio_button.py`: standalone GPIO capture trigger

## Current Runtime Architecture

Configuration and shared services:

- `config/settings.py`: loads `config/device.yaml`, applies environment overrides, validates camera/display/button/LED/reliability/retention/retry settings
- `config/device.yaml`: committed hardware baseline for the kiosk device
- `system/logging.py`: rotating `logs/app.log` and `logs/error.log`
- `system/health.py`: background CPU, memory, network, and camera health snapshots
- `system/offline_retry.py`: durable retry queue that keeps copied processed images for transient OpenAI failures
- `system/ui_presenters.py`: canonical progress, result, preview, and health-pill formatting shared by Flask and Qt
- `system/setup_flow.py`: import-safe first-boot setup state, validation, and persistence helpers shared by Flask and Qt
- `system/result_history.py`: shared recent-result storage and decoration helpers used by both UI surfaces

Shared capture stack:

- `camera/capture.py`: OpenCV-only USB webcam capture backend
- `camera/live_preview.py`: live preview service with persistent-preview mode plus Linux snapshot fallback
- `vision/preprocess.py`: base preprocessing plus advanced screen/document path
- `vision/screen_detect.py`: screen/document quadrilateral detection
- `vision/perspective.py`: point ordering and perspective correction
- `vision/enhance_text.py`: denoise, brightness correction, CLAHE contrast, and text sharpening
- `pipeline/runner.py`: canonical `run_capture`, `run_preprocess`, `run_analyze`, `run_capture_analyze`, and `save_latest_result`
- `ai/openai_client.py`: OpenAI Responses API wrapper with explicit timeout, retry, and retryable-error classification

UI and hardware layer:

- `app.py`: Flask kiosk UI state machine, recent-results history, health bar, delete-all-data flow, and offline retry integration
- `qt_app/app_controller.py`: single QML-facing facade for screen navigation, setup, capture, result, and error state
- `qt_app/runtime.py`: shared Qt bootstrap for settings, preview, health, result history, retry queue, and setup stores
- `qt_app/image_provider.py`: in-memory QML image providers for live preview and latest result media
- `hardware/status.py`: shared `READY`, `MODE_SELECTED`, `CAPTURING`, `PROCESSING`, `DONE`, and `ERROR` helpers
- `hardware/button.py`: capture button, mode buttons, and optional back button controller
- `hardware/led.py`: optional single-color LED that mirrors the shared device state
- `gpio/button.py`: compatibility wrapper for the current hardware button controller

## Supported AI Modes

Canonical backend modes from `ai/modes.py`:

- `document_reader`
- `math_solver`
- `meeting_assistant`
- `engineering_mode`
- `general_vision`

Current touch/GPIO presets:

- `read_text` -> `document_reader`
- `summarize_document` -> `document_reader`
- `analyze_image` -> `general_vision`
- `professional_assistant` -> `general_vision`
- `solve_problem` -> `math_solver`

Notes:

- `meeting_assistant` and `engineering_mode` exist today, but they are not exposed as dedicated touchscreen buttons.
- With `SCREEN_OPTIMIZATION=auto`, advanced screen/document optimization is enabled by default for `document_reader`, `math_solver`, and `meeting_assistant`.

## Flask UI Behavior

The Flask app now stores state in local JSON files instead of relying on large Flask sessions.

Current screens:

- `home` without a selected mode: VisionDesk dashboard, mode picker cards, clock, and health pills
- `home` with a selected mode: the same dashboard layout with the chosen mode card highlighted
- `processing`: auto-refreshing progress screen with `Capturing...`, `Processing...`, and `Thinking...`
- `result`: two-panel answer layout with status, current mode, processed preview, answer text, and capture/back actions
- `error`: short classified failure state with retry actions
- `history`: text-only recent result list
- `history_detail`: full text view for one saved result

Important routes:

- `/capture`, `/capture-analyze`, `/analyze`: all currently start the same background `run_capture_analyze` job
- `/camera/live-stream.mjpg`: default live preview stream
- `/camera/live-frame.jpg`: compatibility and diagnostics frame endpoint
- `/api/ui-state`: JSON-safe public device state
- `/api/health`: compact device-health payload
- `/reanalyze`: compatibility route that now fails gracefully because result history is text-only
- `/data/delete-all`: explicit two-step delete-all-data action

Device-state flow:

```text
READY -> MODE_SELECTED -> CAPTURING -> PROCESSING -> DONE | ERROR
```

## Native Qt UI Behavior

The native Qt app is now the parallel migration surface for the primary on-device workflow. Qt v1 currently covers:

- `setup`
- `home`
- `camera`
- `processing`
- `result`
- `error`

Key Qt runtime notes:

- `qt_app.main` talks to shared Python services directly instead of polling `/api/ui-state` or `/api/health`.
- QML image providers are used for the live preview and the latest result preview instead of exposing arbitrary file paths.
- `history` and `history_detail` remain Flask-only during the current migration milestone.

## Current Device Defaults

The committed baseline in `config/device.yaml` currently uses:

- Camera still capture: `1920x1080`
- Live preview: `640x360`, `30 FPS`, `force_mjpeg: true`
- Display: `1200x800` landscape
- Main capture button: GPIO17
- Mode buttons: GPIO5, GPIO6, GPIO13, GPIO19, GPIO26
- Back button: GPIO22
- Local-only Flask host: `127.0.0.1:5000`
- Default AI mode: `document_reader`
- Screen optimization: `auto`
- Offline retry poll interval: `5` seconds
- Retention policy: text history only by default, private working media purged on startup and after success

## Runtime Artifacts

Important generated files and directories:

- `data/latest_result.txt`: latest readable result summary
- `data/ui_state.json`: current kiosk state and selected mode
- `data/result_history.json`: text-only recent results
- `data/ui-previews/`: local-only active result preview for the current answer screen
- `data/health_status.json`: latest health snapshot
- `data/private/current/`: unique per-job working captures and processed images
- `data/private/retry_queue.json`: persisted retry queue metadata
- `data/private/retry/`: copied processed images waiting for background retry
- `data/private/quarantine/`: malformed or legacy artifacts moved aside during recovery
- `debug/`: latest advanced-preprocess debug outputs

## Common Commands

OpenAI test on an existing image:

```bash
python test_ai_vision.py --image test_images/document.jpg --mode document_reader
```

Camera capture:

```bash
python test_camera_capture.py --backend opencv --camera-index 0
```

Preprocess:

```bash
python test_preprocess.py
python test_preprocess.py --grayscale
```

Advanced screen/document optimization:

```bash
python test_screen_vision.py --input test_images/document.jpg --detect-screen --enhance
```

Full terminal pipeline:

```bash
python main.py --mode document_reader
python main.py --mode math_solver
python main.py --mode document_reader --skip-capture --screen-optimization on
```

Flask UI:

```bash
python app.py
```

Native Qt UI:

```bash
pip install -r requirements-qt.txt
python -m qt_app.main --windowed --mock-hardware
python -m qt_app.main
```

Standalone GPIO listener:

```bash
python test_gpio_button.py
```

Device diagnostics:

```bash
python check_hardware.py
```

## Validation Snapshot

Verified on 2026-07-12 in the current local development environment:

- `python -m pytest tests/test_first_boot_setup.py tests/test_app_phase11.py tests/test_qt_deployment_service.py tests/test_qt_app.py -q` -> `63 passed, 4 skipped, 23 subtests passed`

Latest documented real-device behavior from 2026-07-10:

- End-to-end `Read Text` capture succeeded on Raspberry Pi hardware
- GPIO-triggered capture path worked after the live-preview handoff fix
- The kiosk UI displayed recent text-only results and the compact health bar correctly

## Known Limitations And Follow-ups

- Same-image reanalysis is intentionally unavailable while result history remains text-only.
- The offline retry queue has no dedicated queue-management screen yet.
- `history` and `history_detail` are still Flask-only while the native Qt migration focuses on the main capture flow.
- More validation is still needed on the exact target Raspberry Pi hardware for button feel, LED timing, and preview smoothness.
- The current UI is tuned first for a `1200x800` landscape display.
- OpenAI analysis still requires network access and a valid API key.

## Development Guardrails

- Do not commit `.env` or real API keys.
- Keep shared behavior in `pipeline/runner.py` so CLI, Flask, Qt, and GPIO stay aligned.
- Keep UI shaping and setup/history persistence logic in `system/ui_presenters.py`, `system/setup_flow.py`, and `system/result_history.py` so Flask and Qt stay behavior-compatible.
- Keep runtime artifacts out of git.
- Prefer updating `config/device.yaml` for committed hardware defaults and use env vars for deployment-specific overrides.
- Preserve the privacy-first model: result history is text-only by default, working images stay private, and delete-all-data should keep clearing retained user artifacts.
