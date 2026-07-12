# Project Context

## Current product shape

VisionDesk is a native `PySide6 + Qt Quick/QML` kiosk application. The Qt app is the only production UI and is expected to run under `visiondesk.service`. It handles:

- 6-step first-boot setup for device checks, Wi-Fi, OpenAI key, camera, and GPIO
- mode selection
- live camera preview
- capture and processing
- result display
- saved history and history detail
- offline retry visibility through shared backend state
- GPIO button integration
- device actions for user-data reset, configuration reset, and full factory reset

## Entrypoints

- `python -m qt_app.main --windowed --mock-hardware`
- `python -m qt_app.main`
- `sudo ./install.sh`
- `sudo ./update.sh --check`
- `sudo ./update.sh --local /path/to/archive.tar.gz`
- `sudo ./uninstall.sh`
- `sudo ./factory-reset.sh --mode user_data`

## Important modules

- `visiondesk/version.py`: single application version source
- `visiondesk/paths.py`: production/dev path resolver and override layer

- `qt_app/main.py`: Qt bootstrap and fullscreen/windowed startup
- `qt_app/app_controller.py`: QML-facing facade plus device-action reset flow
- `qt_app/setup_controller.py`: setup workflow controller
- `qt_app/history_controller.py`: history and clear-history behavior
- `qt_app/pipeline_controller.py`: capture/analyze worker orchestration
- `qt_app/health_controller.py`: header metrics and health refresh
- `qt_app/gpio_controller.py`: hardware button integration
- `qt_app/runtime.py`: shared runtime wiring, path-aware startup, restart handling, and reset recovery

- `system/setup_flow.py`: authoritative setup state persistence and validation helpers
- `system/diagnostics.py`: install/setup smoke checks and friendly device checks
- `system/result_history.py`: text-only history persistence, recovery, delete-one, and clear
- `system/factory_reset.py`: shared configuration reset, user-data reset, and full factory reset logic
- `system/migrations.py`: update/install migration entrypoint
- `system/ui_presenters.py`: sanitized answer formatting, detail rendering, progress, and health shaping
- `system/offline_retry.py`: deferred retry queue and private media retention

## Persisted data

Production locations:

- `/etc/visiondesk/device.yaml`: durable device config and compatibility setup fields
- `/etc/visiondesk/visiondesk.env`: private secrets such as `OPENAI_API_KEY`
- `/var/lib/visiondesk/setup_state.json`: authoritative setup progress and completion
- `/var/lib/visiondesk/result_history.json`: saved text-only result history
- `/var/lib/visiondesk/latest_result.txt`: latest non-sensitive result summary
- `/var/lib/visiondesk/private/`: private current media, retry media, cache, queue metadata, and quarantine files
- `/var/lib/visiondesk/factory_reset_state.json`: reset recovery marker
- `/var/log/visiondesk/`: lifecycle and service logs

Development defaults:

- `config/device.yaml`
- `.env`
- `data/`
- `logs/`

## Guardrails

- no public image-serving path
- text-only history by default
- bounded retry retention
- atomic JSON/text writes
- quarantine on corrupt persisted files
- `User-Data Reset` does not remove device config or secrets
- uninstall preserves `/etc/visiondesk`, `/var/lib/visiondesk`, and `/var/log/visiondesk` unless `--purge` is explicitly requested

## Recent migration result

- all legacy web UI code has been removed
- there is no secondary UI runtime
- there is no local HTTP UI port
- `visiondesk.service` is the only supported production UI service
- setup routing now uses the shared authoritative setup-state file instead of repo-local temporary state
