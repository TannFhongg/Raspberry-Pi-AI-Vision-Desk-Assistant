# UI Demo Pack

This folder is a small handoff package for collecting the current VisionDesk UI screenshots.

## Expected image files

- `UI_HOME.png`
- `UI_PREVIEW.png`
- `UI_PROCESS.png`
- `UI_RESULT.png`

You can drop the real screenshots into those files manually. The filenames already match the current UI flow.

## What this project is

VisionDesk is a Raspberry Pi 5 touchscreen capture assistant built around:

- a USB webcam
- OpenCV preprocessing
- OpenAI Vision analysis
- a Flask kiosk UI
- optional GPIO hardware buttons

Current product profile:

- local-only kiosk at `127.0.0.1:5000`
- `1200x800` landscape touchscreen layout
- private runtime media under `data/private/`
- text-first result history
- offline retry support for retryable AI/network failures

## Current UI flow

The screenshots in this folder should follow the current user journey:

1. `UI_HOME.png` -> mode selection dashboard
2. `UI_PREVIEW.png` -> camera preview screen after a mode is chosen
3. `UI_PROCESS.png` -> processing screen during an active capture/analyze job
4. `UI_RESULT.png` -> final answer screen

## Recommended capture flow

1. Run `python app.py`
2. Open `http://127.0.0.1:5000`
3. Capture the `home` screen before selecting a mode
4. Select a mode and capture the `camera` screen
5. Start a job and capture the `processing` screen while progress is active
6. Wait for completion and capture the `result` screen

## Important context

- The current active objective for the codebase is the `Processing` screen, with the Figma design treated as the source of truth.
- The app uses one shared HTML template, `templates/index.html`, and swaps screen sections based on persisted UI state.
- The UI is not a generic dashboard. It is a touchscreen appliance flow: `home -> camera -> processing -> result`.
- Health pills and processing state should reflect real backend data, not mocked demo values.

## Files in this folder

- [`SCREENSHOT_GUIDE.md`](./SCREENSHOT_GUIDE.md): what each screenshot should contain
- [`PROJECT_UI_CONTEXT.md`](./PROJECT_UI_CONTEXT.md): current UI, mode, state, and privacy context
- [`PROCESSING_SCREEN_CONTEXT.md`](./PROCESSING_SCREEN_CONTEXT.md): extra notes for the current processing-screen objective
