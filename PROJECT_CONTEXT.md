# Project Context

Updated on: 2026-07-11
Project root: `C:\Users\Admin\Desktop\Raspberry Pi AI Vision Desk Assistant`

## Purpose

This repository is a portfolio-ready Raspberry Pi 5 AI vision desk assistant. It demonstrates a full local hardware and software workflow:

```text
Camera capture -> OpenCV preprocessing / screen optimization -> OpenAI Vision analysis -> CLI / Touchscreen UI / GPIO result
```

The project is organized in phases so each layer can be tested independently and then composed through a shared pipeline.

## Current Architecture

Main entrypoints:

- `main.py`: terminal CLI for full capture, preprocess, and analyze, or for analyzing an existing captured image with `--skip-capture`
- `app.py`: touchscreen-first Flask UI with `home`, `processing`, `result`, `error`, `history`, and `history_detail` screens
- `test_gpio_button.py`: standalone terminal listener for a physical GPIO button that triggers the full pipeline
- `test_ai_vision.py`: one-off OpenAI Vision test using an existing local image
- `test_camera_capture.py`: one-off camera capture test
- `test_preprocess.py`: one-off OpenCV preprocessing test
- `test_screen_vision.py`: one-off long-distance screen/document optimization test with debug outputs

Shared core:

- `pipeline/runner.py`: central orchestration for `run_capture`, `run_preprocess`, `run_analyze`, `run_capture_analyze`, and `save_latest_result`
- `camera/capture.py`: USB webcam capture backend built on OpenCV only
- `vision/preprocess.py`: preprocessing orchestration for both the legacy path and the advanced screen/document optimization path
- `vision/screen_detect.py`: preview-based rectangle detection for screens and documents
- `vision/perspective.py`: quadrilateral ordering, scaling, and four-point perspective correction
- `vision/enhance_text.py`: denoise, brightness correction, CLAHE contrast, and text sharpening
- `ai/openai_client.py`: OpenAI Responses API wrapper for image analysis with friendly app errors
- `system/offline_retry.py`: durable retry queue that stores retryable OpenAI failures and replays them later from private saved processed images
- `ai/modes.py`: canonical assistant mode registry, alias handling, and UI metadata
- `ai/context.py`: hidden backend context builder for mode-specific OpenAI instructions
- `ai/prompts.py`: compatibility shim for older mode/prompt imports
- `hardware/status.py`: shared `READY`, `CAPTURING`, `PROCESSING`, `DONE`, and `ERROR` lifecycle helpers for the UI and hardware flows
- `hardware/button.py`: canonical gpiozero-based short-press capture and long-press clear controller with debounce and duplicate-trigger protection
- `hardware/led.py`: optional single-color GPIO LED indicator that mirrors the shared device lifecycle
- `gpio/button.py`: compatibility wrapper that re-exports the new hardware button controller
- `templates/index.html`: screen-based template for the current landscape touch UI, including live preview, text-only recent results, delete-all-data controls, and queued-retry messaging
- `static/style.css`: kiosk styles optimized for `480x320` landscape, with health pills, live preview emphasis, scrollable answer content, and classified error screens

Runtime artifacts:

- `data/private/current/captured.jpg`: latest temporary camera capture for the active job
- `data/private/current/processed.jpg`: latest temporary preprocessed image for the active job
- `data/private/current/processed.jpg.meta.json`: preprocessing sidecar metadata used for freshness checks
- `debug/`: latest advanced screen/document debug images
- `data/latest_result.txt`: latest readable pipeline result from Flask or standalone GPIO runs
- `data/ui_state.json`: saved UI mode, current screen, `device_state`, status text, and answer/error state
- `data/result_history.json`: saved recent successful assistant results as text-only history
- `data/health_status.json`: latest background health snapshot for CPU, RAM, network, and camera status
- `data/private/retry_queue.json`: persisted metadata for retryable queued AI failures
- `data/private/retry/`: copied processed images waiting for automatic background retry
- `data/private/quarantine/`: malformed or legacy runtime artifacts moved aside during startup/job purge

