# VisionDesk Project Description

VisionDesk is a Raspberry Pi 5 assistant appliance built around a native `PySide6 + Qt Quick/QML` kiosk interface. A USB camera captures an image, the pipeline preprocesses it with OpenCV-oriented vision helpers, OpenAI analyzes it, and the device shows the answer directly on-screen with GPIO button support.

## Product highlights

- native Qt/QML embedded UI
- 6-step first-boot setup wizard for device checks, Wi-Fi, OpenAI key, camera, and GPIO
- live preview, capture, processing, and result flow
- saved text-only history and history detail screens
- offline retry queue with bounded private storage
- health header and GPIO integration
- privacy-first local persistence with user-data reset, configuration reset, and full factory reset flows

## Technical shape

- `qt_app/` for the native UI runtime and controllers
- shared backend modules for camera, preprocessing, pipeline, AI, hardware, health, setup, reset, and result history
- shared production/dev path resolution through `visiondesk/paths.py`
- production persistence under `/etc/visiondesk`, `/var/lib/visiondesk`, `/var/log/visiondesk`, and `/opt/visiondesk`
- versioned appliance lifecycle scripts for install, local-archive update, uninstall, and factory reset

## Run modes

- development: `python -m qt_app.main --windowed --mock-hardware`
- direct Qt run: `python -m qt_app.main`
- installed appliance: `visiondesk.service`
