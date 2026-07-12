# Architecture

## High-level flow

```text
Qt/QML UI
  -> qt_app.app_controller
  -> setup / history / health / camera / pipeline controllers
  -> shared runtime services
  -> camera / vision / ai / pipeline / hardware / system modules
  -> private local storage + OpenAI
```

## Native UI stack

- `qt_app/main.py` creates the Qt application, image provider, and root controller.
- `qt_app/app_controller.py` is the single facade exposed to QML.
- `qt_app/qml/` contains the kiosk screens and shared components.
- `qt_app/setup_controller.py` owns the 6-step setup wizard.
- `qt_app/history_controller.py` owns saved-result list/detail state and clear-history behavior.
- `qt_app/runtime.py` owns shared settings, path-aware startup, restart signaling, and reset recovery.

## Shared backend stack

- `visiondesk/version.py` is the only application version source.
- `visiondesk/paths.py` resolves development and production layout from one shared override layer.
- `system/setup_flow.py` provides authoritative setup persistence, state normalization, and completion logic.
- `system/diagnostics.py` provides install/setup smoke checks and friendly device diagnostics.
- `system/result_history.py` provides text-only history persistence, corruption recovery, single-item delete, and clear-history support.
- `system/offline_retry.py` provides durable retry queue behavior with private storage bounds.
- `system/factory_reset.py` provides configuration reset, user-data reset, full factory reset, and reset recovery markers.
- `system/migrations.py` is the release migration entrypoint used by install/update flows.
- `system/ui_presenters.py` provides answer sanitization, result/detail shaping, progress copy, and health/header shaping.

## Deployment stack

- `install.sh` validates the Raspberry Pi target, installs system packages, stages a versioned release under `/opt/visiondesk/releases/<version>`, seeds config on first install, renders `visiondesk.service`, runs smoke checks, and rolls back on failure.
- `deployment/visiondesk.service` starts the Qt app only.
- `deployment/visiondesk-launch.sh` waits for a usable X11/Wayland session and then executes `python -m qt_app.main`.
- `update.sh` validates local archives using `manifest.json` plus checksums, builds an isolated venv, runs migrations and diagnostics, flips `/opt/visiondesk/current`, restarts the service, and records rollback metadata.
- `uninstall.sh` removes the app and service while preserving config/data/logs by default.
- `factory-reset.sh` is a thin CLI wrapper over the shared Python reset backend.

## Storage model

Production layout:

- `/opt/visiondesk/current`: active release symlink
- `/opt/visiondesk/releases/<version>`: immutable staged releases
- `/etc/visiondesk/device.yaml`: durable device config
- `/etc/visiondesk/visiondesk.env`: durable secrets and overrides
- `/var/lib/visiondesk/setup_state.json`: authoritative setup progress and completion
- `/var/lib/visiondesk/result_history.json`: saved text-only result history
- `/var/lib/visiondesk/latest_result.txt`: latest non-sensitive result summary
- `/var/lib/visiondesk/private/current/`: current capture working files
- `/var/lib/visiondesk/private/retry/`: queued retry media
- `/var/lib/visiondesk/private/cache/`: cached preview artifacts
- `/var/lib/visiondesk/private/retry_queue.json`: queued retry metadata
- `/var/lib/visiondesk/private/quarantine/`: corrupt persisted files and leftovers
- `/var/lib/visiondesk/factory_reset_state.json`: reset recovery marker
- `/var/log/visiondesk/`: install, update, and runtime logs

Development defaults:

- `config/device.yaml`
- `.env`
- `data/result_history.json`
- `data/latest_result.txt`
- `data/setup_state.json`
- `data/private/`
- `logs/`

Both layouts are resolved through `visiondesk/paths.py`. Production/dev overrides are controlled by `VISIONDESK_PATH_MODE`, `DEVICE_CONFIG_PATH`, `VISIONDESK_ENV_FILE`, `VISIONDESK_DATA_DIR`, and `VISIONDESK_LOG_DIR`.

## Setup and reset model

- setup routing is driven by the authoritative setup-state file, not by repo-local temporary state and not by config flags alone
- setup completion is mirrored into `device.yaml` for compatibility, but the setup-state file is the source of truth for UI routing
- the OpenAI key is written to `visiondesk.env` and only Qt-facing masked state is exposed to QML
- reset operations write a recovery marker before modifying persistent state so startup can resume interrupted cleanup safely

## Privacy model

- result history stores text and safe metadata only
- private media stays under the shared private storage tree
- startup purge trims transient data
- `User-Data Reset` clears user content without deleting device config or secrets
- `Configuration Reset` and `Full Factory Reset` relaunch the app into Setup Wizard without uninstalling the service
- persisted writes use atomic file replacement helpers
