# VisionDesk project context

Maintainer reference for VisionDesk **1.0.0**. This file is a code map, not an
end-user installation guide; use [setup.md](setup.md) for deployment steps.

## Product boundary

VisionDesk is one native `PySide6 + Qt Quick/QML` appliance application. In
production, `visiondesk.service` launches `qt_app.main`. There is no Flask,
Chromium, or permanent LAN web UI.

The only HTTP component is `system/setup_portal.py`: a short-lived phone
provisioning server bound to the temporary protected AP while setup is
incomplete. It is part of the native application lifecycle, not a second UI
runtime.

The product currently provides:

- Setup, Home, Camera, Processing, Result, History, History Detail, and Error
  screens.
- Five modes: `read_text`, `summarize_document`, `analyze_image`,
  `professional_assistant`, and `solve_problem`.
- A six-step setup state machine: welcome, Wi-Fi, OpenAI, camera, GPIO, finish.
- Non-touch GPIO navigation and capture controls.
- Text-only history, bounded private retry media, reset flows, and
  readiness-verified updates.

## Entrypoints

```bash
python -m qt_app.main --windowed --mock-hardware
python -m qt_app.main
python -m pytest -q
python tools/capture_ui_screenshots.py
sudo ./install.sh
sudo ./update.sh --check
sudo ./update.sh --local /path/to/release.tar.gz
sudo ./update.sh --rollback
sudo ./factory-reset.sh --mode user_data
sudo ./uninstall.sh
```

`update.sh --local` requires an archive with `manifest.json` and checksums.
**TODO:** no archive-building command is present in this repository.

## Main modules

- `visiondesk/version.py` — canonical application version.
- `visiondesk/paths.py` — development/production path resolver.
- `qt_app/main.py` — Qt bootstrap and QML loading.
- `qt_app/app_controller.py` — single QML-facing façade.
- `qt_app/runtime.py` — shared settings, paths, lifecycle, reset recovery, and
  service readiness wiring.
- `qt_app/setup_controller.py` — setup wizard and phone-portal lifecycle.
- `qt_app/pipeline_controller.py` — camera capture and analysis orchestration.
- `qt_app/history_controller.py`, `health_controller.py`, and
  `gpio_controller.py` — QML-facing feature controllers.
- `system/setup_flow.py` — authoritative persisted setup state and completion.
- `system/setup_portal.py` and `system/device_setup.py` — temporary AP, local
  portal, Wi-Fi scan/connection, and credential handoff.
- `system/result_history.py`, `offline_retry.py`, `factory_reset.py`,
  `migrations.py`, `diagnostics.py`, and `readiness.py` — persistence and
  lifecycle services.
- `ai/modes.py` — canonical mode prompts and compatibility aliases.
- `deployment/` — systemd launcher/service and NetworkManager PolicyKit rule.

## Persistent state

| Development | Production | Purpose |
| --- | --- | --- |
| `config/device.yaml` | `/etc/visiondesk/device.yaml` | Device configuration |
| `.env` | `/etc/visiondesk/visiondesk.env` | Secrets and environment overrides |
| `data/setup_state.json` | `/var/lib/visiondesk/setup_state.json` | Authoritative setup state |
| `data/result_history.json` | `/var/lib/visiondesk/result_history.json` | Text-only history |
| `data/private/` | `/var/lib/visiondesk/private/` | Private media, retry state, cache, quarantine |
| `logs/` | `/var/log/visiondesk/` | Runtime and lifecycle logs |

`setup_state.json` is the source of truth for setup routing. Completion also
updates `device.yaml` for compatibility. The factory configuration begins with
`setup.completed: false` so a new appliance enters Setup.

## Invariants

- Do not expose an OpenAI key to QML, history, or logs. A candidate key must
  verify before persistence.
- Keep result history text-only by default; use the private storage tree for
  transient/retry media.
- Preserve `/etc/visiondesk`, `/var/lib/visiondesk`, and `/var/log/visiondesk`
  on normal uninstall. `--purge` is the explicit destructive path.
- Keep production writes within the paths allowed by `visiondesk.service`.
- Do not replace the temporary WPA2 phone setup channel with an open AP or a
  general LAN bind.

See [docs/architecture.md](docs/architecture.md) for the full runtime and
deployment design.
