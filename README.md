# Raspberry Pi AI Vision Desk Assistant

Updated: 2026-07-12

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready Raspberry Pi 5 project that turns a USB webcam, OpenCV preprocessing, OpenAI Vision analysis, Flask, a native `PySide6 + Qt Quick/QML` frontend, and GPIO controls into a small-device capture appliance.

```text
Camera capture -> OpenCV preprocess / screen optimization -> OpenAI Vision -> CLI / Touchscreen UI / GPIO controls
```

## Current Status

- End-to-end capture, preprocess, analyze, and result display flows are implemented across CLI, Flask, Qt, and GPIO entrypoints.
- The committed device baseline is now a local-only kiosk profile on `127.0.0.1:5000` with a `1200x800` landscape UI.
- A mandatory first-boot setup wizard now blocks the normal kiosk flow until Wi-Fi, `OPENAI_API_KEY`, camera diagnostics, and GPIO verification have been reviewed.
- The current default hardware profile uses `1920x1080` still capture, a lighter `640x360` live preview, text-only result history, private runtime media, and a background offline retry queue.
- Physical controls support one capture button, five mode buttons, an optional back button, and an optional single-color status LED.
- Targeted shared-plus-Qt validation on 2026-07-12: `python -m pytest tests/test_first_boot_setup.py tests/test_app_phase11.py tests/test_qt_deployment_service.py tests/test_qt_app.py -q` completed with `63 passed, 4 skipped, 23 subtests passed`.
- Latest documented on-device validation on 2026-07-10: the `Read Text` flow captured a Raspberry Pi 27W USB-C power supply box, returned structured OCR-style output, and confirmed the fixed live-preview-to-capture handoff on the GPIO-triggered path.

## Milestone Snapshot

- Phase 1-4: OpenAI image analysis, USB camera capture, preprocessing, and the shared CLI pipeline are in place.
- Phase 5-6: Flask touchscreen UI and GPIO-triggered capture are integrated around the same pipeline runner.
- Phase 8-9: device diagnostics and long-distance screen/document optimization are implemented.
- Phase 10-11: production-oriented landscape kiosk UI, live preview, and the shared hardware state machine are implemented.
- Phase 13-15: assistant mode registry, reliability/logging/health monitoring, recent results, offline retry, and privacy hardening are implemented.
- Phase 16: first-boot setup gating, YAML-backed setup metadata, `.env` key upsert, Wi-Fi onboarding via `nmcli`, and setup-specific GPIO verification are implemented.

## What Works Today

- `main.py` runs the full camera -> preprocess -> OpenAI workflow from the terminal.
- `app.py` exposes a touchscreen-first Flask UI with `setup`, `home`, `processing`, `result`, `error`, `history`, and `history_detail` screens.
- `qt_app/` now contains the native `PySide6 + Qt Quick/QML` app for `setup`, `home`, `camera`, `processing`, `result`, and `error`, backed by shared Python services instead of HTTP UI polling.
- `test_gpio_button.py` and the embedded Flask GPIO listener both trigger the same shared capture pipeline.
- Live framing is available through `/camera/live-stream.mjpg`, with `/camera/live-frame.jpg` kept as a diagnostic and compatibility endpoint.
- Compact device-health data is available through `/api/health`, and the UI state is exposed through `/api/ui-state`.
- Setup state is exposed through `/api/setup-state`, and the local UI can reopen the wizard later from `/admin/setup`.
- Recent successful results are stored as text-only history in `data/result_history.json`.
- Retryable OpenAI failures can be queued in `data/private/retry_queue.json` and replayed automatically from copied processed images in `data/private/retry/`.
- Private working images are isolated under `data/private/current/` and are purged after successful jobs by default.
- The local UI exposes a two-step `Delete All Data` action that clears text history, queued retry media, temp media, and quarantined leftovers.
- Rotating logs and background health snapshots are written to `logs/` and `data/health_status.json`.
- `OPENAI_API_KEY` persistence is handled by atomic `.env` updates, while `config/device.yaml` stores only non-secret setup status and Wi-Fi metadata.

## Project Structure

