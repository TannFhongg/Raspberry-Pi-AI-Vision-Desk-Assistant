# Raspberry Pi AI Vision Desk Assistant

## Project Overview

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready Raspberry Pi 5 project that demonstrates a full local AI vision workflow:

```text
Camera Capture -> OpenCV Preprocessing / Screen Optimization -> OpenAI Vision Analysis -> CLI / Touchscreen UI / GPIO Trigger
```

The project is organized in phases so each layer can be tested independently and then combined into a single shared pipeline.

## Features

- Capture high-resolution images from a Raspberry Pi CSI camera with Picamera2
- Support autofocus, exposure, brightness, and capture-delay controls on supported camera backends
- Fall back to OpenCV `VideoCapture` for USB webcams
- Apply safe OpenCV preprocessing before AI analysis
- Optimize distant monitor/document photos with screen detection, perspective correction, and text enhancement
- Analyze images with multiple AI modes using the OpenAI Python SDK
- Run the full pipeline from the terminal
- Control the same pipeline from a touchscreen-first Flask UI
- Use a configurable physical GPIO button to trigger the same capture flow
- Load device defaults from `config/device.yaml` with environment variable and CLI overrides
- Run `python check_hardware.py` to verify camera, display, internet, OpenAI, and GPIO readiness
- Boot straight into the touchscreen UI with Chromium kiosk mode on Raspberry Pi OS Bookworm
- Save the latest readable pipeline result to `data/latest_result.txt`
- Persist the current UI mode and screen state in `data/ui_state.json`

## Hardware Used

- Raspberry Pi 5 8GB
- Autofocus camera such as Raspberry Pi Camera Module 3 or Arducam 64MP
- Optional USB webcam
- 2.5 inch HDMI touchscreen or other small HDMI display
- Push button connected to the configured GPIO pin and `GND`
- Case, heatsink, or active cooling for sustained capture workloads
- Internet connection for OpenAI API access

## Software Stack

- Python
- Flask
- OpenCV
- OpenAI Python SDK
- Picamera2
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

Install the camera and OpenCV system packages first:

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv chromium-browser
```

### Virtual Environment

Create the virtual environment with system site packages so APT-installed `picamera2` and `cv2` are available:

```bash
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Verify Key Imports

```bash
python -c "from picamera2 import Picamera2; print('Picamera2 OK')"
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
GPIO_BUTTON_PIN=17
VISION_CAMERA_BACKEND=auto
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
AI_DEFAULT_MODE=read_text
STARTUP_BEHAVIOR=kiosk
STARTUP_URL=http://localhost:5000
UI_BASE_FONT_SIZE=20
UI_TITLE_FONT_SIZE=34
UI_STATUS_FONT_SIZE=28
UI_BUTTON_FONT_SIZE=24
UI_TOUCH_TARGET=68
UI_PROCESSING_REFRESH_MS=1200
UI_IDLE_REFRESH_MS=2500
```

## Device Configuration

`config/device.yaml` is the committed hardware baseline for the standalone device. Runtime precedence is:

```text
config/device.yaml -> environment variables -> CLI flags
```

Default camera, display, button, AI, vision, and startup settings:

```yaml
camera:
  backend: auto
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

ai:
  default_mode: read_text

vision:
  screen_optimization: auto

startup:
  behavior: kiosk
  url: http://localhost:5000
```

## Phase 1: OpenAI Vision Test

Send an existing image file to OpenAI Vision:

```bash
python test_ai_vision.py --image test_images/document.jpg --mode summarize_document
```

## Phase 2: Camera Capture

Try Picamera2 first, then fall back to OpenCV if needed:

```bash
python test_camera_capture.py --backend auto
```

Force the Raspberry Pi CSI camera backend:

```bash
python test_camera_capture.py --backend picamera2
```

Force a USB webcam:

```bash
python test_camera_capture.py --backend opencv --camera-index 0
```

High-resolution autofocus example:

```bash
python test_camera_capture.py --backend picamera2 --width 4608 --height 2592 --autofocus-mode continuous
```

Manual exposure example:

