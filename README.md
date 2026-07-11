# Raspberry Pi AI Vision Desk Assistant

## Project Overview

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready Raspberry Pi 5 project that demonstrates a full local AI vision workflow:

```text
Camera Capture -> OpenCV Preprocessing / Screen Optimization -> OpenAI Vision Analysis -> CLI / Touchscreen UI / GPIO Trigger
```

The project is organized in phases so each layer can be tested independently and then combined into a single shared pipeline.

## Portfolio Snapshot

- Built an embedded AI assistant on Raspberry Pi 5 that combines camera capture, OpenCV preprocessing, OpenAI vision analysis, touchscreen UI, and GPIO hardware controls in one shared workflow
- Designed the interface for a compact `480x320` landscape touchscreen with live MJPEG preview, device health pills, background processing states, recent-result recall, and a scrollable answer view
- Structured the codebase like a deployable product instead of a one-off demo, with shared pipeline orchestration, persisted UI state, rotating logs, health monitoring, hardware-safe busy-state handling, and an offline retry queue for transient AI failures

## Validated Results

Validated on July 10, 2026:

- The `READY` screen renders correctly on the target landscape touchscreen and exposes 5 assistant modes: `Read Text`, `Summarize Document`, `Analyze Image`, `Professional Assistant`, and `Solve Problem`
- The `Read Text` flow successfully captured and analyzed a Raspberry Pi 27W USB-C power supply box and returned structured content including product name, product link, mixed-language label text, input range, output rails, and max power
- The physical capture path triggered from `GPIO17` now works end-to-end after fixing the live-preview-to-capture camera handoff race that previously surfaced as `Camera disconnected`
- The compact answer screen was refined for readability by reducing the response font size by 35 percent so longer OCR and AI outputs fit better on the device display
- The live preview now streams over MJPEG for smoother on-device framing instead of browser-side image polling
- Successful analyses are now available again through `Recent Results`, backed by RAM cache plus persisted history on disk
- Recent results now render as a thumbnail gallery in RAM so old scans can be reopened with faster visual recognition
- The result screen can now re-analyze the same saved image in a different assistant mode without taking another photo
- The main result view now gives more room to `Answer` by removing the on-screen GPIO re-analyze hint and tightening the header and health bar
- Transient network or OpenAI failures are now saved into an offline retry queue and retried automatically when service connectivity returns
- Automated regression coverage is currently green: `python -m pytest` -> `105 passed`

## Portfolio Value

- Demonstrates end-to-end hardware and software integration on Raspberry Pi
- Shows small-screen UX thinking for a real embedded device instead of a desktop-only AI demo
- Reuses one shared workflow across terminal, touchscreen, and physical button control paths
- Includes production-minded reliability work such as retries, logs, health checks, smoother live preview, and queued recovery from transient cloud failures

## Documentation Discipline

- README and the Markdown files in `docs/` and the project root are updated whenever a meaningful product improvement lands so the repository stays portfolio-ready and accurate

## Features

- Capture high-resolution images from a USB webcam through OpenCV `VideoCapture`
- Support autofocus, exposure, brightness, and capture-delay controls on the USB/OpenCV camera path
- Apply safe OpenCV preprocessing before AI analysis
- Optimize distant monitor/document photos with screen detection, perspective correction, and text enhancement
- Analyze images with multiple AI modes using the OpenAI Python SDK
- Run the full pipeline from the terminal
- Control the same pipeline from a touchscreen-first Flask UI
- Use a production landscape touchscreen UI optimized for `480x320` Raspberry Pi displays
- Stream a smoother live preview over MJPEG while framing the subject before capture
- Show a compact health bar with overall system, CPU temperature, RAM usage, network, and camera status
- Keep recent successful results available for nearly instant re-open without recapturing
- Show thumbnail previews for recent saved scans directly inside the history gallery
- Re-analyze the same already-captured image under a different AI mode without touching the camera again
- Queue retryable OpenAI or network failures offline and retry them automatically in the background
- Use 5 dedicated GPIO mode buttons plus 1 capture button to trigger the same capture flow
- Use a production-style hardware state machine with short-press capture, long-press clear, physical mode selection, and optional LED feedback
- Load device defaults from `config/device.yaml` with environment variable and CLI overrides
- Run `python check_hardware.py` to verify camera, display, internet, OpenAI, and GPIO readiness
- Boot straight into the touchscreen UI with Chromium kiosk mode on Raspberry Pi OS Bookworm
- Save the latest readable pipeline result to `data/latest_result.txt`
- Persist the current UI mode and screen state in `data/ui_state.json`

