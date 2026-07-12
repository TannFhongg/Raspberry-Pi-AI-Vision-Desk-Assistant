# Project Context

## Current product shape

VisionDesk is a native `PySide6 + Qt Quick/QML` kiosk application. The Qt app is the only production UI. It handles:

- first-boot setup for Wi-Fi and `OPENAI_API_KEY`
- mode selection
- live camera preview
- capture and processing
- result display
- saved history and history detail
- offline retry visibility through shared backend state
- GPIO button integration
- delete-all-data behavior

## Entrypoints

- `python -m qt_app.main --windowed --mock-hardware`
- `python -m qt_app.main`

## Important modules

- `qt_app/main.py`: Qt bootstrap and fullscreen/windowed startup
- `qt_app/app_controller.py`: QML-facing facade
- `qt_app/setup_controller.py`: setup workflow controller
- `qt_app/history_controller.py`: history, detail, clear-history, and delete-all-data controller
- `qt_app/pipeline_controller.py`: capture/analyze worker orchestration
- `qt_app/health_controller.py`: header metrics and health refresh
- `qt_app/gpio_controller.py`: hardware button integration

- `system/setup_flow.py`: setup state persistence and validation helpers
- `system/result_history.py`: text-only history persistence, recovery, delete-one, and clear
- `system/ui_presenters.py`: sanitized answer formatting, detail rendering, progress, and health shaping
- `system/offline_retry.py`: deferred retry queue and private media retention
- `qt_app/runtime.py`: shared runtime wiring and delete-all-data orchestration

## Persisted data

- `config/device.yaml`: device config and setup-completion metadata
- `.env`: private secrets such as `OPENAI_API_KEY`
- `data/result_history.json`: saved text-only result history
- `data/latest_result.txt`: latest non-sensitive result summary
- `data/setup_state.json`: temporary setup progress file
- `data/private/`: private current media, retry media, queue metadata, and quarantine files

## Guardrails

- no public image-serving path
- text-only history by default
- bounded retry retention
- atomic JSON/text writes
- quarantine on corrupt persisted files
- `Delete All Data` does not remove device config or `.env`

## Recent migration result

- all legacy web UI code has been removed
- there is no secondary UI runtime
- there is no local HTTP UI port
- native Qt now covers setup, capture, result, history, and delete-all-data