```text
raspberry-pi-ai-vision-assistant/
|-- ai/
|-- camera/
|-- config/
|-- data/
|-- debug/
|-- deployment/
|-- docs/
|-- gpio/
|-- hardware/
|-- pipeline/
|-- qt_app/
|-- static/
|-- system/
|-- templates/
|-- tests/
|-- vision/
|-- app.py
|-- check_hardware.py
|-- main.py
|-- PROJECT_CONTEXT.md
|-- README.md
|-- requirements.txt
|-- requirements-qt.txt
|-- test_ai_vision.py
|-- test_camera_capture.py
|-- test_gpio_button.py
|-- test_preprocess.py
`-- test_screen_vision.py
```

Key directories:

- `ai/`: canonical assistant modes, hidden per-mode context, and the OpenAI client wrapper
- `camera/`: USB webcam capture and live preview services
- `config/`: typed settings loader plus the committed `config/device.yaml` baseline
- `hardware/`: button, LED, camera request, setup GPIO verifier, device-state, and diagnostics helpers
- `pipeline/`: shared capture, preprocess, analyze, and result-writing orchestration
- `qt_app/`: native Qt runtime, controllers, QML screens, and image providers for the v1 migration
- `system/`: logging, storage helpers, first-boot setup helpers, health monitor, and offline retry queue
- `templates/` and `static/`: the kiosk-oriented Flask UI
- `vision/`: preprocessing, screen detection, perspective correction, and text enhancement
- `tests/`: regression coverage for settings, first-boot setup, UI behavior, reliability, live preview, GPIO, and pipeline logic

## Setup

### Raspberry Pi OS packages

Install the OS-level dependencies first:

```bash
sudo apt update
sudo apt install -y python3-opencv chromium-browser
```

### Virtual environment

Use system site packages so the APT-installed `cv2` module is available inside the venv:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### First boot flow

On a new device, you can start either UI surface locally:

```bash
python app.py
python -m qt_app.main
```

Both runtimes gate unfinished devices into setup automatically. In the Flask surface this appears at `/setup`. The V1 setup wizard:

- scans and connects Wi-Fi through `nmcli`
- saves `OPENAI_API_KEY` into local `.env`
- runs a lightweight camera diagnostic while showing the live preview
- verifies the configured GPIO buttons once each
- finishes with warning acknowledgment and then either restarts the Flask process or exits the Qt app for relaunch

When the native Qt app completes setup, it exits cleanly and expects systemd or a manual relaunch to bring the normal runtime back up.

V1 keeps the locale fixed to English. Wi-Fi passwords are applied to the OS through NetworkManager and are not stored in `config/device.yaml`.

### Minimum `.env`

Copy `.env.example` to `.env` if you want to pre-seed values before first boot. At minimum:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4-mini
FLASK_SECRET_KEY=change_this_for_local_flask_sessions
```

If `.env` does not already contain a real `OPENAI_API_KEY`, the first-boot wizard will ask for one and save it atomically while preserving unrelated keys and comments.

Most runtime defaults now come from [config/device.yaml](config/device.yaml). Runtime precedence is:

```text
config/device.yaml -> environment variables -> CLI flags
```

### Current device baseline

The committed hardware baseline in [config/device.yaml](config/device.yaml) currently resolves to:

```yaml
camera:
  backend: opencv
  index: 0
  resolution:
    width: 1920
    height: 1080
  preview:
    resolution:
      width: 640
      height: 360
    target_fps: 30.0
    force_mjpeg: true
  autofocus_mode: continuous
  exposure: auto
  brightness: 0.0
  capture_delay_seconds: 1.0
  grayscale: false
  max_dimension: 1600

display:
  size:
    width: 1200
    height: 800
  orientation: landscape

button:
  enabled: true
  pin: 17
  mode_button_1_pin: 5
  mode_button_2_pin: 6
  mode_button_3_pin: 13
  mode_button_4_pin: 19
  mode_button_5_pin: 26
  back_button_pin: 22

app:
  host: 127.0.0.1
  port: 5000
  debug: false

ai:
  default_mode: document_reader

vision:
  screen_optimization: auto

startup:
  behavior: kiosk
  url: http://127.0.0.1:5000

setup:
  completed: true
  completed_at: "2026-07-11T00:00:00"
  version: 1

network:
  wifi:
    ssid: ""
    connection_name: ""
    auto_connect: true
    managed_by: nmcli

localization:
  locale: en

offline_retry:
  enabled: true
  max_items: 10
  max_attempts: 3
  initial_delay_seconds: 30.0
  max_delay_seconds: 900.0
  poll_interval_seconds: 5.0
```