## Hardware Used

- Raspberry Pi 5 8GB
- USB webcam
- 2.5 inch HDMI touchscreen or other small HDMI display
- Six momentary push buttons wired with BCM numbering: 1 capture button plus 5 mode buttons
- Case, heatsink, or active cooling for sustained capture workloads
- Internet connection for OpenAI API access

## Software Stack

- Python
- Flask
- OpenCV
- OpenAI Python SDK
- gpiozero
- python-dotenv
- systemd

## System Architecture

See [docs/architecture.md](docs/architecture.md) for the current text architecture diagram.

## Project Structure

```text
raspberry-pi-ai-vision-assistant/
|-- ai/
|-- camera/
|-- config/
|-- data/
|-- deployment/
|-- docs/
|-- gpio/
|-- hardware/
|-- pipeline/
|-- static/
|-- templates/
|-- tests/
|-- vision/
|-- app.py
|-- check_hardware.py
|-- main.py
|-- requirements.txt
|-- test_ai_vision.py
|-- test_camera_capture.py
|-- test_gpio_button.py
|-- test_screen_vision.py
`-- test_preprocess.py
```

## Setup Instructions

### Raspberry Pi OS Packages

Install the required camera and browser packages first:

```bash
sudo apt update
sudo apt install -y python3-opencv chromium-browser
```

### Virtual Environment

Create the virtual environment with system site packages so APT-installed `cv2` is available:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Verify Key Imports

```bash
python -c "import cv2; print('OpenCV OK:', cv2.__version__)"
python -c "import flask, openai, gpiozero; print('Python packages OK')"
```

## Environment Variables

Copy `.env.example` to `.env` and update the required values:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4-mini
FLASK_SECRET_KEY=change_this_for_local_flask_sessions
```

Most hardware defaults now live in [config/device.yaml](config/device.yaml). Environment variables still override that file when needed:

```env
DEVICE_CONFIG_PATH=config/device.yaml
ENABLE_GPIO_BUTTON=1
CAPTURE_BUTTON_PIN=17
MODE_BUTTON_1_PIN=5
MODE_BUTTON_2_PIN=6
MODE_BUTTON_3_PIN=13
MODE_BUTTON_4_PIN=19
MODE_BUTTON_5_PIN=26
# Optional dedicated back button:
# BACK_BUTTON_PIN=21
# Legacy alias still accepted:
# GPIO_BUTTON_PIN=17
GPIO_BUTTON_DEBOUNCE_SECONDS=0.15
GPIO_BUTTON_HOLD_SECONDS=1.2
ENABLE_GPIO_LED=0
GPIO_LED_PIN=27
GPIO_LED_ACTIVE_HIGH=1
VISION_CAMERA_BACKEND=opencv
VISION_CAMERA_INDEX=0
VISION_CAPTURE_WIDTH=4608
VISION_CAPTURE_HEIGHT=2592
VISION_AUTOFOCUS_MODE=continuous
VISION_EXPOSURE=auto
VISION_BRIGHTNESS=0.0
VISION_CAPTURE_DELAY_SECONDS=1.0
VISION_GRAYSCALE=0
VISION_MAX_DIMENSION=1600
SCREEN_OPTIMIZATION=auto
UI_SCREEN_WIDTH=480
UI_SCREEN_HEIGHT=320
UI_DISPLAY_ORIENTATION=landscape
AI_DEFAULT_MODE=document_reader
STARTUP_BEHAVIOR=kiosk
STARTUP_URL=http://localhost:5000
RELIABILITY_LOG_LEVEL=INFO
RELIABILITY_LOG_MAX_BYTES=1048576
RELIABILITY_LOG_BACKUP_COUNT=5
RELIABILITY_HEALTH_MONITOR_ENABLED=1
RELIABILITY_HEALTH_CHECK_INTERVAL_SECONDS=60
RELIABILITY_CAMERA_PROBE_INTERVAL_SECONDS=300
RELIABILITY_OPENAI_TIMEOUT_SECONDS=30
RELIABILITY_OPENAI_RETRY_ATTEMPTS=3
RELIABILITY_OPENAI_RETRY_BACKOFF_SECONDS=2
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
OFFLINE_RETRY_MAX_ENTRIES=24
```

