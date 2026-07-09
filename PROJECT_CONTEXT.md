# Project Context

Updated on: 2026-07-09
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
- `app.py`: touchscreen-first Flask UI with `home`, `mode_select`, `processing`, `result`, and `error` screens
- `test_gpio_button.py`: standalone terminal listener for a physical GPIO button that triggers the full pipeline
- `test_ai_vision.py`: one-off OpenAI Vision test using an existing local image
- `test_camera_capture.py`: one-off camera capture test
- `test_preprocess.py`: one-off OpenCV preprocessing test
- `test_screen_vision.py`: one-off long-distance screen/document optimization test with debug outputs

Shared core:

- `pipeline/runner.py`: central orchestration for `run_capture`, `run_preprocess`, `run_analyze`, `run_capture_analyze`, and `save_latest_result`
- `camera/capture.py`: camera abstraction with `auto`, `picamera2`, and `opencv` backends. Auto tries Picamera2 first, then OpenCV
- `vision/preprocess.py`: preprocessing orchestration for both the legacy path and the advanced screen/document optimization path
- `vision/screen_detect.py`: preview-based rectangle detection for screens and documents
- `vision/perspective.py`: quadrilateral ordering, scaling, and four-point perspective correction
- `vision/enhance_text.py`: denoise, brightness correction, CLAHE contrast, and text sharpening
- `ai/openai_client.py`: OpenAI Responses API wrapper for image analysis with friendly app errors
- `ai/prompts.py`: supported mode definitions, alias handling, and prompt builder
- `gpio/button.py`: gpiozero-based button trigger with a busy flag to avoid overlapping pipeline runs
- `templates/index.html`: screen-based template for the current Phase 10 touch UI
- `static/style.css`: portrait-first kiosk styles optimized for `320x480`, with large touch targets, scrollable answer content, and classified error screens

Runtime artifacts:

- `static/captured.jpg`: latest camera capture
- `static/processed.jpg`: latest preprocessed image
- `static/processed.jpg.meta.json`: preprocessing sidecar metadata used for freshness checks
- `debug/`: latest advanced screen/document debug images
- `data/latest_result.txt`: latest readable pipeline result from Flask or standalone GPIO runs
- `data/ui_state.json`: saved UI mode, current screen, status text, and answer/error state

## Supported AI Modes

Defined in `ai/prompts.py`:

- `read_text`
- `summarize`
- `summarize_document`
- `solve_problem`
- `analyze_image`
- `professional_assistant`

`summarize` is an alias for `summarize_document`.

With `SCREEN_OPTIMIZATION=auto`, the advanced screen/document optimization path is enabled by default only for `read_text`, `summarize_document`, and `solve_problem`.

## Web UI Behavior

`app.py` uses a small JSON state file instead of storing large answer payloads in Flask session cookies.

Current touchscreen flow:

- `home`: ready screen with current mode, status, and large `Capture`, `Mode`, and `Retry` buttons
- `mode_select`: dedicated mode picker that saves the chosen mode and returns to home
- `processing`: background capture job status with auto-refresh, simplified centered messaging, and a `Thinking...` state during AI-heavy steps
- `result`: large scrollable answer screen with persistent `Capture`, `Mode`, and `Retry` buttons
- `error`: classified camera/network/API/generic error screen with the same touch-friendly action row

Interaction notes:

- `/capture`, `/capture-analyze`, and `/analyze` currently all start the same background `run_capture_analyze` workflow
- `/back` and `/clear` both reset the UI to `home` while preserving the selected mode
- `/retry` re-runs the same shared capture workflow for the currently selected mode
- when the GPIO listener is started inside Flask, a physical button press reuses the same capture job as the touch UI
- the home screen auto-refreshes while the embedded GPIO listener is active so hardware-triggered state changes appear without manual reload

## Setup Notes

Python package requirements in `requirements.txt`:

- `openai`
- `python-dotenv`
- `pillow`
- `flask`
- `gpiozero`

Important Raspberry Pi OS packages are expected from APT, not pip:

- `python3-picamera2`
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
VISION_CAMERA_BACKEND=auto
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
```

Security note: keep `.env` out of git and keep `.env.example` limited to placeholders only.

## Common Commands

Run OpenAI Vision on an existing image:

```bash
python test_ai_vision.py --image test_images/document.jpg --mode summarize_document
```

Capture from camera:

```bash
python test_camera_capture.py --backend auto
python test_camera_capture.py --backend picamera2
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
python main.py --mode solve_problem
python main.py --mode analyze_image
python main.py --mode read_text --backend picamera2
python main.py --mode professional_assistant --backend opencv --camera-index 0
python main.py --mode read_text --skip-capture --screen-optimization on
python main.py --mode read_text --skip-capture --screen-optimization off
```

Run Flask touchscreen UI:

```bash
python app.py
```

Local URL:

```text
http://127.0.0.1:5000
```

Portrait example:

```bash
UI_SCREEN_WIDTH=320 UI_SCREEN_HEIGHT=480 UI_DISPLAY_ORIENTATION=portrait python app.py
```

Run GPIO button listener:

```bash
python test_gpio_button.py
python test_gpio_button.py --mode read_text
python test_gpio_button.py --mode professional_assistant --backend picamera2
```

## Hardware Context

Required or expected hardware:

- Raspberry Pi 5
- Raspberry Pi Camera Module, Arducam CSI camera, or USB webcam
- Push button connected to GPIO17 and GND
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
dirty (Phase 10 touchscreen UI and documentation updates present)
```

## Known Limitations And Follow-ups

- Full camera and GPIO behavior still needs real Raspberry Pi hardware verification
- OpenAI analysis requires internet access and a valid API key
- The touch UI does not currently show live camera preview or captured/processed image thumbnails
- Web-triggered actions currently funnel into the same full capture and analyze workflow
- Only the latest result and UI state are stored; there is no history view yet
- Phase 10 is tuned first for a `320x480` portrait touchscreen and may need further adjustment for other display sizes
- A fuller background job queue would improve resilience for slow network or model responses

## Development Guardrails

- Do not commit `.env` or real secrets
- Do not change `.env.example` placeholders into real values
- Keep shared behavior in `pipeline/runner.py` so CLI, Flask, and GPIO stay consistent
- Keep generated image and result files out of git
- Prefer small, phase-based tests when changing camera, preprocessing, AI, GPIO, or UI state behavior