Useful override knobs:

- `VISION_CAPTURE_WIDTH`, `VISION_CAPTURE_HEIGHT`
- `LIVE_PREVIEW_WIDTH`, `LIVE_PREVIEW_HEIGHT`, `LIVE_PREVIEW_TARGET_FPS`
- `LIVE_PREVIEW_FORCE_MJPEG`, `LIVE_PREVIEW_FORCE_POLLING`
- `ENABLE_GPIO_BUTTON`, `CAPTURE_BUTTON_PIN`, `MODE_BUTTON_1_PIN` through `MODE_BUTTON_5_PIN`, `BACK_BUTTON_PIN`
- `ENABLE_GPIO_LED`, `GPIO_LED_PIN`, `GPIO_LED_ACTIVE_HIGH`
- `SCREEN_OPTIMIZATION`
- `DEVICE_CONFIG_PATH`
- `STORE_IMAGES`, `TEXT_HISTORY_MAX_ITEMS`, `PURGE_ON_STARTUP`
- `OFFLINE_RETRY_ENABLED`, `OFFLINE_RETRY_POLL_INTERVAL_SECONDS`

## Assistant Modes

Canonical backend modes:

- `document_reader`
- `math_solver`
- `meeting_assistant`
- `engineering_mode`
- `general_vision`

Current touchscreen and GPIO presets:

- `read_text` -> `document_reader`
- `summarize_document` -> `document_reader`
- `analyze_image` -> `general_vision`
- `professional_assistant` -> `general_vision`
- `solve_problem` -> `math_solver`

`meeting_assistant` and `engineering_mode` are currently available from the CLI and backend layers, but they do not have dedicated touchscreen buttons in the present kiosk UI.

With `SCREEN_OPTIMIZATION=auto`, the advanced screen/document optimization path is enabled by default for `document_reader`, `math_solver`, and `meeting_assistant`.

## Common Commands

### OpenAI Vision on an existing image

```bash
python test_ai_vision.py --image test_images/document.jpg --mode document_reader
python test_ai_vision.py --image test_images/math_problem.jpg --mode math_solver
```

### Camera capture only

```bash
python test_camera_capture.py --backend opencv --camera-index 0
python test_camera_capture.py --backend opencv --camera-index 0 --width 1920 --height 1080 --autofocus-mode continuous
```

### Preprocess the latest capture

```bash
python test_preprocess.py
python test_preprocess.py --grayscale
```

### Run the advanced screen/document flow

```bash
python test_screen_vision.py --input test_images/document.jpg --detect-screen --enhance
```

Debug outputs are written to:

```text
debug/original.jpg
debug/detected_screen.jpg
debug/corrected.jpg
debug/enhanced.jpg
```

### Full terminal pipeline

```bash
python main.py --mode document_reader
python main.py --mode math_solver
python main.py --mode general_vision --backend opencv --camera-index 0
python main.py --mode engineering_mode
```

### Full pipeline without a live capture

```bash
cp test_images/math_problem.jpg data/private/current/captured.jpg
python main.py --mode math_solver --skip-capture
python main.py --mode document_reader --skip-capture --screen-optimization on
python main.py --mode document_reader --skip-capture --screen-optimization off
```

### Flask touchscreen UI

```bash
python app.py
```

Local URL:

```text
http://127.0.0.1:5000
```

### Standalone GPIO listener

```bash
python test_gpio_button.py
python test_gpio_button.py --mode document_reader
python test_gpio_button.py --mode general_vision
```

### Device diagnostics

```bash
python check_hardware.py
```

### Native Qt UI preview

Install the extra UI dependencies once:

```bash
pip install -r requirements-qt.txt
```

