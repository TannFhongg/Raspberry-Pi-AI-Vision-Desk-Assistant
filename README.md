# Raspberry Pi AI Vision Desk Assistant

VisionDesk is a Raspberry Pi appliance built around a native `PySide6 + Qt Quick/QML` interface. It captures an image from a USB camera, preprocesses it, sends it to OpenAI, and shows the result directly in the Qt UI with shared setup, GPIO, health, history, offline retry, and privacy-aware local storage.

The shipped product is a single Qt app managed by `systemd`. There is no Flask/Chromium kiosk stack in production.

## Highlights

- native Qt/QML screens for `setup`, `home`, `camera`, `processing`, `result`, `history`, `history_detail`, and `error`
- authoritative 6-step setup wizard: welcome/device checks, Wi-Fi, OpenAI key, camera test, GPIO test, finish
- shared version and path resolution through `visiondesk/version.py` and `visiondesk/paths.py`
- production-safe persistence for config, secrets, user data, logs, retry state, and reset recovery markers
- device actions for clear history, user-data reset, configuration reset, and full factory reset

## Supported deployment model

- Raspberry Pi OS Desktop with LightDM-managed autologin
- ARM Raspberry Pi target
- dedicated desktop user: `visiondesk`
- single supported UI service: `visiondesk.service`
- versioned releases under `/opt/visiondesk/releases/<version>`

## Development commands

Install Python dependencies:

```bash
pip install -r requirements.txt
```

Run locally in a normal window with deterministic mock services:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Run the direct Qt entrypoint without the installed service wrapper:

```bash
python -m qt_app.main
```

Run tests:

```bash
pytest -q
```

## Appliance lifecycle commands

Install onto a Raspberry Pi appliance:

```bash
sudo ./install.sh [--non-interactive] [--skip-hardware-check] [--reset-config] [--force]
```

Check an installed appliance:

```bash
sudo ./update.sh --check
```

Stage and apply a technician-supplied local archive update:

```bash
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz [--version 1.2.3] [--dry-run]
```

Rollback to the previous release recorded by the last successful update:

```bash
sudo ./update.sh --rollback
```

Remove the app and service while preserving config, data, and logs by default:

```bash
sudo ./uninstall.sh [--purge] [--keep-logs] [--yes] [--dry-run]
```

Run a factory reset without uninstalling the app:

```bash
sudo ./factory-reset.sh --mode {configuration|user_data|factory_reset} [--remove-wifi] [--yes] [--phrase "ERASE VISIONDESK"] [--dry-run]
```

## Production service

The production UI is defined by:

- `deployment/visiondesk.service`
- `deployment/visiondesk-launch.sh`

Useful service commands:

```bash
sudo systemctl start visiondesk.service
sudo systemctl restart visiondesk.service
sudo systemctl status visiondesk.service
journalctl -u visiondesk.service -f
```

## Filesystem layout

Production layout:

- `/opt/visiondesk/releases/<version>`: staged immutable release directories
- `/opt/visiondesk/current`: active release symlink
- `/etc/visiondesk/device.yaml`: durable device config
- `/etc/visiondesk/visiondesk.env`: durable secrets and path overrides
- `/var/lib/visiondesk/setup_state.json`: authoritative setup wizard state
- `/var/lib/visiondesk/result_history.json`: saved text-only history
- `/var/lib/visiondesk/latest_result.txt`: latest non-sensitive result summary
- `/var/lib/visiondesk/private/`: current media, retry media, cache, queue data, and quarantine files
- `/var/lib/visiondesk/factory_reset_state.json`: reset recovery marker
- `/var/log/visiondesk/`: service and lifecycle logs such as `install.log` and `update.log`

Development defaults:

- `config/device.yaml`
- `.env`
- `data/`
- `logs/`

Development and production both flow through `visiondesk/paths.py`, with explicit overrides available via `VISIONDESK_PATH_MODE`, `DEVICE_CONFIG_PATH`, `VISIONDESK_ENV_FILE`, `VISIONDESK_DATA_DIR`, and `VISIONDESK_LOG_DIR`.

## Setup and reset behavior

- setup routing reads `/var/lib/visiondesk/setup_state.json` in production and falls back safely if the file is missing or corrupt
- setup completion is mirrored into `device.yaml` for compatibility, but the setup-state file is the routing source of truth
- the OpenAI key is stored in `visiondesk.env` with restrictive permissions and is never returned raw to QML after save
- `User-Data Reset` clears history, retry queue, cached previews, and private media
- `Configuration Reset` clears setup completion, config overrides, and the OpenAI key, then relaunches into Setup Wizard
- `Full Factory Reset` combines both and can optionally remove the saved Wi-Fi profile

## Project layout

- `visiondesk/`: shared version and filesystem path resolver
- `qt_app/`: native app runtime, controllers, image provider, models, and QML
- `system/`: setup, diagnostics, history, health, logging, retry, migrations, and reset logic
- `camera/`, `vision/`, `pipeline/`, `ai/`, `hardware/`: reusable backend modules
- `deployment/`: systemd and launcher assets for the installed appliance
- `tests/`: backend and Qt coverage