## Device Configuration

`config/device.yaml` is the committed hardware baseline for the standalone device. Runtime precedence is:

```text
config/device.yaml -> environment variables -> CLI flags
```

Default camera, display, button, AI, vision, and startup settings:

```yaml
camera:
  backend: opencv
  index: 0
  resolution:
    width: 4608
    height: 2592
  autofocus_mode: continuous
  exposure: auto
  brightness: 0.0
  capture_delay_seconds: 1.0
  grayscale: false
  max_dimension: 1600

display:
  size:
    width: 480
    height: 320
  orientation: landscape

button:
  enabled: true
  pin: 17
  mode_button_1_pin: 5
  mode_button_2_pin: 6
  mode_button_3_pin: 13
  mode_button_4_pin: 19
  mode_button_5_pin: 26
  back_button_pin: null
  debounce_seconds: 0.15
  hold_seconds: 1.2

led:
  enabled: false
  pin: 27
  active_high: true

ai:
  default_mode: document_reader

vision:
  screen_optimization: auto

startup:
  behavior: kiosk
  url: http://localhost:5000

reliability:
  log_level: INFO
  log_max_bytes: 1048576
  log_backup_count: 5
  health_monitor_enabled: true
  health_check_interval_seconds: 60.0
  camera_probe_interval_seconds: 300.0
  openai_timeout_seconds: 30.0
  openai_retry_attempts: 3
  openai_retry_backoff_seconds: 2.0
```

Runtime reliability artifacts:

- `logs/app.log`: rotating general runtime log
- `logs/error.log`: rotating error-only log
- `data/health_status.json`: latest system health snapshot
- `data/result_history.json`: persisted recent successful assistant results
- `data/result_history_assets/`: saved source and processed images used for RAM thumbnails and instant re-analysis
- `data/offline_retry_queue.json`: persisted retry queue metadata for transient AI failures
- `data/offline_retry/`: copied processed images waiting for automatic retry

Default GPIO wiring uses BCM numbering:

- `Button Main / Capture`: GPIO17
- `Button 1 / Read Text`: GPIO5
- `Button 2 / Summarize Document`: GPIO6
- `Button 3 / Analyze Image`: GPIO13
- `Button 4 / Professional Assistant`: GPIO19
- `Button 5 / Solve Problem`: GPIO26

## Assistant Modes

The shared assistant layer supports 5 canonical internal modes:

- `document_reader`
- `math_solver`
- `meeting_assistant`
- `engineering_mode`
- `general_vision`

The current touchscreen and GPIO button presets still expose the simplified labels `read_text`, `summarize_document`, `analyze_image`, `professional_assistant`, and `solve_problem`, which map onto those internal modes.

## Phase 1: OpenAI Vision Test

Send an existing image file to OpenAI Vision:

```bash
python test_ai_vision.py --image test_images/document.jpg --mode document_reader
```

## Phase 2: Camera Capture

Capture from the supported USB webcam backend:

