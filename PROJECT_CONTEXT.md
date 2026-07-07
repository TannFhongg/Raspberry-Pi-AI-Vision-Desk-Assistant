# Project Context

Captured on: 2026-07-06
Project root: `C:\Users\Admin\Desktop\Raspberry Pi AI Vision Desk Assistant`

## Purpose

This repository is a portfolio-ready Raspberry Pi 5 AI vision desk assistant. It demonstrates a full local hardware/software workflow:

```text
Camera capture -> OpenCV preprocessing -> OpenAI Vision analysis -> CLI / Flask UI / GPIO result
```

The project is organized in phases so each layer can be tested independently, then composed through a shared pipeline.

## Current Architecture

Main entrypoints:

- `main.py`: terminal CLI for the full capture, preprocess, and analyze flow.
- `app.py`: Flask dashboard for capture, analyze, capture+analyze, clear, preview, status, error, and answer display.
- `test_gpio_button.py`: terminal listener for a physical GPIO button that triggers the full pipeline.
- `test_ai_vision.py`: one-off OpenAI Vision test using an existing local image.
- `test_camera_capture.py`: one-off camera capture test.
- `test_preprocess.py`: one-off OpenCV preprocessing test.

Shared core:

- `pipeline/runner.py`: central orchestration for `run_capture`, `run_preprocess`, `run_analyze`, `run_capture_analyze`, and `save_latest_result`.
- `camera/capture.py`: camera abstraction with `auto`, `picamera2`, and `opencv` backends. Auto tries Picamera2 first, then OpenCV.
- `vision/preprocess.py`: safe preprocessing with optional resize, grayscale, CLAHE contrast, and light sharpening.
- `ai/openai_client.py`: OpenAI Responses API wrapper for image analysis. It validates image type/size and returns friendly app errors.
- `ai/prompts.py`: supported mode definitions and prompt builder.
- `gpio/button.py`: gpiozero-based button trigger with a busy flag to avoid overlapping pipeline runs.

Runtime artifacts:

- `static/captured.jpg`: latest camera capture.
- `static/processed.jpg`: latest preprocessed image.
- `data/latest_result.txt`: latest GPIO-triggered result.
- `data/web_feedback.json`: local Flask dashboard feedback state.

These generated files are ignored by git.

## Supported AI Modes

Defined in `ai/prompts.py`:

- `read_text`
- `summarize`
- `summarize_document`
- `solve_problem`
- `professional_assistant`

`summarize` is an alias for `summarize_document`.

## Web UI State

`app.py` uses Flask sessions only for the selected mode. Larger text feedback is stored in `data/web_feedback.json` to avoid large session cookies.

The UI template is `templates/index.html`, and styling is in `static/style.css`.

Dashboard controls:

- AI mode dropdown
- Capture Image
- Analyze Image
- Capture + Analyze
- Clear
- Status and error panels
- AI answer panel
- Captured and processed image previews

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
OPENAI_MODEL=gpt-4o-mini
FLASK_SECRET_KEY=change_this_for_local_flask_sessions
```

Security note: `.env.example` currently appears to contain a real OpenAI API key and is modified in the working tree. Do not commit that secret. Rotate the key, then replace it with a placeholder.

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

Run full terminal pipeline:

```bash
python main.py --mode solve_problem
python main.py --mode read_text --backend picamera2
python main.py --mode professional_assistant --backend opencv --camera-index 0
```

Run Flask dashboard:

```bash
python app.py
```

Local URL:

```text
http://127.0.0.1:5000
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
- Optional HDMI display, touchscreen, speaker, buzzer, or power bank for demos

## Deployment

Systemd service template:

- `deployment/ai-vision-assistant.service`

Docs:

- `docs/architecture.md`: architecture diagram and module notes.
- `docs/demo_checklist.md`: demo preparation and flow.
- `docs/upwork_project_description.md`: portfolio/freelance-oriented project description.
- `hardware_require.txt`: hardware checklist.

## Current Worktree State

Observed git status before this file was created:

```text
 M .env.example
```

`PROJECT_CONTEXT.md` did not exist before this snapshot.

## Known Limitations And Follow-ups

- Full camera and GPIO behavior must be verified on Raspberry Pi hardware.
- OpenAI analysis requires internet access and a valid API key.
- Flask actions are synchronous; a background job flow would improve UX for slow analysis.
- The app currently stores only the latest result, not a result history.
- Consider adding an LED or buzzer for GPIO feedback.
- Consider restoring `.env.example` to safe placeholder values after rotating the exposed key.
- Verify the configured OpenAI model name before a public demo.

## Development Guardrails

- Do not commit `.env` or real secrets.
- Do not overwrite user changes in `.env.example` without explicit approval.
- Keep shared behavior in `pipeline/runner.py` so CLI, Flask, and GPIO stay consistent.
- Keep generated image/result files out of git.
- Prefer small, phase-based tests when changing camera, preprocessing, AI, or GPIO behavior.