Run the native Qt app in a desktop window:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Run against real hardware and use fullscreen by default:

```bash
python -m qt_app.main
```

## Web and Hardware Flow

The first-boot gate now sits in front of the normal device state machine:

```text
SETUP_REQUIRED -> setup wizard -> restart -> READY -> MODE_SELECTED -> CAPTURING -> PROCESSING -> DONE | ERROR
```

Once setup is complete, the current shared device state machine is:

```text
READY -> MODE_SELECTED -> CAPTURING -> PROCESSING -> DONE | ERROR
```

Current UI behavior:

- `setup`: mandatory first-boot wizard for Wi-Fi, API key, camera check, GPIO verification, warning review, and restart
- `home` without a selected mode: shows the VisionDesk dashboard, five touch modes, the large clock, and the health pills
- `home` with a selected mode: keeps the same dashboard layout, highlights the selected mode card, and waits for the main capture trigger
- `processing`: auto-refreshing progress view with `Capturing...`, `Processing...`, and `Thinking...`
- `result`: a two-panel answer screen with status, current mode, processed preview, answer text, `Capture Again`, and `Back`
- `error`: short classified camera/network/API/generic failure screen with retry actions
- `history` and `history_detail`: recent text-only results without retained source images

Qt v1 notes:

- `qt_app.main` does not open an HTTP port for UI state or health polling in normal operation.
- The Qt app reuses shared Python presenters, setup helpers, and result-history helpers directly.
- `history` and `history_detail` remain Flask-only in the current migration milestone.

Route notes:

- `/setup`: mandatory first-boot wizard screen
- `/api/setup-state`: persisted setup progress for the setup UI
- `/setup/wifi/scan`, `/setup/wifi/connect`, `/setup/openai-key`, `/setup/camera/test`, `/setup/gpio/test/start`, `/setup/gpio/test/stop`, `/setup/finish`: setup workflow endpoints
- `/admin/setup`: local wizard re-entry after the device has already been configured
- `/capture`, `/capture-analyze`, and `/analyze` currently all start the same background `run_capture_analyze` workflow
- `/camera/live-stream.mjpg` is the default browser preview path
- `/camera/live-frame.jpg` is kept for diagnostics and stream-fallback compatibility
- `/api/ui-state` and `/api/health` provide compact device state for the kiosk UI
- `/reanalyze` is intentionally kept as a compatibility route, but it now fails gracefully because text-only retention does not keep source images for same-image reanalysis

Physical controls:

- `Button Main`: short press captures, long press clears the current result or error
- `Button 1`: `Read Text`
- `Button 2`: `Summarize Document`
- `Button 3`: `Analyze Image`
- `Button 4`: `Professional Assistant`
- `Button 5`: `Solve Problem`
- `Back Button` on GPIO22: returns to mode selection when the device is idle

Optional LED behavior:

- `READY` and `DONE`: solid on
- `CAPTURING`: slow blink
- `PROCESSING`: medium blink
- `ERROR`: fast blink

## Storage and Reliability

User-facing and runtime artifacts:

- `data/latest_result.txt`: latest readable result summary
- `data/ui_state.json`: persisted UI mode, screen, and device state
- `data/setup_state.json`: persisted partial first-boot wizard progress
- `data/result_history.json`: text-only recent result history
- `data/ui-previews/`: local-only active result preview used by the answer screen
- `data/health_status.json`: latest background health snapshot
- `data/private/current/`: per-job working capture and processed files
- `data/private/retry_queue.json`: persisted queue metadata for retryable OpenAI failures
- `data/private/retry/`: copied processed images waiting for background retry
- `data/private/quarantine/`: malformed or unsafe artifacts moved aside during recovery
- `logs/app.log` and `logs/error.log`: rotating runtime logs
- `.env`: the only persisted app-side storage for `OPENAI_API_KEY`
- `config/device.yaml`: committed hardware defaults plus non-secret setup completion and Wi-Fi metadata

Reliability behavior:

