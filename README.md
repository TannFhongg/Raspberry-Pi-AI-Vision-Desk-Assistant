# VisionDesk

**Version 1.0.0** — Raspberry Pi AI Vision Desk Assistant.

VisionDesk is a native `PySide6 + Qt Quick/QML` appliance for a Raspberry Pi 5.
It captures a USB-camera image, prepares it locally, sends the image to OpenAI,
and presents the result in a fullscreen desktop interface. The production UI is
one `systemd` service, `visiondesk.service`; there is no Chromium kiosk, Flask
application, or persistent browser-based management UI.

## What is in this repository

- Eight QML screens: Setup, Home, Camera, Processing, Result, History, History
  Detail, and Error.
- Five distinct AI workflows: Read Text, Summarize Document, Analyze Image,
  Professional Assistant, and Solve Problem.
- A six-step setup flow for Wi-Fi, OpenAI key verification, camera, GPIO, and
  completion.
- A short-lived, WPA2-protected phone setup network for a new physical device.
  It displays a QR URL and an eight-digit pairing code on the VisionDesk panel.
- GPIO control for a non-touch display, text-only result history, bounded
  private retry media, reset actions, and versioned on-device releases.

The current product profile is an 11.6-inch landscape HDMI display without
touch input. Normal operation uses ten GPIO buttons. Keep a USB keyboard and
mouse available for recovery and administrative text entry.

Not implemented: text-to-speech / “Hear printed text”. Do not present it as a
delivered feature.

## Hardware target

- Raspberry Pi 5 (8 GB), USB-C 5 V/5 A power supply, cooling, and microSD card.
- Raspberry Pi OS Desktop 64-bit with a graphical session.
- USB webcam and 11.6-inch HDMI display.
- Ten momentary GPIO buttons; the exact BCM mapping is in
  [setup.md](setup.md) and [hardware_require.txt](hardware_require.txt).
- Wi-Fi managed by NetworkManager. AP/hotspot support is required only for
  phone-first setup; keyboard/mouse setup remains available as a fallback.

## Development quick start

Python 3.10 or newer is required. Create a virtual environment from the
repository root.

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Linux / Raspberry Pi OS Desktop:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

For the Linux Qt system packages and the complete Windows/Linux development
instructions, see [setup.md](setup.md).

Run the deterministic desktop flow without a camera, GPIO, Wi-Fi, or an API
key:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Run the test suite:

```bash
python -m pytest -q
```

For a headless Linux/SSH test run:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
```

To use real OpenAI analysis during development, copy `.env.example` to `.env`
and set `OPENAI_API_KEY`. Never commit `.env` or place credentials in a command,
screenshot, or log.

## Install a new Raspberry Pi appliance

`install.sh` packages the source directory from which it runs into a release at
`/opt/visiondesk/releases/<version>` and starts
`/opt/visiondesk/current` through `visiondesk.service`. Therefore a new Pi must
first receive this repository or an equivalent checked source tree.

```bash
sudo apt update
sudo apt install -y git
git clone --depth 1 --branch master \
  https://github.com/TannFhongg/Raspberry-Pi-AI-Vision-Desk-Assistant.git \
  ~/visiondesk
cd ~/visiondesk
git rev-parse --short HEAD
sudo ./install.sh
```

The repository currently has no release tag. Record the printed commit ID with
each deployed device. **TODO:** create an audited, versioned release/tag process
before commercial handoff so installations are not taken from a moving branch.

The factory configuration has `setup.completed: false`. After the first boot,
the device enters Welcome and attempts phone-first setup when the Wi-Fi adapter
supports protected AP mode. Enter the OpenAI key during setup; do not put it in
the cloned source tree for a new device.

The complete fresh-device, first-boot, GPIO, service, update, reset, and demo
procedure is in [setup.md](setup.md).

## Operating an installed device

```bash
sudo systemctl status visiondesk.service
sudo systemctl restart visiondesk.service
journalctl -u visiondesk.service -f
sudo ./update.sh --check
```

`update.sh --local /path/to/archive.tar.gz` accepts only a technician-supplied
archive that contains `manifest.json` and its checksum file. The updater verifies
the archive, creates an isolated environment, runs migrations and diagnostics,
and rolls back if the new service does not produce a matching readiness marker
and remain stable. **TODO:** this repository does not yet provide a release
archive creation command.

Persistent paths on the appliance:

| Path | Purpose |
| --- | --- |
| `/opt/visiondesk/current` | Active release symlink |
| `/opt/visiondesk/releases/<version>` | Versioned application releases |
| `/etc/visiondesk/device.yaml` | Device configuration |
| `/etc/visiondesk/visiondesk.env` | Secrets and path overrides; mode `0600` |
| `/var/lib/visiondesk/` | Setup state, history, private retry data, readiness markers |
| `/var/log/visiondesk/` | Install, update, and service logs |

## Documentation

- [setup.md](setup.md) — Vietnamese end-to-end guide for development, a new Pi,
  phone setup, demo, service operations, update, reset, and uninstall.
- [docs/architecture.md](docs/architecture.md) — runtime, storage, deployment,
  setup, and privacy design.
- [docs/phone_setup.md](docs/phone_setup.md) — phone-first provisioning and
  recovery boundary.
- [docs/demo_checklist.md](docs/demo_checklist.md) — factual product-demo
  checklist.
- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — concise code map and operational
  invariants for contributors.