```bash
python test_camera_capture.py --backend picamera2 --exposure 12000 --brightness 0.1 --capture-delay 1.5
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

## Phase 4: Full Terminal Pipeline

Run the full pipeline from the terminal:

```bash
python main.py --mode solve_problem
```

Other useful examples:

```bash
python main.py --mode summarize
python main.py --mode summarize_document
python main.py --mode analyze_image
python main.py --mode read_text --backend picamera2
python main.py --mode professional_assistant --backend opencv --camera-index 0
python main.py --mode read_text --grayscale
```

### Run Phase 4 without a camera

You can reuse a saved test image instead of capturing a new one:

```bash
cp test_images/math_problem.jpg static/captured.jpg
python main.py --mode solve_problem --skip-capture
```

Other no-camera examples:

```bash
python main.py --mode summarize --skip-capture
python main.py --mode read_text --skip-capture --grayscale
python main.py --mode read_text --skip-capture --screen-optimization on
python main.py --mode read_text --skip-capture --screen-optimization off
```

When `--skip-capture` is used, `main.py` loads `static/captured.jpg`, preprocesses it into `static/processed.jpg`, and sends the processed image to OpenAI Vision. With `SCREEN_OPTIMIZATION=auto`, the advanced screen/document path is enabled by default for `read_text`, `summarize`, `summarize_document`, and `solve_problem`.

## Phase 5: Flask Touchscreen UI

Start the touchscreen UI:

```bash
python app.py
```

The current UI is a kiosk-style, touchscreen-first flow tuned for small Raspberry Pi displays.

For production Pi hardware, Phase 8 targets this default boot behavior:

```text
Power on -> systemd starts Flask -> Chromium opens http://localhost:5000 in kiosk mode
```

Screen flow:

- `home`: minimal launcher with `Mode` and `Capture`
- `mode_select`: dedicated mode picker for `Read Text`, `Summarize Document`, `Solve Problem`, `Analyze Image`, and `Professional Assistant`
- `processing`: auto-refreshing progress screen for capture, preprocessing, AI analysis, and answer preparation
- `result`: readable answer screen with `New Capture` and `Back`
- `error`: friendly error screen with `Try Again` and `Back`

Tapping `Capture` on the home screen starts the full background capture -> preprocess -> analyze workflow for the currently selected mode.

The selected mode and current screen state are stored in `data/ui_state.json`.

Open the UI locally on the Pi:

```text
http://127.0.0.1:5000
```

Open it fullscreen in Chromium kiosk mode:

```bash
chromium-browser --kiosk --app=http://127.0.0.1:5000
```

Portrait touchscreen example:

```bash
UI_SCREEN_WIDTH=320 UI_SCREEN_HEIGHT=480 UI_DISPLAY_ORIENTATION=portrait python app.py
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

Inside the Flask app, the button reuses the same background capture job as the touchscreen UI.

Inside the Flask app, the default AI mode comes from `config/device.yaml` unless overridden by environment variables.

You can still run the standalone GPIO button listener:

```bash
python test_gpio_button.py
```

The default mode is `solve_problem`. You can override it:

```bash
python test_gpio_button.py --mode read_text
python test_gpio_button.py --mode summarize
python test_gpio_button.py --mode analyze_image
python test_gpio_button.py --mode professional_assistant --backend picamera2
python test_gpio_button.py --mode solve_problem --backend opencv --camera-index 0
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

## Troubleshooting

### Missing `OPENAI_API_KEY`

- Add the key to `.env`
- Restart the Flask app or rerun the terminal script

### OpenAI API Authentication, Quota, or Network Error

- Verify the API key
- Check Raspberry Pi internet access
- Retry after a moment if rate limit or quota is the issue

### Picamera2 Not Available

- Run `sudo apt install -y python3-picamera2`
- Recreate the venv with `python3 -m venv --system-site-packages .venv`

### OpenCV Not Available

- Run `sudo apt install -y python3-opencv`
- Recreate the venv with `python3 -m venv --system-site-packages .venv`

### Camera Capture Failure

- Check CSI camera cable seating
- Check USB webcam connection
- Run `python check_hardware.py`
- Close other apps that may be using the camera

### Autofocus Or Exposure Controls Not Applying

- Confirm you are using a Picamera2-supported autofocus camera
- Some OpenCV webcam drivers ignore autofocus, exposure, or brightness requests
- Review any non-fatal warnings printed by `test_camera_capture.py` or `main.py`

### No Image Available

- Run a capture step first
- Confirm `static/captured.jpg` exists

### Touch UI Layout Does Not Fit The Screen

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
- Confirm the button is wired to the configured GPIO pin and `GND`

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

Note:

- You may need to edit the service file paths for your actual repo location
- You may need to change `User=pi` if your Raspberry Pi uses a different username
- The service loads `.env`, and `.env` can override `config/device.yaml`

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
