# Phone-first Provisioning

This procedure is for the 11.6-inch non-touch VisionDesk appliance. It lets an
installer enter Wi-Fi and the OpenAI API key from a phone, while the panel is
used only to display the temporary network, pairing code, QR code, and progress.

## Preconditions

- `setup.completed` is `false` in the active device configuration, or a
  Configuration/Factory Reset has returned the device to setup.
- `setup_portal.enabled` and `setup_portal.auto_start_when_setup_incomplete`
  are enabled. The shipped profile uses `wlan0`, `192.168.4.1`, port `80`, and
  a 15-minute session.
- The Wi-Fi adapter supports protected AP mode and is managed by NetworkManager.
- The appliance was installed with `install.sh`; it installs the VisionDesk
  NetworkManager PolicyKit rule. Confirm permissions with `nmcli general permissions`.

## Installer flow

1. Power on VisionDesk and wait for the Welcome screen.
2. On the phone, join the panel's `VisionDesk-Setup-XXXX` SSID using the
   displayed temporary password.
3. Scan the QR code or browse to the panel's local address.
4. Enter the panel's eight-digit pairing code.
5. Select the target Wi-Fi, enter its password, and enter the OpenAI API key.
6. Submit once. The phone is disconnected when the temporary AP is removed.
7. Watch the VisionDesk panel while it joins Wi-Fi, verifies the API key, and
   checks the camera. Finally, press each of the ten physical buttons once.
8. VisionDesk completes setup and restarts into Home.

The QR payload is only the local URL. The temporary Wi-Fi password and pairing
code are generated per portal launch. The API key stays in memory until its
verification passes, then is saved into the protected environment file; it is
never displayed by the QML UI or returned by the phone portal.

## Recovery

If the portal reports it cannot start:

1. Attach the recovery keyboard/mouse and use the on-panel Wi-Fi/OpenAI wizard.
2. Check `systemctl status NetworkManager` and `nmcli general permissions`.
3. Confirm the configured interface exists with `nmcli device status` and that
   the adapter advertises AP mode.
4. Check `journalctl -u visiondesk.service -b` for a non-secret failure summary.

Do not copy credentials into a shell command or a service log while diagnosing.
If the wireless adapter does not support AP mode, keep `setup_portal.enabled:
false`; standard keyboard/mouse provisioning continues to work.

## Security boundary

The setup server listens only on the configured AP IPv4 address. Its JSON
endpoints require a pairing code and an expiring `HttpOnly; SameSite=Strict`
session cookie. It has no general LAN bind, no persistent session, and deletes
its own `visiondesk-setup-*` NetworkManager profile when stopped. This is a
local WPA2-protected setup channel, not an internet-facing management service.
