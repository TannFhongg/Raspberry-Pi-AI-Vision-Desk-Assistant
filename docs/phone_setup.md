# Phone-first provisioning

This procedure applies to a new VisionDesk 1.0.0 appliance with the 11.6-inch
non-touch display. The device panel shows the temporary network and progress;
a phone supplies Wi-Fi credentials and the OpenAI API key.

## Preconditions

- VisionDesk was installed with `install.sh` and `visiondesk.service` is
  running.
- Setup is incomplete. A factory installation has `setup.completed: false`; an
  existing device can return to this state with Configuration Reset or Factory
  Reset.
- In `/etc/visiondesk/device.yaml`, `setup_portal.enabled` and
  `setup_portal.auto_start_when_setup_incomplete` are enabled. The shipped
  configuration uses `wlan0`, `192.168.4.1`, port `80`, the
  `VisionDesk-Setup` SSID prefix, and a 15-minute session lifetime.
- The Wi-Fi adapter is managed by NetworkManager and can create a protected AP.
  If it cannot, use the keyboard/mouse fallback below.

`install.sh` installs the PolicyKit rule required for the dedicated
`visiondesk` user to scan Wi-Fi, create the protected AP, control connections,
and modify system Wi-Fi profiles. Check the effective policy on the Pi with:

```bash
nmcli general permissions
```

## Provision a new device

1. Power on the device and wait for the Welcome screen.
2. Read the **Phone setup** card on the panel. It shows a temporary
   `VisionDesk-Setup-XXXX` SSID, a generated Wi-Fi password, a QR code/local
   URL, and an eight-digit pairing code.
3. Connect the phone to that temporary SSID, then scan the QR code or open the
   displayed local URL.
4. Enter the pairing code, select the target Wi-Fi network, and enter the
   target Wi-Fi password and OpenAI API key.
5. Submit once. VisionDesk stops and removes the temporary AP, then connects to
   the chosen Wi-Fi, verifies the OpenAI key, and runs the camera check.
6. Press each of the ten physical buttons during the GPIO step. The application
   completes setup and restarts into Home.

The QR payload contains only the local URL. It never contains the temporary
Wi-Fi password, the pairing code, Wi-Fi credentials, or the API key.

## If phone setup cannot start

1. Attach the recovery keyboard and mouse, then use the on-panel Setup wizard
   to enter Wi-Fi and the OpenAI key directly.
2. Inspect NetworkManager and the Wi-Fi interface:

   ```bash
   sudo systemctl status NetworkManager
   nmcli device status
   nmcli general permissions
   ```

3. Inspect the non-secret application failure summary:

   ```bash
   journalctl -u visiondesk.service -b
   ```

4. If the adapter cannot create a protected AP, set
   `setup_portal.enabled: false` in `/etc/visiondesk/device.yaml` and restart
   the service. Keyboard/mouse provisioning remains the supported fallback.

Do not paste Wi-Fi passwords or OpenAI keys into shell commands or logs while
diagnosing.

## Security boundary

The portal is a short-lived HTTP server bound only to its configured AP IPv4
address. It is reachable after joining the generated WPA2-protected AP, not as
a normal LAN management site. Pairing must complete before its JSON APIs are
available; failed pairing attempts are bounded, and the session expires. The
session cookie is `HttpOnly; SameSite=Strict`; it cannot authorize anything
once the portal session stops.

Wi-Fi and OpenAI credentials are not returned to QML, included in the QR code,
or intentionally logged. The temporary NetworkManager profile is removed when
the portal stops. Do not expose the portal address through another network or
replace the AP with an open network.

For the full installation and reset procedure, see [../setup.md](../setup.md).