## Supported AI Modes

Defined in `ai/modes.py`:

- `document_reader`
- `math_solver`
- `meeting_assistant`
- `engineering_mode`
- `general_vision`

Legacy aliases are still accepted:

- `read_text`, `summarize`, `summarize_document` -> `document_reader`
- `solve_problem` -> `math_solver`
- `analyze_image`, `professional_assistant` -> `general_vision`

With `SCREEN_OPTIMIZATION=auto`, the advanced screen/document optimization path is enabled by default only for `document_reader`, `math_solver`, and `meeting_assistant`.

## Web UI Behavior

`app.py` uses a small JSON state file instead of storing large answer payloads in Flask session cookies.

Current touchscreen flow:

- `home` without a selected mode: mode list, direct `Capture` button, and health bar
- `home` with a selected mode: live MJPEG preview, current mode header, health pills, and capture CTA
- `processing`: background capture job status with auto-refresh, simplified centered messaging, and a `Thinking...` state during AI-heavy steps
- `result`: large scrollable answer screen with `Capture Again`, `Recent Results`, and delete-all-data actions
- `result`: answer-first screen that keeps the full answer area visible instead of showing legacy re-analysis UI or GPIO helper copy
- `error`: classified camera/network/API/generic error screen with the same touch-friendly action row
- `history`: recent saved answers list with text-only summaries and retention metadata
- `history_detail`: full saved answer view for a single previous scan without thumbnails or image reuse actions

Interaction notes:

- `/capture`, `/capture-analyze`, and `/analyze` currently all start the same background `run_capture_analyze` workflow
- `/back` returns to `home` while preserving the selected mode
- `/clear` resets the UI to `READY` and clears `data/latest_result.txt`
- `/retry` re-runs the same shared capture workflow for the currently selected mode
- `/camera/live-stream.mjpg` serves the current live preview as an MJPEG stream
- `/reanalyze` remains as a compatibility route but now returns a friendly text-only-retention error instead of reusing saved media
- when the GPIO listener is started inside Flask, short press triggers capture/analyze and long press clears the visible result or error
- the `home`, `result`, and `error` screens auto-refresh while the embedded GPIO listener is active so hardware-triggered state changes appear without manual reload
- retryable OpenAI failures are queued on disk instead of being discarded immediately when the processed image is available
- the local UI exposes a two-step `Delete All Data` action that clears retained text history, retry data, and private runtime media

## Setup Notes

Python package requirements in `requirements.txt`:

- `openai`
- `python-dotenv`
- `pillow`
- `flask`
- `gpiozero`

Important Raspberry Pi OS packages are expected from APT, not pip:

- `python3-opencv`

