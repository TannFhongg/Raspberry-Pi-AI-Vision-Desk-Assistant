# VisionDesk demo checklist

This checklist covers the features present in VisionDesk 1.0.2. It does not
claim text-to-speech or any other feature absent from the application.

## Before the demo

- Use a Raspberry Pi 5 with the 11.6-inch non-touch HDMI display, USB webcam,
  Internet access, and the ten configured GPIO buttons. Keep a USB keyboard and
  mouse connected for recovery.
- Confirm the HDMI output is the panel's native 1366 x 768 at 100% desktop
  scaling and a non-stretching monitor aspect mode.
- Confirm the appliance is healthy:

  ```bash
  sudo systemctl status visiondesk.service
  nmcli device status
  ```

- For a live AI demonstration, verify Internet access and use an OpenAI API key
  with available quota. Enter the key through Setup on an appliance; do not show
  or paste it into a terminal, slide, screenshot, or log.
- Prepare a printed-text sample, a document with clear headings/actions, a
  photo or object scene, work material such as a table/whiteboard, and a short
  math or logic problem. These correspond to the five implemented modes.
- For a development-only UI demo, start the deterministic mock flow instead:

  ```bash
  python -m qt_app.main --windowed --mock-hardware
  ```

## Demo order

1. Show the non-touch Home screen and select a mode using GPIO Up, Down, and
   Select. The BCM button map is in [../setup-en.md](../setup-en.md).
2. Demonstrate camera preview, Capture, Review and Adjust, explicit Confirm and
   Analyze, the Processing screen, and Result. Point out that no AI request is
   made before confirmation.
3. Demonstrate each implemented workflow with the matching prepared sample:

   - Read Text
   - Summarize Document
   - Analyze Image
   - Professional Assistant
   - Solve Problem

4. Open History and History Detail to show that saved history is text-only.
5. Open Settings and Device Health to show the text-size preference and
   non-sensitive Technical Details without placing raw metrics in the header.
6. Explain that live results depend on the image, network, and OpenAI service;
   do not promise fixed content or response time.

## Optional first-boot demonstration

Use a factory-new device or one deliberately reset to incomplete setup. Do not
reset the only prepared demo device immediately before a client meeting.

1. On Welcome, show the temporary SSID, QR code, local URL, and pairing code.
2. Join the displayed WPA2-protected AP from a phone and complete the pairing
   flow.
3. Submit target Wi-Fi and the OpenAI key, then show the camera and GPIO steps.
4. On Finish Setup, verify that long gate messages wrap and scroll above the
   fixed footer, and that Ready is enabled only after every required gate passes.
5. Explain that the temporary AP is removed after submission and that the portal
   is not a persistent LAN management page.

See [phone_setup.md](phone_setup.md) for the exact workflow and fallback.

## Boundaries to state accurately

- The 11.6-inch display is not touch-enabled; GPIO is the normal input method.
- “Hear printed text” / TTS is not implemented in version 1.0.2.
- Desktop mock mode demonstrates UI states but does not prove camera, GPIO,
  display sharpness, or production readiness.
- History defaults to text and safe metadata. Private captured/retry media is
  kept under `/var/lib/visiondesk/private/` and is subject to retention limits.
- A candidate OpenAI key is verified before persistence and is not exposed to
  QML as raw or masked text.
- The product runs as `visiondesk.service`; phone provisioning is a short-lived
  local HTTP service on the temporary AP, not a browser kiosk or permanent web
  dashboard.

## After the demo

- Close any document or image containing client data.
- Review History and use the appropriate reset action only with authorization:
  User-Data Reset, Configuration Reset, or Full Factory Reset have different
  effects. Commands and consequences are in [../setup-en.md](../setup-en.md).
- Do not leave a temporary phone setup AP running or a keyboard attached in an
  unattended client environment.
