# Raspberry Pi AI Vision Desk Assistant

## Project Overview

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready Raspberry Pi 5 project that proves a full local AI vision workflow:

Camera Capture -> OpenCV Preprocessing -> OpenAI Vision Analysis -> Terminal Output / Web UI / GPIO Trigger

The project is organized in phases so each layer can be tested independently and then composed into a full working assistant.

## Features

- Capture images from a Raspberry Pi CSI camera with Picamera2
- Fall back to OpenCV `VideoCapture` for USB webcams
- Apply safe OpenCV preprocessing before AI analysis
- Analyze images with multiple AI modes using the OpenAI Python SDK
- Run the full pipeline from the terminal
- Control the pipeline from a local Flask dashboard
- Trigger the pipeline with a physical GPIO button on GPIO17
- Save the most recent GPIO-triggered result to `data/latest_result.txt`
- Package the project with deployment and demo documentation for GitHub portfolio use

## Hardware Used

- Raspberry Pi 5
- Raspberry Pi camera / Arducam CSI camera
- Optional USB webcam
- Push button connected to `GPIO17` and `GND`
- Optional HDMI display
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

See [docs/architecture.md](docs/architecture.md) for the text architecture diagram.

## Project Structure

```text
raspberry-pi-ai-vision-assistant/
├── ai/
├── camera/
├── data/
├── deployment/
├── docs/
├── gpio/
├── pipeline/
├── static/
├── templates/
├── vision/
├── app.py
├── main.py
├── requirements.txt
├── test_ai_vision.py
├── test_camera_capture.py
├── test_preprocess.py
└── test_gpio_button.py
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

Copy `.env.example` to `.env` and update the values:

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-5.4-mini
FLASK_SECRET_KEY=change_this_for_local_flask_sessions
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
python main.py --mode read_text --backend picamera2
python main.py --mode professional_assistant --backend opencv --camera-index 0
python main.py --mode read_text --grayscale
```

## Phase 5: Flask Web UI

Start the web dashboard:

```bash
python app.py
```

Or with Flask:

```bash
flask run --host=0.0.0.0 --port=5000
```

Open the UI locally:

```text
http://127.0.0.1:5000
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

Run the GPIO button listener:

```bash
python test_gpio_button.py
```

The default mode is `solve_problem`. You can override it:

```bash
python test_gpio_button.py --mode read_text
python test_gpio_button.py --mode summarize
python test_gpio_button.py --mode professional_assistant --backend picamera2
python test_gpio_button.py --mode solve_problem --backend opencv --camera-index 0
```

The script keeps listening until `Ctrl+C`.

Latest readable GPIO-triggered result:

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

### Processed Preview Missing In Flask UI

- This is expected when `static/processed.jpg` is older than the latest `static/captured.jpg`
- Click `Analyze Image` or `Capture + Analyze` to regenerate it

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

## Portfolio Description

See [docs/upwork_project_description.md](docs/upwork_project_description.md).

## Future Improvements

- Add background task execution for the Flask UI
- Add a result history log instead of only `latest_result.txt`
- Add GPIO feedback LED or buzzer
- Add OCR-first preprocessing presets
- Add touchscreen-friendly fullscreen mode
- Add offline fallback analysis options
