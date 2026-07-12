# Raspberry Pi AI Vision Desk Assistant

VisionDesk is now a native `PySide6 + Qt Quick/QML` kiosk application for Raspberry Pi. It captures an image from a USB camera, preprocesses it, sends it to OpenAI, and shows the result directly in the Qt interface with GPIO, setup, health, history, offline retry, and privacy-aware local storage.

## What it includes

- Native Qt/QML screens for `setup`, `home`, `camera`, `processing`, `result`, `history`, `history_detail`, and `error`
- Shared Python backend for capture, preprocessing, OpenAI analysis, GPIO controls, health monitoring, offline retry, and retention
- First-boot setup flow for Wi-Fi and `OPENAI_API_KEY`
- Text-only result history by default
- `Delete All Data` and `Clear History` flows in the native UI

## Main commands

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run locally in a normal window with deterministic mock services:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Run the production kiosk entrypoint:

```bash
python -m qt_app.main
```

Run tests:

```bash
pytest -q
```

## Production service

The production UI service template is:

- `deployment/visiondesk-qt.service`

Useful service commands:

```bash
sudo systemctl start visiondesk-qt
sudo systemctl restart visiondesk-qt
journalctl -u visiondesk-qt -f
```

## Important paths

- `config/device.yaml`: device defaults and startup behavior
- `.env`: private runtime secrets such as `OPENAI_API_KEY`
- `data/result_history.json`: persisted text-only recent results
- `data/latest_result.txt`: latest non-sensitive result summary
- `data/setup_state.json`: temporary partial setup progress
- `data/private/`: private current media, retry media, queue data, and quarantine artifacts

## Configuration notes

- `startup.behavior` is the remaining startup UI setting in `config/device.yaml`
- Wi-Fi metadata is written into `config/device.yaml` by the native setup flow
- The OpenAI key is stored in `.env`
- There is no local UI web server or secondary kiosk runtime in production

## Project layout

- `qt_app/`: native app runtime, controllers, image provider, models, and QML
- `system/`: shared setup, history, health, logging, retry, and persistence logic
- `camera/`, `vision/`, `pipeline/`, `ai/`, `hardware/`: reusable backend modules
- `tests/`: backend and Qt coverage
- `deployment/visiondesk-qt.service`: systemd template for the native UI
