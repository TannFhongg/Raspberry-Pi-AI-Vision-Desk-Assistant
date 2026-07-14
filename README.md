# VisionDesk

VisionDesk is a Raspberry Pi appliance built around a native `PySide6 + Qt Quick/QML` interface. It captures an image from a USB camera, preprocesses it, sends it to OpenAI, and presents the result in the Qt UI. Setup, GPIO, health checks, history, offline retry, storage retention, and recovery use shared backend services.

The shipped product is one native Qt application managed by `systemd`; production does not use a Flask, browser, or Chromium kiosk stack.

## Highlights

- native Qt/QML screens for setup, home, camera, processing, results, history, and errors
- authoritative six-step setup wizard for device checks, Wi-Fi, OpenAI, camera, GPIO, and completion
- candidate OpenAI keys are verified before they are persisted
- text-only history by default, with bounded private media storage for retries
- atomic persistence, corrupt-state quarantine, and reset recovery
- versioned releases with readiness-verified update and automatic rollback

## Development quick start

Requirements:

- Python `3.10+`
- a desktop session for Qt Quick/QML
- a valid OpenAI API key only when testing real analysis

From the repository root, create and use the project virtual environment.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create `.env` from the example when you want the documented defaults:

```powershell
Copy-Item .env.example .env
```

For development, the strict minimum for real OpenAI analysis is:

```dotenv
OPENAI_API_KEY=sk-your-real-key
```

`OPENAI_MODEL` is optional and defaults to `gpt-5.4-mini`. `DEVICE_CONFIG_PATH` is optional when running from this repository because it already defaults to `config/device.yaml`. Keep the following explicit values if preferred:

```dotenv
OPENAI_API_KEY=sk-your-real-key
OPENAI_MODEL=gpt-5.4-mini
DEVICE_CONFIG_PATH=config/device.yaml
```

Copy the full `.env.example` only when overriding camera, GPIO, display, reliability, retention, or offline-retry defaults. Do not commit `.env` or share an API key. The mock desktop flow can start without a key; completing live OpenAI setup and analysis requires a verified key.

Run the desktop app with deterministic mock services:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Run against connected local hardware:

```bash
python -m qt_app.main
```

## Display configuration

The production hardware profile uses an 11.6-inch non-touch HDMI display in landscape orientation. The Qt/QML layout has a 1200x800 design canvas. In normal kiosk operation the app runs fullscreen at the HDMI panel's native resolution; it does not force the panel to 1200x800.

`display.size` in `config/device.yaml` and `UI_SCREEN_WIDTH` / `UI_SCREEN_HEIGHT` in `.env` control the initial size only when the app is run with `--windowed`. Keep them at `1200x800` for the design reference. The display has no touch input: GPIO 23/24/25 provide Up, Down, and Select for normal navigation. Retain a USB keyboard and mouse for setup and administrative text entry.

## Phone-first setup on a non-touch panel

On an unfinished physical appliance, VisionDesk can create a short-lived WPA2 setup network so that Wi-Fi credentials and the OpenAI key can be entered from a phone. It is enabled by the `setup_portal` section in `config/device.yaml` (or the matching `SETUP_PORTAL_*` variables), starts automatically only while setup is incomplete, and is never started in `--mock-hardware` development mode.

1. On the VisionDesk Welcome screen, join the displayed `VisionDesk-Setup-XXXX` network with its one-time password.
2. Scan the displayed QR code or open the displayed local address. The QR code contains the address only, never a password or API key.
3. Enter the eight-digit pairing code shown on the panel, choose the nearby Wi-Fi, and enter its password plus the OpenAI key.
4. VisionDesk acknowledges the request, stops and deletes the temporary AP, connects to the chosen Wi-Fi, verifies the key, runs the camera check, and then asks the operator to press each physical button once.

The portal is bound only to its AP address, has a 15-minute default lifetime, requires the pairing code before its JSON APIs are available, and uses a short-lived `HttpOnly; SameSite=Strict` cookie. Wi-Fi and OpenAI credentials are not returned to QML, included in the QR code, or intentionally logged. The temporary portal is HTTP rather than TLS because it is reachable only after joining the random WPA2-protected AP; do not expose its address through another network or replace it with an open AP.

The installer installs a narrowly enumerated NetworkManager PolicyKit rule for the dedicated `visiondesk` group, covering Wi-Fi scan, protected AP creation, connection control, and system-profile modification. On the Pi, confirm the actual distribution policy with:

```bash
nmcli general permissions
```