```bash
```bash
python test_camera_capture.py --backend opencv --camera-index 0
```

High-resolution autofocus example:

```bash
python test_camera_capture.py --backend opencv --camera-index 0 --width 4608 --height 2592 --autofocus-mode continuous
```

Manual exposure example:

```bash
python test_camera_capture.py --backend opencv --camera-index 0 --exposure 12000 --brightness 0.1 --capture-delay 1.5
```

Captured output:

```text
static/captured.jpg
```

## Phase 3: Preprocessing

Preprocess the latest captured image:

```bash
python test_preprocess.py
```

Enable grayscale mode:

```bash
python test_preprocess.py --grayscale
```

Processed output:

```text
static/processed.jpg
```

## Phase 4: Full Terminal Pipeline

Run the full pipeline from the terminal:

```bash
python main.py --mode math_solver
```

Other useful examples:

```bash
python main.py --mode document_reader
python main.py --mode meeting_assistant
python main.py --mode engineering_mode
python main.py --mode general_vision --backend opencv --camera-index 0
python main.py --mode document_reader --grayscale
```

### Run Phase 4 without a camera

You can reuse a saved test image instead of capturing a new one:

```bash
cp test_images/math_problem.jpg static/captured.jpg
python main.py --mode math_solver --skip-capture
```

Other no-camera examples:

```bash
python main.py --mode meeting_assistant --skip-capture
python main.py --mode document_reader --skip-capture --grayscale
python main.py --mode document_reader --skip-capture --screen-optimization on
python main.py --mode document_reader --skip-capture --screen-optimization off
```

When `--skip-capture` is used, `main.py` loads `static/captured.jpg`, preprocesses it into `static/processed.jpg`, and sends the processed image to OpenAI Vision. With `SCREEN_OPTIMIZATION=auto`, the advanced screen/document path is enabled by default for `document_reader`, `math_solver`, and `meeting_assistant`.

## Phase 5: Flask Touchscreen UI

Start the touchscreen UI:

```bash
python app.py
```

The current UI is a kiosk-style, touchscreen-first flow tuned for small Raspberry Pi displays.

The current default device profile uses a `480x320` landscape touchscreen.

For production Pi hardware, the current setup targets this default boot behavior:

```text
Power on -> systemd starts Flask -> Chromium opens http://localhost:5000 in kiosk mode
```

Screen flow:

- `home` without a selected mode: mode list for `Read Text`, `Summarize Document`, `Analyze Image`, `Professional Assistant`, and `Solve Problem`, plus a direct `Capture` action and the live system health bar
- `home` with a selected mode: live MJPEG camera preview, selected mode header, `Click Button to Capture`, health pills, and `Change Mode`
- `processing`: auto-refreshing progress screen with simplified centered status and a `Thinking...` state during AI analysis
- `result`: readable answer screen with a large scrollable answer box, `Capture Again`, and optional `Recent Results`
- `history`: saved recent results list with thumbnail previews for reopening previous successful scans
- `history_detail`: full saved answer view for one historical scan, plus same-image re-analysis actions
- `error`: classified `Camera error`, `Network error`, `API error`, or generic error screen with retry actions

Tapping `Capture` starts the full background capture -> preprocess -> analyze workflow for the currently selected mode.

The selected mode and current screen state are stored in `data/ui_state.json`.
Transient OpenAI or network failures can now be converted into a queued result state instead of being lost immediately.

Open the UI locally on the Pi:

```text
http://127.0.0.1:5000
```

Open it fullscreen in Chromium kiosk mode:

```bash
chromium-browser --kiosk http://127.0.0.1:5000
```

Landscape touchscreen example:

```bash
UI_SCREEN_WIDTH=480 UI_SCREEN_HEIGHT=320 UI_DISPLAY_ORIENTATION=landscape python app.py
```

You can also use Flask directly:

```bash
flask run --host=0.0.0.0 --port=5000
```

Open it from another device on the same network:

```text
http://<raspberry-pi-ip>:5000
```

Find the Pi IP address with:

```bash
hostname -I
```

## Phase 6: GPIO Button Trigger

The Flask app can start the GPIO button listener automatically when `ENABLE_GPIO_BUTTON=1`.

Inside the Flask app, the physical control panel reuses the same background capture job as the touchscreen UI.

Inside the Flask app, the default AI mode comes from `config/device.yaml` unless overridden by environment variables.

Default physical button behavior:

- `Button Main`: short press starts capture, long press clears the current result
- `Button 1`: selects `Read Text`
- `Button 2`: selects `Summarize Document`
- `Button 3`: selects `Analyze Image`
- `Button 4`: selects `Professional Assistant`
- `Button 5`: selects `Solve Problem`

You can still run the standalone GPIO button listener:

```bash
python test_gpio_button.py
```

The default mode is `document_reader`. You can override it:

```bash
python test_gpio_button.py --mode document_reader
python test_gpio_button.py --mode math_solver
python test_gpio_button.py --mode engineering_mode
python test_gpio_button.py --mode meeting_assistant --backend opencv --camera-index 0
```

The script keeps listening until `Ctrl+C`.

Latest readable pipeline result:

```text
data/latest_result.txt
```

## Phase 8: Hardware Diagnostics

Run the standalone device diagnostic:

```bash
python check_hardware.py
```

The script verifies:

- Camera detected and able to capture a still image
- Display connected when startup behavior is `kiosk`
- Internet connection available
- OpenAI API reachable with the configured key and model
- GPIO available through `gpiozero`

## Phase 9: Long-Distance Screen/Document Vision Optimization

Run the advanced screen/document preprocessing flow on an existing image:

```bash
python test_screen_vision.py --input test_images/screen_photo.jpg --detect-screen --enhance
```

If `--detect-screen` and `--enhance` are both omitted, `test_screen_vision.py` enables both by default.

Debug outputs:

```text
debug/original.jpg
debug/detected_screen.jpg
debug/corrected.jpg
debug/enhanced.jpg
```

## Phase 10: Production Touchscreen UI

Phase 10 upgrades the Flask touchscreen experience into a production-ready small-screen UI. The current default device profile uses a `480x320` landscape Raspberry Pi display.

Highlights:

- live-preview-first home state with large mode labels, smoother MJPEG camera framing, and a compact health strip
- simplified processing screen that shows `Thinking...` during AI-heavy steps
- readable scrollable answer box designed for long responses on a 2.5 inch display
- result history and instant answer recall for recent successful captures
- error classification for `Camera error`, `Network error`, `API error`, and fallback generic errors
- fullscreen-friendly CSS for Chromium kiosk mode without page-level scrolling

Recommended landscape launch command:

```bash
UI_SCREEN_WIDTH=480 UI_SCREEN_HEIGHT=320 UI_DISPLAY_ORIENTATION=landscape python app.py
```

Chromium kiosk launch:

```bash
chromium-browser --kiosk http://localhost:5000
```

## Phase 11: Production Hardware Button And LED

Phase 11 turns the physical controls into a product-style hardware flow shared by the Flask UI and GPIO listener.

Device state machine:

```text
READY -> CAPTURING -> PROCESSING -> DONE | ERROR
```

Button behavior:

- short press from `READY`, `DONE`, or `ERROR` starts a new capture and analysis run
- long press from `READY`, `DONE`, or `ERROR` clears the visible answer or error and returns to `READY`
- presses are ignored while the device is in `CAPTURING` or `PROCESSING`

LED behavior with the optional single-color GPIO LED:

- `READY`: solid on
- `CAPTURING`: slow blink
- `PROCESSING`: medium blink
- `DONE`: solid on
- `ERROR`: fast blink

The current lifecycle state is now persisted in `data/ui_state.json` as `device_state`, and the idle touchscreen screens auto-refresh when the GPIO listener is active so button-only interaction updates the kiosk display without a keyboard.

## Phase 13: Assistant Modes

Phase 13 upgrades the assistant layer from a single generic prompt into a shared mode system used by the CLI, Flask UI, and GPIO trigger.

Current canonical assistant modes:

- `document_reader`
- `math_solver`
- `meeting_assistant`
- `engineering_mode`
- `general_vision`

Phase 13 behavior:

- the canonical mode registry lives in `ai/modes.py`
- hidden per-mode OpenAI instructions are built in `ai/context.py`
- the currently selected UI mode is persisted in `data/ui_state.json`
- the default device mode comes from `config/device.yaml` or `AI_DEFAULT_MODE`
- the touchscreen and GPIO presets still use the simplified labels `read_text`, `summarize_document`, `analyze_image`, `professional_assistant`, and `solve_problem`

Examples:

```bash
python main.py --mode document_reader
python main.py --mode math_solver
python main.py --mode meeting_assistant
python test_ai_vision.py --image test_images/document.jpg --mode engineering_mode
python test_gpio_button.py --mode general_vision
```

## Phase 14: Reliability, Logging, And Health Monitoring

Phase 14 adds runtime reliability features so the assistant behaves more like a deployable device instead of a one-off script.

Phase 14 improvements:

- OpenAI requests use configurable timeout, retry count, and exponential backoff settings
- uncaught process and thread exceptions are routed into the shared logging system
- rotating runtime logs are written to `logs/app.log` and `logs/error.log`
- a background health monitor can write snapshots to `data/health_status.json`
- health checks avoid intrusive camera probing while the device is already busy
- reliability settings can be controlled from `config/device.yaml` or environment overrides

Key reliability settings:

```env
RELIABILITY_LOG_LEVEL=INFO
RELIABILITY_LOG_MAX_BYTES=1048576
RELIABILITY_LOG_BACKUP_COUNT=5
RELIABILITY_HEALTH_MONITOR_ENABLED=1
RELIABILITY_HEALTH_CHECK_INTERVAL_SECONDS=60
RELIABILITY_CAMERA_PROBE_INTERVAL_SECONDS=300
RELIABILITY_OPENAI_TIMEOUT_SECONDS=30
RELIABILITY_OPENAI_RETRY_ATTEMPTS=3
RELIABILITY_OPENAI_RETRY_BACKOFF_SECONDS=2
```

Useful checks:

```bash
python check_hardware.py
journalctl -u ai-vision-assistant.service -f
```

## Phase 15: Live Preview, Recent Results, And Offline Retry

Phase 15 pushes the assistant closer to a resilient product workflow instead of a demo-only happy path.

Phase 15 improvements:

- live camera preview now streams through `/camera/live-stream.mjpg` instead of client-side JPEG polling
- recent successful answers are cached in memory and persisted to `data/result_history.json`
- the touchscreen can reopen recent saved answers nearly instantly through `Recent Results`
- retryable OpenAI failures such as network loss, timeout, rate limiting, or `5xx` responses are stored in `data/offline_retry_queue.json`
- a background retry worker replays queued analyses automatically from copied processed images in `data/offline_retry/`
- queued failures appear to the user as `Queued for retry` instead of only showing a hard error
- recent-result cards now include RAM-backed thumbnails for faster visual browsing
- saved images can still be re-run under another mode without recapture, but the main result screen now stays answer-first by hiding the touch `Analyze Same Image As` panel, removing the GPIO hint text, and tightening the header and health pills
- when the embedded GPIO listener is active, those same saved-image re-analysis flows can also be triggered from the physical mode buttons, and the physical back button exits to the ready screen

## Troubleshooting

### Missing `OPENAI_API_KEY`

- Add the key to `.env`
- Restart the Flask app or rerun the terminal script

### OpenAI API Authentication, Quota, or Network Error

- Verify the API key
- Check Raspberry Pi internet access
- Retry after a moment if rate limit or quota is the issue
- When `OFFLINE_RETRY_ENABLED=1`, transient connection/time-out/server failures are automatically queued for background retry instead of being discarded immediately

### OpenCV Not Available

- Run `sudo apt install -y python3-opencv`
- Recreate the venv with `python3 -m venv --system-site-packages .venv`

### Camera Capture Failure

- Check USB webcam connection
- Run `python check_hardware.py`
- Close other apps that may be using the camera

### Autofocus Or Exposure Controls Not Applying

- Some OpenCV webcam drivers ignore autofocus, exposure, or brightness requests
- Review any non-fatal warnings printed by `test_camera_capture.py` or `main.py`

### No Image Available

- Run a capture step first
- Confirm `static/captured.jpg` exists

### Touch UI Layout Does Not Fit The Screen

- The current default profile is tuned for a `480x320` landscape display
- Adjust `display.size.width` and `display.size.height` in `config/device.yaml`
- Change `display.orientation` or override `UI_DISPLAY_ORIENTATION`
- Increase or decrease `UI_TOUCH_TARGET` and font sizes for the attached display

### Reset The UI State

- Stop the Flask app
- Delete `data/ui_state.json` if you want to reset the saved mode and current screen
- Start `python app.py` again

### GPIO Not Available

- Ensure you are running on a Raspberry Pi
- Confirm `gpiozero` is installed
- Confirm the capture button and each optional mode button are wired to the configured GPIO pin and `GND`

### Kiosk Display Does Not Open On Boot

- Confirm `startup.behavior` is `kiosk`
- Confirm Chromium is installed and available as `chromium` or `chromium-browser`
- Copy [deployment/labwc-autostart.example](deployment/labwc-autostart.example) to `~/.config/labwc/autostart`
- Confirm [deployment/kiosk-launch.sh](deployment/kiosk-launch.sh) is executable on the Pi

## Demo Checklist

See [docs/demo_checklist.md](docs/demo_checklist.md).

## Deployment With systemd

The example service file is in:

[deployment/ai-vision-assistant.service](deployment/ai-vision-assistant.service)

Copy it to the systemd directory:

```bash
sudo cp deployment/ai-vision-assistant.service /etc/systemd/system/
```

Reload systemd:

```bash
sudo systemctl daemon-reload
```

Enable the service on boot:

```bash
sudo systemctl enable ai-vision-assistant.service
```

Start the service:

```bash
sudo systemctl start ai-vision-assistant.service
```

Check service status:

```bash
sudo systemctl status ai-vision-assistant.service
```

View live logs:

```bash
journalctl -u ai-vision-assistant.service -f
```

Local rotating files are also written to:

```text
logs/app.log
logs/error.log
```

Note:

- You may need to edit the service file paths for your actual repo location
- You may need to change `User=pi` if your Raspberry Pi uses a different username
- The service loads `.env`, and `.env` can override `config/device.yaml`
- The service is configured to auto-restart after crashes with a short restart delay
- Health snapshots are written to `data/health_status.json` when the health monitor is enabled

For fullscreen kiosk startup on Raspberry Pi OS Bookworm with `labwc`:

1. Copy [deployment/labwc-autostart.example](deployment/labwc-autostart.example) to `~/.config/labwc/autostart`
2. Update the repo path inside the copied file if needed
3. Make [deployment/kiosk-launch.sh](deployment/kiosk-launch.sh) executable on the Pi:

```bash
chmod +x deployment/kiosk-launch.sh
```

4. Reboot the Pi and confirm Chromium opens `http://localhost:5000`

Manual fallback commands:

```bash
python app.py
chromium-browser http://localhost:5000
```

## Portfolio Description

See [docs/upwork_project_description.md](docs/upwork_project_description.md).

## Future Improvements

- Add result history instead of only the latest saved output
- Add GPIO feedback LED or buzzer
- Add optional live preview or captured-image confirmation screens
- Move long-running analysis into a fuller background job model
