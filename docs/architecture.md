# VisionDesk architecture

Applies to VisionDesk **1.0.0**. VisionDesk is a native Raspberry Pi desktop
appliance, not a browser kiosk. `visiondesk.service` starts the only production
UI: the `PySide6 + Qt Quick/QML` application in `qt_app/`.

## Runtime flow

```text
Qt/QML screens
        │
qt_app.app_controller and feature controllers
        │
qt_app.runtime
        ├── setup state and diagnostics
        ├── camera, vision, pipeline, and AI modules
        ├── history, retry queue, health, reset, and readiness services
        └── GPIO integration
        │
private local storage  ←→  OpenAI API
```

`qt_app/main.py` creates the Qt application, image provider, runtime, and
QML-facing controller. The main screen set is Setup, Home, Camera, Processing,
Result, History, History Detail, and Error. `system/ui_catalog.py` supplies the
six setup steps and the five UI modes.

The five canonical AI modes are Read Text, Summarize Document, Analyze Image,
Professional Assistant, and Solve Problem. Their system prompts and output
contracts live in `ai/modes.py`; legacy names are aliases for compatibility,
not additional modes.

## First boot and phone provisioning

`system/setup_flow.py` owns the authoritative setup state. On a newly installed
device, the factory config sets `setup.completed: false`, so the application
routes to Setup. Completion updates both persistent setup state and the device
configuration.

`qt_app/setup_controller.py` auto-starts `system/setup_portal.py` only when all
of these are true:

- the app is running on physical hardware, not `--mock-hardware`;
- setup is incomplete;
- `setup_portal.enabled` and its auto-start setting are enabled.

The portal asks NetworkManager to create a temporary protected AP, binds its
small HTTP server only to the configured AP address, and shows its URL, QR code,
SSID/password, and eight-digit pairing code on the QML Setup screen. It is not
a permanent web UI and is not intended to bind to a normal LAN. The portal
submits Wi-Fi credentials and an OpenAI key to the setup controller, then stops
and removes the temporary AP before Wi-Fi/key validation continues.

For the operator workflow and recovery steps, see
[phone_setup.md](phone_setup.md).

## Deployment model

`install.sh`, run from a checked source tree, does the following:

1. Validates prerequisites, installs system packages, creates the dedicated
   `visiondesk` user/group, and installs the narrow NetworkManager PolicyKit
   rule in `deployment/49-visiondesk-networkmanager.rules`.
2. Seeds `/etc/visiondesk/device.yaml` and `/etc/visiondesk/visiondesk.env` on
   first install.
3. Copies the source into `/opt/visiondesk/releases/<version>`, builds its
   virtual environment, and points `/opt/visiondesk/current` to that release.
4. Installs `deployment/visiondesk.service`; its launcher waits for X11 or
   Wayland and executes `python -m qt_app.main` as user `visiondesk`.
5. Runs migrations and diagnostics, then starts the service. The install script
   restores its prior state when installation fails.

The service has no general web-server dependency. Its systemd sandbox permits
write access only to `/etc/visiondesk`, `/var/lib/visiondesk`, and
`/var/log/visiondesk`.

`update.sh --local` accepts a local archive only when it contains
`manifest.json` and the declared checksum file. It builds an isolated
environment, runs migrations and diagnostics, switches the `current` symlink,
then requires a fresh readiness marker from the expected service process and a
stable running period. Otherwise it restores the prior release.

**TODO:** The repository contains the updater but not a command that builds the
required release archive and manifest.

## Storage and configuration

| Location | Responsibility |
| --- | --- |
| `/opt/visiondesk/current` | Active release symlink |
| `/opt/visiondesk/releases/<version>` | Installed release directories |
| `/etc/visiondesk/device.yaml` | Durable device configuration |
| `/etc/visiondesk/visiondesk.env` | OpenAI key and path overrides; installed with mode `0600` |
| `/var/lib/visiondesk/setup_state.json` | Authoritative setup progress and completion |
| `/var/lib/visiondesk/result_history.json` | Text-only result history |
| `/var/lib/visiondesk/latest_result.txt` | Latest non-sensitive result summary |
| `/var/lib/visiondesk/private/` | Current media, retry media, cache, queue metadata, and quarantine files |
| `/var/lib/visiondesk/runtime/readiness.json` | Non-secret startup marker for install/update validation |
| `/var/lib/visiondesk/factory_reset_state.json` | Reset recovery marker |
| `/var/log/visiondesk/` | Application and lifecycle logs |

In development, `visiondesk/paths.py` resolves the same concerns under the
repository: `config/device.yaml`, `.env`, `data/`, and `logs/`. Supported path
overrides are `VISIONDESK_PATH_MODE`, `DEVICE_CONFIG_PATH`,
`VISIONDESK_ENV_FILE`, `VISIONDESK_DATA_DIR`, and `VISIONDESK_LOG_DIR`.

## Data and safety boundaries

- Result history stores text and safe metadata by default; retry media remains
  under the private data tree and is bounded by retention settings.
- Candidate OpenAI keys are verified before persistence. QML receives only
  configured/not-configured state, never a raw or masked key.
- Setup, history, and reset writes use atomic replacement; corrupt persisted
  data is quarantined rather than silently reused.
- User-Data Reset clears user content while preserving configuration and
  secrets. Configuration Reset clears setup/configuration credentials and
  returns the app to Setup. Factory Reset combines those actions and can remove
  the saved Wi-Fi profile.

Operational commands and a new-device installation guide are in
[../setup.md](../setup.md).