Recommended venv command on Raspberry Pi:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Environment variables:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4-mini
FLASK_SECRET_KEY=change_this_for_local_flask_sessions
ENABLE_GPIO_BUTTON=1
GPIO_BUTTON_PIN=17
GPIO_BUTTON_DEBOUNCE_SECONDS=0.15
GPIO_BUTTON_HOLD_SECONDS=1.2
ENABLE_GPIO_LED=0
GPIO_LED_PIN=27
GPIO_LED_ACTIVE_HIGH=1
VISION_CAMERA_BACKEND=opencv
VISION_CAMERA_INDEX=0
VISION_CAPTURE_WIDTH=1280
VISION_CAPTURE_HEIGHT=720
VISION_GRAYSCALE=0
VISION_MAX_DIMENSION=1600
SCREEN_OPTIMIZATION=auto
UI_SCREEN_WIDTH=480
UI_SCREEN_HEIGHT=320
UI_DISPLAY_ORIENTATION=landscape
UI_BASE_FONT_SIZE=20
UI_TITLE_FONT_SIZE=34
UI_STATUS_FONT_SIZE=28
UI_BUTTON_FONT_SIZE=24
UI_TOUCH_TARGET=68
UI_PROCESSING_REFRESH_MS=1200
UI_IDLE_REFRESH_MS=2500
LIVE_PREVIEW_FRAME_INTERVAL_MS=80
OFFLINE_RETRY_ENABLED=1
OFFLINE_RETRY_POLL_INTERVAL_SECONDS=30
APP_HOST=127.0.0.1
APP_PORT=5000
FLASK_DEBUG=0
STORE_IMAGES=0
TEXT_HISTORY_MAX_ITEMS=100
TEXT_HISTORY_RETENTION_DAYS=30
RETRY_MEDIA_RETENTION_HOURS=24
PURGE_ON_STARTUP=1
OFFLINE_RETRY_MAX_ITEMS=10
OFFLINE_RETRY_MAX_ATTEMPTS=3
OFFLINE_RETRY_INITIAL_DELAY_SECONDS=30
OFFLINE_RETRY_MAX_DELAY_SECONDS=900
OFFLINE_RETRY_MIN_FREE_MB=128
OFFLINE_RETRY_MAX_STORAGE_MB=512
```

Security note: keep `.env` out of git and keep `.env.example` limited to placeholders only.

## Common Commands

Run OpenAI Vision on an existing image:

```bash
python test_ai_vision.py --image test_images/document.jpg --mode document_reader
```

Capture from camera:

```bash
python test_camera_capture.py --backend opencv --camera-index 0
```

Preprocess latest capture:

```bash
python test_preprocess.py
python test_preprocess.py --grayscale
```

Run advanced screen/document preprocessing:

```bash
python test_screen_vision.py --input test_images/screen_photo.jpg --detect-screen --enhance
```

Run full terminal pipeline:

```bash
python main.py --mode math_solver
python main.py --mode engineering_mode
python main.py --mode general_vision --backend opencv --camera-index 0
python main.py --mode document_reader --skip-capture --screen-optimization on
python main.py --mode document_reader --skip-capture --screen-optimization off
```

Run Flask touchscreen UI:

```bash
python app.py
```

Local URL:

```text
http://127.0.0.1:5000
```

Landscape example:

```bash
UI_SCREEN_WIDTH=480 UI_SCREEN_HEIGHT=320 UI_DISPLAY_ORIENTATION=landscape python app.py
```

Run GPIO button listener:

```bash
python test_gpio_button.py
python test_gpio_button.py --mode document_reader
python test_gpio_button.py --mode general_vision --backend opencv --camera-index 0
```

## Hardware Context

Required or expected hardware:

- Raspberry Pi 5
- USB webcam
- Push button connected to GPIO17 and GND
- Optional LED connected to a configured GPIO pin and GND
- Internet connection for OpenAI API access
- Optional HDMI display, small touchscreen, speaker, buzzer, or power bank for demos

## Deployment

Systemd service template:

- `deployment/ai-vision-assistant.service`

Docs:

- `docs/architecture.md`: current architecture diagram and module notes
- `docs/demo_checklist.md`: demo preparation and flow
- `docs/upwork_project_description.md`: portfolio and freelance-oriented project description
- `hardware_require.txt`: hardware checklist

## Current Worktree State

Observed git status before this file was last updated:

```text
dirty (live preview, recent results, and offline retry improvements present)
```

## Known Limitations And Follow-ups

- Full camera and GPIO behavior still needs real Raspberry Pi hardware verification
- OpenAI analysis requires internet access and a valid API key
- The queued retry worker currently writes recovered answers into latest-result and recent-history storage, but it does not yet surface a dedicated queue-management screen
- Web-triggered actions still funnel into the same full capture and analyze workflow rather than separate capture-only and analyze-only UI paths
- The current UI is tuned first for a `480x320` landscape touchscreen and may need further adjustment for other display sizes
- Exact button feel and LED timing still need final validation on the target Raspberry Pi hardware

## Development Guardrails

- Do not commit `.env` or real secrets
- Do not change `.env.example` placeholders into real values
- Keep shared behavior in `pipeline/runner.py` so CLI, Flask, and GPIO stay consistent
- Keep generated image and result files out of git
- Prefer small, phase-based tests when changing camera, preprocessing, AI, GPIO, or UI state behavior
