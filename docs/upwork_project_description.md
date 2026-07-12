# VisionDesk Project Description

VisionDesk is a Raspberry Pi 5 assistant appliance built around a native `PySide6 + Qt Quick/QML` kiosk interface. A USB camera captures an image, the pipeline preprocesses it with OpenCV-oriented vision helpers, OpenAI analyzes it, and the device shows the answer directly on-screen with GPIO button support.

## Product highlights

- native Qt/QML embedded UI
- first-boot Wi-Fi and OpenAI key setup
- live preview, capture, processing, and result flow
- saved text-only history and history detail screens
- offline retry queue with bounded private storage
- health header and GPIO integration
- privacy-first local persistence with delete-all-data behavior

## Technical shape

- `qt_app/` for the native UI runtime and controllers
- shared backend modules for camera, preprocessing, pipeline, AI, hardware, health, setup, and result history
- local persistence under `config/`, `.env`, and `data/private/`

## Run modes

- development: `python -m qt_app.main --windowed --mock-hardware`
- production: `python -m qt_app.main`
