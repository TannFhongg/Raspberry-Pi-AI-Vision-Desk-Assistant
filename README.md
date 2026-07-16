# VisionDesk

**Version 1.0.4** — Raspberry Pi AI Vision Desk Assistant. Documentation was
synchronized for tag `v1.0.4` on 2026-07-16.

VisionDesk is a native `PySide6 + Qt Quick/QML` appliance for a Raspberry Pi 5.
It captures a USB-camera image, prepares it locally, sends the image to OpenAI,
and presents the result in a fullscreen desktop interface. The production UI is
one `systemd` service, `visiondesk.service`; there is no Chromium kiosk, Flask
application, or persistent browser-based management UI.

## What is in this repository

- Eleven QML screens: Setup, Home, Camera, Review and Adjust, Processing,
  Result, History, History Detail, Error, Settings, and Device Health.
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

The primary production display target is the panel's native **1366 x 768**
geometry. VisionDesk renders directly into the fullscreen Qt window; it does not
scale or stretch an older design canvas. The previously documented 1200 x 800
target was an incorrect early assumption and is retained only in explicitly
marked historical material.

Not implemented: text-to-speech / “Hear printed text”. Do not present it as a
delivered feature.

Current `v1.0.4` UI status:

- The application renders responsively at the 1366 x 768 production target
  without a root-level design-canvas transform.
- Finish Setup validation cards use content-driven heights, wrapped diagnostics,
  equal heights within each two-column row, and a scrollable body above the
  fixed Back/Ready footer.
- Desktop mock limitations are labeled as expected mock-mode limitations;
  raw GPIO implementation exceptions are not used as the primary message.
- The current documentation capture set contains 27 individual 1366 x 768
  screenshots plus one contact sheet.
- The verified split regression run contains 239 passing tests. Physical HDMI,
  camera, and GPIO validation is still required on the target Pi; any optional
  touch controller is also unverified.

## Hardware target

- Raspberry Pi 5 (8 GB), USB-C 5 V/5 A power supply, cooling, and microSD card.
- Raspberry Pi OS Desktop 64-bit with a graphical session.
- USB webcam and 11.6-inch HDMI display.
- Native display output at 1366 x 768 with desktop scaling at 100%.
- Noto Sans (installed by `install.sh`) or the automatic Inter, DejaVu Sans,
  bundled Roboto fallback.
- Ten momentary GPIO buttons; the exact BCM mapping is in
  [setup-en.md](setup-en.md) and [hardware_require.txt](hardware_require.txt).
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
instructions, see [setup-en.md](setup-en.md).

Run the deterministic desktop flow without a camera, GPIO, Wi-Fi, or an API
key:

```bash
python -m qt_app.main --windowed --mock-hardware
```

Run the test suite on Linux/Raspberry Pi OS:

```bash
python -m pytest -q
```

On Windows, keep the non-Qt and Qt application groups in separate processes.
This avoids a native OpenCV/PySide teardown conflict observed when both stacks
are loaded by one pytest process:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
$env:QT_QUICK_BACKEND = "software"
$env:QSG_RHI_BACKEND = "software"
python -m pytest -q --ignore=tests/test_qt_app.py
python -m pytest -q tests/test_qt_app.py
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
git clone --depth 1 --branch v1.0.4 \
  https://github.com/TannFhongg/Raspberry-Pi-AI-Vision-Desk-Assistant.git \
  ~/visiondesk
cd ~/visiondesk
git describe --tags --exact-match
chmod +x install.sh
sudo ./install.sh
```

On a new appliance, reboot once if the installer reports that the configured
`visiondesk` graphical session is not active yet. This lets LightDM replace the
administrator's current desktop session with the dedicated appliance session:

```bash
sudo reboot
```

If the camera or GPIO hardware is not connected yet, install the software first
and defer those checks explicitly:

```bash
sudo ./install.sh --skip-hardware-check
```

Production deployments use the fixed `v1.0.4` tag. Developers may use `master`
for ongoing work, but it is not a production deployment target.

The factory configuration has `setup.completed: false`. After the first boot,
the device enters Welcome and attempts phone-first setup when the Wi-Fi adapter
supports protected AP mode. Enter the OpenAI key during setup; do not put it in
the cloned source tree for a new device.

The complete fresh-device, first-boot, GPIO, service, update, reset, and demo
procedure is in [setup-en.md](setup-en.md).

## Operating an installed device

```bash
sudo systemctl status visiondesk.service
sudo systemctl restart visiondesk.service
journalctl -u visiondesk.service -f
sudo ./update.sh --check
```

Use the official package builder and verifier before a local update. The release
format, GitHub upload, dry-run, update, and rollback instructions are in
[docs/release-packaging.md](docs/release-packaging.md).

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

- [setup-en.md](setup-en.md) — English end-to-end guide for development, a new Pi,
  phone setup, demo, service operations, update, reset, and uninstall.
- [setup-vi.md](setup-vi.md) — Vietnamese version of the end-to-end setup guide.
- [docs/architecture.md](docs/architecture.md) — runtime, storage, deployment,
  setup, and privacy design.
- [docs/phone_setup.md](docs/phone_setup.md) — phone-first provisioning and
  recovery boundary.
- [docs/demo_checklist.md](docs/demo_checklist.md) — factual product-demo
  checklist.
- [docs/release-packaging.md](docs/release-packaging.md) — official appliance
  archive contract, build, verification, GitHub upload, update, and rollback.
- [docs/display-1366x768-text-readability-report.md](docs/display-1366x768-text-readability-report.md)
  — current display, typography, Finish Setup, test, and screenshot status.
- [docs/1366x768-hardware-validation.md](docs/1366x768-hardware-validation.md)
  — required real Raspberry Pi/HDMI validation checklist.
- [docs/ui-commercial-upgrade-report.md](docs/ui-commercial-upgrade-report.md)
  — historical record of the earlier commercial UI/camera-review upgrade.
- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md) — concise code map and operational
  invariants for contributors.
