"""Short-lived, local-only phone provisioning portal for first boot."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import html
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
import secrets
import string
import threading
import time
from typing import Any, Callable
from urllib.parse import urlparse

from config.settings import SetupPortalSettings
from system.device_setup import (
    ProvisioningAccessPoint,
    create_provisioning_access_point,
    remove_provisioning_access_point,
)

LOGGER = logging.getLogger(__name__)
_MAX_BODY_BYTES = 16_384
_MAX_PAIR_ATTEMPTS = 5
_COOKIE_NAME = "visiondesk_setup_session"
_DISPLAY_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

NetworkScanner = Callable[[], list[dict[str, Any]]]
ProvisionSubmitter = Callable[[str, str, str], bool]
StatusProvider = Callable[[], dict[str, Any]]
AccessPointStarter = Callable[..., ProvisioningAccessPoint]
AccessPointStopper = Callable[..., None]
Clock = Callable[[], float]


class SetupPortalError(Exception):
    """Raised when the temporary provisioning portal cannot be started safely."""


@dataclass(frozen=True, slots=True)
class SetupPortalDetails:
    """Display-safe first-boot pairing information for the local panel."""

    ssid: str
    password: str
    pairing_code: str
    address: str
    port: int
    url: str
    qr_data_url: str = ""


class SetupPortalSession:
    """Single-use pairing session with bounded attempts and monotonic expiry."""

    def __init__(
        self,
        *,
        timeout_seconds: float,
        clock: Clock = time.monotonic,
        pairing_code: str | None = None,
        token: str | None = None,
    ) -> None:
        self._clock = clock
        self._expires_at = clock() + max(1.0, timeout_seconds)
        self._pairing_code = pairing_code or _random_digits(8)
        self._token = token or secrets.token_urlsafe(32)
        self._failed_attempts = 0

    @property
    def pairing_code(self) -> str:
        return self._pairing_code

    @property
    def remaining_seconds(self) -> int:
        return max(0, int(self._expires_at - self._clock()))

    def pair(self, pairing_code: str) -> str | None:
        """Return a session cookie token when the displayed code is accepted."""
        if self.expired or self._failed_attempts >= _MAX_PAIR_ATTEMPTS:
            return None
        if not secrets.compare_digest(str(pairing_code or "").strip(), self._pairing_code):
            self._failed_attempts += 1
            return None
        return self._token

    def authenticated(self, token: str | None) -> bool:
        """Return whether a request carries the active opaque session token."""
        return (
            not self.expired
            and isinstance(token, str)
            and secrets.compare_digest(token, self._token)
        )

    @property
    def expired(self) -> bool:
        return self._clock() >= self._expires_at


class SetupPortal:
    """Own a local HTTP server and its matching temporary Wi-Fi access point."""

    def __init__(
        self,
        *,
        settings: SetupPortalSettings,
        scan_networks: NetworkScanner,
        submit_provisioning: ProvisionSubmitter,
        status_provider: StatusProvider,
        start_access_point: AccessPointStarter = create_provisioning_access_point,
        stop_access_point: AccessPointStopper = remove_provisioning_access_point,
        clock: Clock = time.monotonic,
    ) -> None:
        self.settings = settings
        self._scan_networks = scan_networks
        self._submit_provisioning = submit_provisioning
        self._status_provider = status_provider
        self._start_access_point = start_access_point
        self._stop_access_point = stop_access_point
        self._clock = clock
        self._session: SetupPortalSession | None = None
        self._details: SetupPortalDetails | None = None
        self._access_point: ProvisioningAccessPoint | None = None
        self._networks: list[dict[str, Any]] = []
        self._server: ThreadingHTTPServer | None = None
        self._server_thread: threading.Thread | None = None
        self._lock = threading.RLock()

    @property
    def active(self) -> bool:
        with self._lock:
            return self._server is not None and self._details is not None

    @property
    def details(self) -> SetupPortalDetails | None:
        with self._lock:
            return self._details

    def start(self) -> SetupPortalDetails:
        """Create the AP, bind the portal only to its address, and start serving."""
        with self._lock:
            if self.active and self._details is not None:
                return self._details
            if not self.settings.enabled:
                raise SetupPortalError("Phone provisioning is disabled in device configuration.")

            session = SetupPortalSession(
                timeout_seconds=self.settings.session_timeout_minutes * 60,
                clock=self._clock,
            )
            # A single Wi-Fi radio cannot reliably scan while it is hosting an
            # AP. Capture the nearby-network list before NetworkManager changes
            # wlan0 into access-point mode, then serve that safe snapshot.
            self._networks = self._scan_and_sanitize_networks()
            suffix = _random_display_text(4)
            ssid = f"{self.settings.ssid_prefix}-{suffix}"
            password = _random_display_text(14)
            connection_name = f"visiondesk-setup-{secrets.token_hex(4)}"
            try:
                access_point = self._start_access_point(
                    ssid=ssid,
                    password=password,
                    interface=self.settings.interface,
                    address=self.settings.address,
                    connection_name=connection_name,
                )
                server = self._build_server(access_point.address, self.settings.port)
            except Exception as exc:
                if "access_point" in locals():
                    try:
                        self._stop_access_point(connection_name=access_point.connection_name)
                    except Exception:
                        LOGGER.warning("Could not remove failed temporary setup network")
                raise SetupPortalError("Could not start the local phone setup portal.") from exc

            bound_port = int(server.server_address[1])
            url = _portal_url(access_point.address, bound_port)
            self._session = session
            self._access_point = access_point
            self._server = server
            self._details = SetupPortalDetails(
                ssid=access_point.ssid,
                password=password,
                pairing_code=session.pairing_code,
                address=access_point.address,
                port=bound_port,
                url=url,
                qr_data_url=_build_qr_data_url(url),
            )
            self._server_thread = threading.Thread(
                target=server.serve_forever,
                daemon=True,
                name="visiondesk-setup-portal",
            )
            self._server_thread.start()
            return self._details

    def stop(self) -> None:
        """Stop serving and remove the matching temporary NetworkManager profile."""
        with self._lock:
            server = self._server
            thread = self._server_thread
            access_point = self._access_point
            self._server = None
            self._server_thread = None
            self._access_point = None
            self._session = None
            self._details = None
            self._networks = []

        if server is not None:
            try:
                server.shutdown()
            finally:
                server.server_close()
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        if access_point is not None:
            try:
                self._stop_access_point(connection_name=access_point.connection_name)
            except Exception:
                LOGGER.warning("Could not remove temporary phone setup network")

    def _build_server(self, address: str, port: int) -> ThreadingHTTPServer:
        portal = self

        class PortalRequestHandler(_SetupPortalRequestHandler):
            owner = portal

        class PortalHttpServer(ThreadingHTTPServer):
            allow_reuse_address = True
            daemon_threads = True

        try:
            return PortalHttpServer((address, port), PortalRequestHandler)
        except OSError as exc:
            raise SetupPortalError("The local phone setup portal could not bind to its access-point address.") from exc

    def _pair(self, pairing_code: str) -> str | None:
        with self._lock:
            session = self._session
            return session.pair(pairing_code) if session is not None else None

    def _authenticated(self, token: str | None) -> bool:
        with self._lock:
            session = self._session
            return session.authenticated(token) if session is not None else False

    def _session_remaining_seconds(self) -> int:
        with self._lock:
            return self._session.remaining_seconds if self._session is not None else 0

    def _safe_status(self) -> dict[str, Any]:
        try:
            status = self._status_provider()
        except Exception:
            status = {"stage": "unavailable", "message": "Setup status is temporarily unavailable."}
        safe_status = status if isinstance(status, dict) else {}
        return {
            "stage": str(safe_status.get("stage", "waiting_for_phone")),
            "message": str(safe_status.get("message", "Waiting for phone setup.")),
            "wifi_status": str(safe_status.get("wifi_status", "idle")),
            "openai_status": str(safe_status.get("openai_status", "idle")),
            "camera_status": str(safe_status.get("camera_status", "idle")),
            "gpio_status": str(safe_status.get("gpio_status", "idle")),
            "remaining_seconds": self._session_remaining_seconds(),
        }

    def _safe_networks(self) -> list[dict[str, Any]]:
        """Return the pre-AP, display-safe nearby network snapshot."""
        with self._lock:
            return [dict(item) for item in self._networks]

    def _scan_and_sanitize_networks(self) -> list[dict[str, Any]]:
        try:
            networks = self._scan_networks()
        except Exception:
            return []
        safe_networks: list[dict[str, Any]] = []
        for item in networks[:64]:
            if not isinstance(item, dict):
                continue
            ssid = str(item.get("ssid", "")).strip()
            if not ssid or len(ssid) > 32:
                continue
            try:
                signal = max(0, min(100, int(item.get("signal", 0))))
            except (TypeError, ValueError):
                signal = 0
            safe_networks.append(
                {
                    "ssid": ssid,
                    "signal": signal,
                    "security": str(item.get("security", "open"))[:32] or "open",
                }
            )
        return safe_networks

    def _submit(self, payload: dict[str, Any]) -> bool:
        ssid = str(payload.get("ssid", "")).strip()
        password = str(payload.get("password", ""))
        api_key = str(payload.get("api_key", "")).strip()
        if not ssid or len(ssid) > 32 or len(password) > 128 or len(api_key) > 512:
            return False
        try:
            return bool(self._submit_provisioning(ssid, password, api_key))
        except Exception:
            return False

    def _page_html(self) -> str:
        details = self.details
        if details is None:
            return ""
        address = html.escape(details.address)
        return f"""<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>VisionDesk Setup</title><style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:32px auto;padding:0 18px;background:#f6f8fc;color:#17233a}}main{{background:#fff;padding:24px;border-radius:16px;box-shadow:0 5px 20px #17233a18}}label{{display:block;margin-top:14px;font-weight:650}}input,select,button{{box-sizing:border-box;width:100%;padding:12px;margin-top:6px;border:1px solid #b9c4d8;border-radius:9px;font:inherit}}button{{background:#155eef;color:white;border:0;font-weight:700;cursor:pointer}}.hidden{{display:none}}#status{{white-space:pre-wrap;margin-top:18px;padding:12px;background:#edf3ff;border-radius:9px}}small{{color:#52627c}}</style></head>