- OpenAI requests use explicit timeout, retry-count, and exponential-backoff settings.
- Health monitoring writes periodic snapshots for CPU, memory, network, and camera status.
- The normal GPIO listener, health monitor, and offline retry worker stay disabled until first-boot setup is completed.
- Camera probes are deferred while live preview, capture, or processing is active.
- Successful jobs purge private working media by default.
- Retryable OpenAI failures are queued instead of being lost immediately when the processed image is available.
- `Delete All Data` clears retained text history, retry data, temp media, and quarantined leftovers.

## Deployment

The project ships with:

- [deployment/ai-vision-assistant.service](deployment/ai-vision-assistant.service)
- [deployment/visiondesk-qt.service](deployment/visiondesk-qt.service)
- [deployment/kiosk-launch.sh](deployment/kiosk-launch.sh)
- [deployment/labwc-autostart.example](deployment/labwc-autostart.example)

Systemd setup:

```bash
sudo cp deployment/ai-vision-assistant.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ai-vision-assistant.service
sudo systemctl start ai-vision-assistant.service
sudo systemctl status ai-vision-assistant.service
journalctl -u ai-vision-assistant.service -f
```

For fullscreen kiosk startup on Raspberry Pi OS Bookworm with `labwc`:

1. Copy `deployment/labwc-autostart.example` to `~/.config/labwc/autostart`
2. Update the repo path in that file if needed
3. Make `deployment/kiosk-launch.sh` executable
4. Reboot and verify Chromium opens `http://127.0.0.1:5000`

To switch the device to the native Qt kiosk service instead:

```bash
sudo cp deployment/visiondesk-qt.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl disable --now ai-vision-assistant.service
sudo systemctl enable --now visiondesk-qt.service
sudo systemctl status visiondesk-qt.service
journalctl -u visiondesk-qt.service -f
```

Qt v1 Raspberry Pi validation checklist:

- confirm the app opens fullscreen at `1200x800`
- verify the live preview keeps the expected aspect ratio on the camera and setup screens
- test capture, retry, and back actions from both touch and GPIO buttons
- confirm setup completion exits the process and that systemd relaunches it cleanly
- confirm no API keys or Wi-Fi passwords appear in the visible UI or logs

## Troubleshooting

### Missing `OPENAI_API_KEY`

- Complete the `/setup` wizard or reopen it from `/admin/setup`
- Add the key to `.env` manually only if you are bypassing the wizard for local development
- Restart `python app.py` or rerun the CLI command

### Wi-Fi setup fails in the wizard

- Confirm NetworkManager and `nmcli` are installed and available on the device
- Verify the SSID and password, especially for hidden networks entered manually
- Check whether the OS can connect outside the app with `nmcli device wifi list`

### OpenCV import or camera failure

- Install `python3-opencv`
- Recreate the venv with `--system-site-packages`
- Run `python check_hardware.py`
- Close other software that may be holding the webcam

### OpenAI request failure

- Verify API key and model access
- Check internet connectivity on the Pi
- If offline retry is enabled, retryable failures are queued automatically when processed media is available

### Touch UI does not fit the display

- Adjust `display.size.width`, `display.size.height`, or `display.orientation` in `config/device.yaml`
- Tune `UI_BASE_FONT_SIZE`, `UI_BUTTON_FONT_SIZE`, and `UI_TOUCH_TARGET`

### GPIO is unavailable

- Confirm you are on a Raspberry Pi with a real pin factory
- Confirm the configured pins are wired to `GND`
- Re-run `python check_hardware.py`

## Known Limitations

- Same-image reanalysis is intentionally unavailable while result history remains text-only.
- The offline retry queue does not yet have a dedicated management screen.
- `/admin/setup` is intentionally unprotected in V1 and is meant only for trusted local device access.
- The V1 setup wizard keeps locale fixed to English and does not yet expose language selection.
- Final button feel, live-preview smoothness, and LED timing still need more validation on the exact target Raspberry Pi hardware.
- The current UI is tuned first for a `1200x800` landscape touchscreen and may need further work for other display sizes.
- OpenAI analysis still requires internet access and a valid API key.

## Related Docs

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
- [docs/architecture.md](docs/architecture.md)
- [docs/demo_checklist.md](docs/demo_checklist.md)
- [docs/upwork_project_description.md](docs/upwork_project_description.md)
