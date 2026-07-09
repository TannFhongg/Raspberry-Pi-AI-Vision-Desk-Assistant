# Raspberry Pi AI Vision Desk Assistant

## Project Overview

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready Raspberry Pi 5 project that demonstrates a full local AI vision workflow:

```text
Camera Capture -> OpenCV Preprocessing -> OpenAI Vision Analysis -> CLI / Touchscreen UI / GPIO Trigger
```

The project is organized in phases so each layer can be tested independently and then combined into a single shared pipeline.

## Features

- Capture images from a Raspberry Pi CSI camera with Picamera2
- Fall back to OpenCV `VideoCapture` for USB webcams
- Apply safe OpenCV preprocessing before AI analysis
- Analyze images with multiple AI modes using the OpenAI Python SDK
- Run the full pipeline from the terminal
- Control the same pipeline from a touchscreen-first Flask UI
- Use a physical GPIO button on `GPIO17` to trigger the same capture flow
- Save the latest readable pipeline result to `data/latest_result.txt`
- Persist the current UI mode and screen state in `data/ui_state.json`

## Hardware Used

- Raspberry Pi 5
- Raspberry Pi camera / Arducam CSI camera
- Optional USB webcam
- Push button connected to `GPIO17` and `GND`
- Optional HDMI display or small touchscreen
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
|-- data/
|-- deployment/
|-- docs/
|-- gpio/
|-- pipeline/
|-- static/
|-- templates/
|-- vision/
|-- app.py
|-- main.py
|-- requirements.txt
|-- test_ai_vision.py
|-- test_camera_capture.py
|-- test_gpio_button.py
`-- test_preprocess.py
```

## Setup Instructions

### Raspberry Pi OS Packages

Install the camera and OpenCV system packages first:

```bash
sudo apt update
sudo apt install -y python3-picamera2 python3-opencv
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

Useful optional runtime settings:

```env
ENABLE_GPIO_BUTTON=1
GPIO_BUTTON_PIN=17
VISION_CAMERA_BACKEND=auto
VISION_CAMERA_INDEX=0
VISION_CAPTURE_WIDTH=1280
VISION_CAPTURE_HEIGHT=720
VISION_GRAYSCALE=0
VISION_MAX_DIMENSION=1600
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
```

When `--skip-capture` is used, `main.py` loads `static/captured.jpg`, preprocesses it into `static/processed.jpg`, and sends the processed image to OpenAI Vision.

## Phase 5: Flask Touchscreen UI

Start the touchscreen UI:

```bash
python app.py
```

The current UI is a kiosk-style, touchscreen-first flow tuned for small Raspberry Pi displays.

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
- Close other apps that may be using the camera

### No Image Available

- Run a capture step first
- Confirm `static/captured.jpg` exists

### Touch UI Layout Does Not Fit The Screen

- Adjust `UI_SCREEN_WIDTH` and `UI_SCREEN_HEIGHT`
- Change `UI_DISPLAY_ORIENTATION` to `portrait`, `landscape`, or `auto`
- Increase or decrease `UI_TOUCH_TARGET` and font sizes for the attached display

### Reset The UI State

- Stop the Flask app
- Delete `data/ui_state.json` if you want to reset the saved mode and current screen
- Start `python app.py` again

### GPIO Not Available

- Ensure you are running on a Raspberry Pi
- Confirm `gpiozero` is installed
- Confirm the button is wired to `GPIO17` and `GND`

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
- The service loads `.env`, so camera, screen, orientation, and GPIO settings can be adjusted there
- For a built-in display, pair the service with a Chromium kiosk launch on the Pi desktop session

## Portfolio Description

See [docs/upwork_project_description.md](docs/upwork_project_description.md).

## Future Improvements

- Add result history instead of only the latest saved output
- Add GPIO feedback LED or buzzer
- Add optional live preview or captured-image confirmation screens
- Move long-running analysis into a fuller background job model
