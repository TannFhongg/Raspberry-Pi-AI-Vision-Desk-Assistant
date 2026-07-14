"""Tests for the short-lived local phone-provisioning portal."""

from __future__ import annotations

import http.client
import json
import logging
from types import SimpleNamespace

import pytest

from config.settings import SetupPortalSettings
from system.device_setup import DeviceSetupError, ProvisioningAccessPoint, create_provisioning_access_point
from system.setup_portal import SetupPortal, SetupPortalSession


def test_portal_session_expires_and_locks_after_bounded_failed_pairings() -> None:
    now = [100.0]
    session = SetupPortalSession(
        timeout_seconds=20,
        clock=lambda: now[0],
        pairing_code="12345678",
        token="opaque-session-token",
    )

    assert session.authenticated("opaque-session-token") is True
    for _ in range(5):
        assert session.pair("00000000") is None
    assert session.pair("12345678") is None

    unexpired = SetupPortalSession(
        timeout_seconds=2,
        clock=lambda: now[0],
        pairing_code="12345678",
        token="opaque-session-token",
    )
    assert unexpired.pair("12345678") == "opaque-session-token"
    now[0] += 2
    assert unexpired.authenticated("opaque-session-token") is False


def test_phone_portal_requires_pairing_and_keeps_credentials_out_of_logs(caplog) -> None:
    lifecycle: list[str] = []
    submitted: list[tuple[str, str, str]] = []
    stopped: list[str] = []
    wifi_password = "wifi-secret-123"
    api_key = "sk-phone-secret-456"

    def start_access_point(**kwargs):
        lifecycle.append("ap")
        return ProvisioningAccessPoint(
            ssid=kwargs["ssid"],
            address="127.0.0.1",
            connection_name=kwargs["connection_name"],
        )

    portal = SetupPortal(
        settings=SetupPortalSettings(
            enabled=True,
            interface="test0",
            address="127.0.0.1",
            port=0,
            ssid_prefix="VisionDesk-Setup",
        ),
        scan_networks=lambda: [
            {"ssid": "Office", "signal": 82, "security": "WPA2"},
            {"ssid": "", "signal": 10, "security": "open"},
        ],
        submit_provisioning=lambda ssid, password, key: submitted.append((ssid, password, key)) is None,
        status_provider=lambda: {"stage": "active", "message": "Waiting for phone."},
        start_access_point=start_access_point,
        stop_access_point=lambda *, connection_name: stopped.append(connection_name),
    )
    caplog.set_level(logging.DEBUG)
    details = portal.start()

    def request(method: str, path: str, payload: dict[str, str] | None = None, *, cookie: str = ""):
        connection = http.client.HTTPConnection("127.0.0.1", details.port, timeout=2)
        headers = {"Host": f"127.0.0.1:{details.port}"}
        body = None
        if payload is not None:
            body = json.dumps(payload)
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        response_body = response.read()
        connection.close()
        return response, response_body

    try:
        response, page = request("GET", "/")
        assert response.status == 200
        assert response.getheader("Cache-Control") == "no-store, max-age=0"
        assert b"VisionDesk setup" in page

        response, _ = request("GET", "/api/networks")
        assert response.status == 401

        response, _ = request("POST", "/api/pair", {"code": "00000000"})
        assert response.status == 403

        response, _ = request("POST", "/api/pair", {"code": details.pairing_code})
        assert response.status == 200
        cookie = response.getheader("Set-Cookie")
        assert cookie is not None and "HttpOnly" in cookie and "SameSite=Strict" in cookie

        response, body = request("GET", "/api/networks", cookie=cookie)
        assert response.status == 200
        assert json.loads(body) == {"networks": [{"ssid": "Office", "signal": 82, "security": "WPA2"}]}

        response, _ = request(
            "POST",
            "/api/provision",
            {"ssid": "Office", "password": wifi_password, "api_key": api_key},
            cookie=cookie,
        )
        assert response.status == 202
        assert submitted == [("Office", wifi_password, api_key)]
        assert wifi_password not in caplog.text
        assert api_key not in caplog.text
    finally:
        portal.stop()

    assert lifecycle == ["ap"]
    assert len(stopped) == 1


def test_access_point_failure_redacts_password_and_removes_only_owned_profile() -> None:
    commands: list[list[str]] = []
    password = "temporary-secret-123"

    def runner(command, **_kwargs):
        commands.append(command)
        if "modify" in command:
            return SimpleNamespace(returncode=1, stdout="", stderr=f"psk={password} rejected")
        return SimpleNamespace(returncode=0, stdout="ok", stderr="")

    with pytest.raises(DeviceSetupError) as error:
        create_provisioning_access_point(
            ssid="VisionDesk-Setup-ABCD",
            password=password,
            interface="wlan0",
            address="192.168.4.1",
            connection_name="visiondesk-setup-1234abcd",
            runner=runner,
        )

    assert password not in str(error.value)
    assert commands[-1] == ["nmcli", "connection", "delete", "id", "visiondesk-setup-1234abcd"]
