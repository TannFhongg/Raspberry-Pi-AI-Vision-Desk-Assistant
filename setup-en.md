# VisionDesk Setup and Demo Guide

Applies to VisionDesk **1.0.0**.

This document reflects the project’s current state: a Raspberry Pi appliance running a
native \`PySide6 + Qt Quick/QML\` application, with an 11.6-inch non-touch HDMI display,
10 GPIO buttons, and first-time setup from a phone through a temporary Wi-Fi AP.

## 1. Current scope

- Eight main screens: Setup, Home, Camera, Processing, Result, History,
  History Detail, and Error.
- Five independent AI workflows: Read Text, Summarize Document, Analyze Image,
  Professional Assistant, and Solve Problem.
- The 11.6-inch display is non-touch: navigate with GPIO Up/Down/Select; keep a
  keyboard and mouse available for recovery and administration.
- Phone-first setup: QR code, temporary SSID/password, and a pairing code appear while
  setup is incomplete; use a phone to enter the target Wi-Fi details and OpenAI API key.
- Production runs only the native Qt service \`visiondesk.service\`; Flask is not part of
  the product runtime. The phone portal uses a short-lived internal HTTP server.

## 2. Required hardware

- Raspberry Pi 5 8GB, 5V/5A USB-C power supply, 32GB or larger microSD card, and a
  cooling fan/case.
- USB webcam.
- 11.6-inch landscape HDMI display, non-touch, with an appropriate HDMI cable.
- A Wi-Fi adapter managed by NetworkManager and supporting protected AP/hotspot mode if
  you want to use phone-first setup.
- Ten momentary push buttons, jumper wires, and a breadboard (recommended).

Default BCM GPIO pins:

| Function | GPIO |
| --- | ---: |
| Capture | 17 |
| Read Text | 5 |
| Summarize Document | 6 |
| Analyze Image | 13 |
| Professional Assistant | 19 |
| Solve Problem | 26 |
| Back | 22 |
| Navigate Up | 23 |
| Navigate Down | 24 |
| Select / Confirm | 25 |

An Ethernet cable is optional. Bring Ethernet, a keyboard/mouse, and a mobile hotspot as
fallback options for the demo.

## 3. Development environment

General requirements: Python 3.10 or newer, plus an X11/Wayland desktop session when
running Qt/QML with a window. The Linux environment below is for an Ubuntu/Debian or
Raspberry Pi OS Desktop development machine; it does not replace the appliance
installation process in section 6.

### 3.1 Windows

From the project directory:

\`\`\`powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
\`\`\`

### 3.2 Linux (Ubuntu/Debian/Raspberry Pi OS Desktop)

Install Python, virtual-environment tools, and the Qt libraries required for PySide6 to
run on X11/Wayland. You do not need to install \`python3-rpi.gpio\` or NetworkManager on a
development machine without GPIO or the phone portal.

\`\`\`bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv \
  libdbus-1-3 libegl1 libgl1 libopengl0 libx11-xcb1 libxcb-cursor0 \
  libxcb-keysyms1 libxcb-icccm4 libxcb-image0 libxcb-randr0 \
  libxcb-render-util0 libxcb-xfixes0 libxcb-xinerama0 libxkbcommon-x11-0

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
\`\`\`

On headless Linux or over SSH, run windowless tests by setting Qt to offscreen mode:

\`\`\`bash
QT_QPA_PLATFORM=offscreen python -m pytest -q
\`\`\`

Runtime Python dependencies are managed in \`requirements.txt\`: PySide6, the OpenAI SDK,
Pillow, \`python-dotenv\`, \`gpiozero\`, PyYAML, NumPy, and \`qrcode\`.
\`pytest\`/\`pytest-qt\` are for testing. Flask is not required to run the current
application.

Create \`.env\` if you need to override local configuration:

\`\`\`powershell
Copy-Item .env.example .env
\`\`\`

On Linux, use:

\`\`\`bash
cp .env.example .env
\`\`\`

To run real OpenAI analysis, add your API key to \`.env\`:

\`\`\`dotenv
OPENAI_API_KEY=sk-your-real-key
\`\`\`

Do not commit \`.env\` or share the key in chat, Git, or screenshots.

## 4. Run and test locally

Run the UI with simulated camera, GPIO, and pipeline:

\`\`\`bash
python -m qt_app.main --windowed --mock-hardware
\`\`\`

Run with local hardware:

\`\`\`bash
python -m qt_app.main
\`\`\`

Run the regression suite:

\`\`\`bash
python -m pytest -q
\`\`\`

Capture Qt/QML UI screenshots with mock data:

\`\`\`bash
python tools/capture_ui_screenshots.py
\`\`\`

Images are written to \`debug/ui-screenshots/\`; \`00-contact-sheet.png\` is a composite
of Setup, Home, Camera, Processing, Result, History, History Detail, and Error.

## 5. Display configuration and setup portal

\`display.size: 1200x800\` in \`config/device.yaml\` is the reference canvas when running
windowed. In the production kiosk, the application is fullscreen at the HDMI display’s
native resolution; this value does not change the hardware resolution.

Phone-first portal configuration:

\`\`\`yaml
setup_portal:
  enabled: true
  auto_start_when_setup_incomplete: true
  session_timeout_minutes: 15
  interface: wlan0
  address: 192.168.4.1
  port: 80
  ssid_prefix: VisionDesk-Setup
\`\`\`

The portal starts only on a real device whose setup is incomplete. It does not run with
\`--mock-hardware\`. The QR code contains only the local URL, for example
\`http://192.168.4.1\`; the temporary Wi-Fi password and 8-digit pairing code appear on
the VisionDesk screen.

The shipped configuration sets \`setup.completed: false\`, so a new device enters Welcome
and displays phone-first setup immediately after the initial installation. Use the
Configuration Reset in section 9 only when you need to return an operating device to the
first-boot flow.

## 6. Install a new Raspberry Pi device

The production target is Raspberry Pi OS Desktop 64-bit, LightDM autologin, and a
dedicated \`visiondesk\` user. The source/release must be available on the Pi before
running the installer: \`install.sh\` packages that source directory into the active
release under \`/opt/visiondesk\`.

### 6.1 Prepare the operating system

1. Use Raspberry Pi Imager to write **Raspberry Pi OS Desktop 64-bit** to the microSD
   card.
2. In Imager, set the username/password, time zone, and Wi-Fi; enable SSH if you will
   operate the device from another computer.
3. Connect the 11.6-inch HDMI display, webcam, keyboard/mouse, and network; boot the Pi
   and sign in.
4. Update the operating system and reboot:

\`\`\`bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
\`\`\`

After the Pi restarts, open Terminal or reconnect through SSH.

### 6.2 Get the correct release source

For the current repository, clone it into the administrator user’s home directory (do not
clone into \`/opt\` and do not use \`sudo git clone\`):

\`\`\`bash
sudo apt install -y git
git clone --depth 1 --branch v1.0.0 \
  https://github.com/TannFhongg/Raspberry-Pi-AI-Vision-Desk-Assistant.git \
  ~/visiondesk
cd ~/visiondesk
git describe --tags --exact-match
chmod +x install.sh
\`\`\`

Production is installed from the fixed \`v1.0.0\` tag, not \`master\`. \`master\` is for
development only. If the Pi has no internet connection, copy source already checked out
at the correct tag via USB or \`scp\`, then \`cd\` into that directory before installing.

You do not need to create \`.env\` in the source or set an OpenAI API key before installing
a new device. The API key is entered and verified during phone-first setup; the installer
creates the restricted secret file \`/etc/visiondesk/visiondesk.env\`.

### 6.3 Install the appliance

\`\`\`bash
sudo ./install.sh
\`\`\`

Options:

\`\`\`bash
sudo ./install.sh --non-interactive
sudo ./install.sh --skip-hardware-check
sudo ./install.sh --reset-config
sudo ./install.sh --force
\`\`\`

The installer installs system packages, creates the release virtual environment and
service, creates persistent directories, and adds a PolicyKit rule that limits
NetworkManager permissions for the \`visiondesk\` group. Once complete, the source in
\`~/visiondesk\` is only for maintenance/updates; the service runs the installed release
at \`/opt/visiondesk/current\`.

After installation, confirm:

\`\`\`bash
nmcli device status
nmcli general permissions
sudo systemctl status NetworkManager
sudo systemctl status visiondesk.service
\`\`\`

Production paths:

- \`/opt/visiondesk/current\`: active release.
- \`/etc/visiondesk/device.yaml\`: persistent device configuration.
- \`/etc/visiondesk/visiondesk.env\`: secrets, with \`0600\` permissions.
- \`/var/lib/visiondesk/\`: setup state, history, and private retry media.
- \`/var/log/visiondesk/\`: service and lifecycle logs.

Do not edit \`config/device.yaml\` in the release source to change production
configuration; use \`/etc/visiondesk/device.yaml\` and \`/etc/visiondesk/visiondesk.env\`.

## 7. Phone-first setup flow

Requirements: \`setup.completed: false\`, the portal enabled, \`wlan0\` supporting AP
mode, and NetworkManager available.

1. Power on VisionDesk and wait for the Welcome screen.
2. The screen displays a **Phone setup** card with the \`VisionDesk-Setup-XXXX\` SSID,
   temporary password, QR code, URL, and 8-digit pairing code.
3. Connect the phone to the temporary SSID, then scan the QR code or open the URL shown
   on the display.
4. Enter the pairing code, select the target Wi-Fi, and enter its Wi-Fi password and the
   OpenAI API key.
5. VisionDesk accepts the request, removes the temporary AP, connects to the target
   Wi-Fi, verifies the API key, and checks the camera.
6. Press each of the 10 GPIO buttons once to complete the wiring test.
7. The device restarts into Home.

If the AP does not start, use the Setup Wizard directly with a keyboard/mouse. Check
\`nmcli device status\`, \`nmcli general permissions\`, and
\`journalctl -u visiondesk.service -b\`.

## 8. Quick demo

1. Prepare a clearly printed document, a sample image, and a short problem.
2. Prepare stable internet Wi-Fi or a mobile hotspot, along with an API key that has
   available quota.
3. Demonstrate first boot via QR if the device is in the incomplete-setup state.
4. Demonstrate the five AI modes in turn, as well as Capture/Back/Up/Down/Select using
   the GPIO buttons.
5. Open Result and History to demonstrate text-only result storage.

Do not advertise “Hear printed text”/TTS as a completed feature: TTS is not implemented
in the current version.

## 9. Service, update, and reset

Manage the service:

\`\`\`bash
sudo systemctl restart visiondesk.service
sudo systemctl status visiondesk.service
journalctl -u visiondesk.service -f
\`\`\`

Update and roll back:

\`\`\`bash
sudo ./update.sh --check
sudo ./update.sh --local /path/to/visiondesk-1.0.0.tar.gz --version 1.0.0 --dry-run
sudo ./update.sh --local /path/to/visiondesk-1.0.0.tar.gz --version 1.0.0
sudo ./update.sh --rollback
\`\`\`

Build and verify the archive on a maintenance workstation, upload it as a GitHub Release,
and follow the \`manifest.json\` contract and checksum described in
[docs/release-packaging.md](docs/release-packaging.md).
Do not use GitHub-generated Source code.zip/Source code.tar.gz directly with
\`update.sh\`.

Reset data or return to the Setup Wizard:

\`\`\`bash
sudo ./factory-reset.sh --mode user_data --yes
sudo ./factory-reset.sh --mode configuration --yes
sudo ./factory-reset.sh --mode factory_reset --phrase "ERASE VISIONDESK"
\`\`\`

A \`configuration\` reset removes the API key and setup state, then returns to Welcome
so phone-first setup can run again. Use \`--remove-wifi\` with a factory reset if saved
Wi-Fi profiles must also be removed.

Uninstall while keeping data/configuration by default:

\`\`\`bash
sudo ./uninstall.sh
\`\`\`

Preview or fully remove:

\`\`\`bash
sudo ./uninstall.sh --dry-run
sudo ./uninstall.sh --purge
\`\`\`

See [docs/architecture.md](docs/architecture.md) for architecture details and
[docs/phone_setup.md](docs/phone_setup.md) for the portal’s security boundary.