<body><main><h1>VisionDesk setup</h1><p>Connected to the temporary device network. Enter the pairing code shown on VisionDesk.</p>
<section id=\"pair\"><label>Pairing code<input id=\"code\" inputmode=\"numeric\" autocomplete=\"one-time-code\" maxlength=\"8\"></label><button onclick=\"pair()\">Continue</button></section>
<section id=\"form\" class=\"hidden\"><label>Wi-Fi network<select id=\"ssid\"><option value=\"\">Loading networks…</option></select></label><label>Wi-Fi password<input id=\"password\" type=\"password\" autocomplete=\"new-password\"></label><label>OpenAI API key<input id=\"api_key\" type=\"password\" autocomplete=\"off\"></label><button onclick=\"provision()\">Apply setup</button><small>Your phone will disconnect when VisionDesk joins the selected Wi-Fi network.</small></section>
<p id=\"status\">Open {address} in this browser.</p></main><script>
async function call(path,body){{let r=await fetch(path,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}});return [r,await r.json()];}}
async function pair(){{let [r,d]=await call('/api/pair',{{code:document.getElementById('code').value}});if(!r.ok){{status('Pairing was not accepted.');return;}}document.getElementById('pair').classList.add('hidden');document.getElementById('form').classList.remove('hidden');loadNetworks();status('Choose your Wi-Fi network and enter the API key.');}}
async function loadNetworks(){{let r=await fetch('/api/networks');let d=await r.json();let s=document.getElementById('ssid');s.innerHTML='';(d.networks||[]).forEach(n=>{{let o=document.createElement('option');o.value=n.ssid;o.textContent=n.ssid+' ('+n.signal+'%)';s.appendChild(o);}});if(!s.options.length){{let o=document.createElement('option');o.value='';o.textContent='No networks found';s.appendChild(o);}}}}
async function provision(){{let [r,d]=await call('/api/provision',{{ssid:document.getElementById('ssid').value,password:document.getElementById('password').value,api_key:document.getElementById('api_key').value}});status(r.ok?'Applying setup. Watch the VisionDesk display while this phone disconnects.':'Setup request was not accepted.');}}
function status(t){{document.getElementById('status').textContent=t;}}</script></body></html>"""


class _SetupPortalRequestHandler(BaseHTTPRequestHandler):
    """HTTP surface with strict routing, no logging, and opaque cookie auth."""

    owner: SetupPortal
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: Any) -> None:
        """Avoid writing request paths or request metadata to application logs."""

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not self._allowed_host():
            self._json_error(HTTPStatus.BAD_REQUEST, "Invalid host.")
            return
        if path == "/":
            self._html(self.owner._page_html())
            return
        if path == "/api/status":
            if not self._require_auth():
                return
            self._json(HTTPStatus.OK, self.owner._safe_status())
            return
        if path == "/api/networks":
            if not self._require_auth():
                return
            self._json(HTTPStatus.OK, {"networks": self.owner._safe_networks()})
            return
        self._json_error(HTTPStatus.NOT_FOUND, "Not found.")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not self._allowed_host():
            self._json_error(HTTPStatus.BAD_REQUEST, "Invalid host.")
            return
        payload = self._read_json_body()
        if payload is None:
            return
        if path == "/api/pair":
            token = self.owner._pair(str(payload.get("code", "")))
            if token is None:
                self._json_error(HTTPStatus.FORBIDDEN, "Pairing was not accepted.")
                return
            self._json(HTTPStatus.OK, {"paired": True}, session_token=token)
            return
        if path == "/api/provision":
            if not self._require_auth():
                return
            if not self.owner._submit(payload):
                self._json_error(HTTPStatus.BAD_REQUEST, "Setup request was not accepted.")
                return
            self._json(HTTPStatus.ACCEPTED, {"accepted": True})
            return
        self._json_error(HTTPStatus.NOT_FOUND, "Not found.")

    def _allowed_host(self) -> bool:
        details = self.owner.details
        if details is None:
            return False
        host = self.headers.get("Host", "").strip().lower()
        return host in {details.address.lower(), f"{details.address.lower()}:{details.port}"}

    def _require_auth(self) -> bool:
        token = _cookie_value(self.headers.get("Cookie", ""), _COOKIE_NAME)
        if self.owner._authenticated(token):
            return True
        self._json_error(HTTPStatus.UNAUTHORIZED, "Pair with the displayed code first.")
        return False

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > _MAX_BODY_BYTES:
            self._json_error(HTTPStatus.BAD_REQUEST, "Invalid request.")
            return None
        if "application/json" not in self.headers.get("Content-Type", "").lower():
            self._json_error(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "Use JSON requests.")
            return None
        try:
            decoded = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json_error(HTTPStatus.BAD_REQUEST, "Invalid request.")
            return None
        if not isinstance(decoded, dict):
            self._json_error(HTTPStatus.BAD_REQUEST, "Invalid request.")
            return None
        return decoded

    def _common_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; base-uri 'none'; frame-ancestors 'none'",
        )

    def _json(self, status: HTTPStatus, payload: dict[str, Any], *, session_token: str | None = None) -> None:
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._common_headers("application/json; charset=utf-8")
        if session_token is not None:
            max_age = self.owner._session_remaining_seconds()
            self.send_header(
                "Set-Cookie",
                f"{_COOKIE_NAME}={session_token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}",
            )
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _json_error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})

    def _html(self, page: str) -> None:
        encoded = page.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self._common_headers("text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _cookie_value(header: str, key: str) -> str | None:
    for item in header.split(";"):
        name, separator, value = item.strip().partition("=")
        if separator and name == key:
            return value
    return None


def _random_digits(length: int) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def _random_display_text(length: int) -> str:
    return "".join(secrets.choice(_DISPLAY_ALPHABET) for _ in range(length))


def _portal_url(address: str, port: int) -> str:
    return f"http://{address}" if port == 80 else f"http://{address}:{port}"


def _build_qr_data_url(value: str) -> str:
    """Return a QR PNG data URL when the optional deployment dependency is installed."""
    try:
        import qrcode
    except ImportError:
        return ""
    try:
        image = qrcode.make(value)
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")
    except Exception:
        return ""