If the Wi-Fi adapter does not support AP mode or NetworkManager is unavailable, the panel reports the failure and the existing keyboard/mouse setup path remains available. Detailed operating and recovery instructions are in [docs/phone_setup.md](docs/phone_setup.md).

Run tests:

```bash
pytest -q
```

## Raspberry Pi appliance

Supported production target:

- Raspberry Pi OS Desktop with LightDM-managed autologin
- ARM Raspberry Pi device
- dedicated `visiondesk` user
- one supported UI service: `visiondesk.service`
- versioned releases under `/opt/visiondesk/releases/<version>`

Install from the repository on the Pi:

```bash
sudo ./install.sh [--non-interactive] [--skip-hardware-check] [--reset-config] [--force]
```

The installer creates the release virtual environment itself, seeds `/etc/visiondesk/visiondesk.env`, and configures `/etc/visiondesk/device.yaml`. On an installed appliance, use `/etc/visiondesk/device.yaml` rather than the repository-relative development path.

Use the on-device setup wizard to enter and verify the OpenAI key. A submitted candidate key stays in memory until verification succeeds; QML receives only a generic configured/not-configured status, never the key or a masked derivative.

Useful service commands:

```bash
sudo systemctl status visiondesk.service
sudo systemctl restart visiondesk.service
journalctl -u visiondesk.service -f
```

## Updates and recovery

Check the installed appliance:

```bash
sudo ./update.sh --check
```

Stage and apply a technician-supplied local archive:

```bash
sudo ./update.sh --local /path/to/visiondesk-release.tar.gz [--version 1.2.3] [--dry-run]
```

Rollback to the previous release recorded by the last successful update:

```bash
sudo ./update.sh --rollback
```

Before switching releases, the updater validates the archive manifest and checksums, builds an isolated environment, runs migrations and diagnostics, and restarts the Qt service. Success requires a fresh non-secret readiness marker for the expected release and service PID, then a stable running period. Merely reporting `active` is not sufficient. Failed startup automatically switches back and verifies the prior release is ready.

The default startup timeout is 60 seconds and stability window is 20 seconds. A technician may tune `UPDATE_STARTUP_TIMEOUT_SECONDS`, `UPDATE_STABILITY_SECONDS`, and `READINESS_MAX_AGE_SECONDS` for a slow device.

## Reset and uninstall

Remove the app and service while preserving configuration, data, and logs by default:

```bash
sudo ./uninstall.sh [--purge] [--keep-logs] [--yes] [--dry-run]
```

Run a reset without uninstalling the application:

```bash
sudo ./factory-reset.sh --mode {configuration|user_data|factory_reset} [--remove-wifi] [--yes] [--phrase "ERASE VISIONDESK"] [--dry-run]
```

- `User-Data Reset` clears history, retry queue, cached previews, and private media.
- `Configuration Reset` clears setup completion, configuration overrides, and the OpenAI key, then returns to Setup Wizard.
- `Full Factory Reset` performs both operations and can remove the saved Wi-Fi profile.

## Filesystem layout

Production layout:

- `/opt/visiondesk/releases/<version>`: immutable staged releases
- `/opt/visiondesk/current`: active release symlink
- `/etc/visiondesk/device.yaml`: durable device configuration
- `/etc/visiondesk/visiondesk.env`: private secrets and path overrides, mode `0600`
- `/var/lib/visiondesk/setup_state.json`: authoritative setup state
- `/var/lib/visiondesk/result_history.json`: text-only history
- `/var/lib/visiondesk/latest_result.txt`: latest non-sensitive result summary
- `/var/lib/visiondesk/private/`: current media, retry media, cache, queue data, and quarantine files
- `/var/lib/visiondesk/runtime/readiness.json`: ephemeral, non-secret update readiness marker
- `/var/lib/visiondesk/factory_reset_state.json`: reset recovery marker
- `/var/log/visiondesk/`: service and lifecycle logs

Development defaults:

- `config/device.yaml`
- `.env`
- `data/`
- `logs/`

Both environments use `visiondesk/paths.py`. The supported overrides are `VISIONDESK_PATH_MODE`, `DEVICE_CONFIG_PATH`, `VISIONDESK_ENV_FILE`, `VISIONDESK_DATA_DIR`, and `VISIONDESK_LOG_DIR`.

## Project layout

- `visiondesk/`: version and filesystem path resolution
- `qt_app/`: native runtime, controllers, image provider, models, and QML
- `system/`: setup, diagnostics, readiness, history, health, logging, retry, migrations, and reset logic
- `camera/`, `vision/`, `pipeline/`, `ai/`, `hardware/`: reusable backend modules
- `deployment/`: systemd and launcher assets
- `tests/`: backend, Qt, and deployment coverage
