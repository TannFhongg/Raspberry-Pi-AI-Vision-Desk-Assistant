"""Unit tests for the Phase 14 OpenAI retry and image validation behavior."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from PIL import Image

from ai.openai_client import OpenAIVisionClient, VisionClientError
from config import SettingsError


class OpenAIVisionClientReliabilityTests(unittest.TestCase):
    """Verify explicit retries, timeouts, and invalid-image handling."""

    def test_retries_timeouts_three_total_attempts(self) -> None:
        image_path = _create_valid_image(".png")
        sleeps: list[float] = []
        instances: list[object] = []
        fake_module, fake_client_class = _build_fake_sdk(
            side_effects=[
                _FakeAPITimeoutError("timeout 1"),
                _FakeAPITimeoutError("timeout 2"),
                SimpleNamespace(output_text="Answer ready"),
            ],
            instances=instances,
        )

        with patch("ai.openai_client.load_device_settings", return_value=_build_settings()), patch(
            "ai.openai_client._import_openai_sdk",
            return_value=(fake_module, fake_client_class),
        ):
            client = OpenAIVisionClient(
                api_key="test-key",
                timeout_seconds=12.0,
                retry_attempts=3,
                retry_backoff_seconds=2.0,
                sleep_func=lambda seconds: sleeps.append(seconds),
            )
            answer = client.analyze_image(str(image_path), "document_reader")

        self.assertEqual(answer, "Answer ready")
        self.assertEqual(instances[0].init_kwargs["timeout"], 12.0)
        self.assertEqual(instances[0].init_kwargs["max_retries"], 0)
        self.assertEqual(len(instances[0].responses.calls), 3)
        self.assertEqual(sleeps, [2.0, 4.0])

    def test_retries_server_errors(self) -> None:
        image_path = _create_valid_image(".png")
        sleeps: list[float] = []
        instances: list[object] = []
        fake_module, fake_client_class = _build_fake_sdk(
            side_effects=[
                _FakeAPIStatusError(500),
                SimpleNamespace(output_text="Recovered"),
            ],
            instances=instances,
        )

        with patch("ai.openai_client.load_device_settings", return_value=_build_settings()), patch(
            "ai.openai_client._import_openai_sdk",
            return_value=(fake_module, fake_client_class),
        ):
            client = OpenAIVisionClient(
                api_key="test-key",
                retry_attempts=3,
                retry_backoff_seconds=2.0,
                sleep_func=lambda seconds: sleeps.append(seconds),
            )
            answer = client.analyze_image(str(image_path), "document_reader")

        self.assertEqual(answer, "Recovered")
        self.assertEqual(len(instances[0].responses.calls), 2)
        self.assertEqual(sleeps, [2.0])

    def test_does_not_retry_bad_request_errors(self) -> None:
        image_path = _create_valid_image(".png")
        sleeps: list[float] = []
        instances: list[object] = []
        fake_module, fake_client_class = _build_fake_sdk(
            side_effects=[_FakeBadRequestError("bad request")],
            instances=instances,
        )

        with patch("ai.openai_client.load_device_settings", return_value=_build_settings()), patch(
            "ai.openai_client._import_openai_sdk",
            return_value=(fake_module, fake_client_class),
        ):
            client = OpenAIVisionClient(
                api_key="test-key",
                retry_attempts=3,
                retry_backoff_seconds=2.0,
                sleep_func=lambda seconds: sleeps.append(seconds),
            )
            with self.assertRaises(VisionClientError):
                client.analyze_image(str(image_path), "document_reader")

        self.assertEqual(len(instances[0].responses.calls), 1)
        self.assertEqual(sleeps, [])

    def test_invalid_image_fails_before_request(self) -> None:
        temp_dir = Path(tempfile.mkdtemp(prefix="vision-invalid-image-"))
        image_path = temp_dir / "broken.jpg"
        image_path.write_bytes(b"not-a-real-image")
        instances: list[object] = []
        fake_module, fake_client_class = _build_fake_sdk(
            side_effects=[SimpleNamespace(output_text="unused")],
            instances=instances,
        )

        with patch("ai.openai_client.load_device_settings", return_value=_build_settings()), patch(
            "ai.openai_client._import_openai_sdk",
            return_value=(fake_module, fake_client_class),
        ):
            client = OpenAIVisionClient(api_key="test-key")
            with self.assertRaises(VisionClientError) as error:
                client.analyze_image(str(image_path), "document_reader")

        self.assertIn("Invalid image file", str(error.exception))
        self.assertEqual(len(instances[0].responses.calls), 0)

    def test_falls_back_to_builtin_reliability_defaults_when_settings_are_unavailable(self) -> None:
        image_path = _create_valid_image(".png")
        instances: list[object] = []
        fake_module, fake_client_class = _build_fake_sdk(
            side_effects=[SimpleNamespace(output_text="Fallback defaults worked")],
            instances=instances,
        )

        with patch(
            "ai.openai_client.load_device_settings",
            side_effect=SettingsError("Device config file not found"),
        ), patch(
            "ai.openai_client._import_openai_sdk",
            return_value=(fake_module, fake_client_class),
        ):
            client = OpenAIVisionClient(api_key="test-key")
            answer = client.analyze_image(str(image_path), "document_reader")

        self.assertEqual(answer, "Fallback defaults worked")
        self.assertEqual(instances[0].init_kwargs["timeout"], 30.0)
        self.assertEqual(len(instances[0].responses.calls), 1)


def _build_settings() -> SimpleNamespace:
    """Return only the reliability values needed by the OpenAI client."""
    return SimpleNamespace(
        reliability=SimpleNamespace(
            openai_timeout_seconds=30.0,
            openai_retry_attempts=3,
            openai_retry_backoff_seconds=2.0,
        )
    )


def _create_valid_image(suffix: str) -> Path:
    """Create a small valid image file on disk for request tests."""
    temp_dir = Path(tempfile.mkdtemp(prefix="vision-openai-image-"))
    image_path = temp_dir / f"sample{suffix}"
    with Image.new("RGB", (4, 4), color=(255, 255, 255)) as image:
        image.save(image_path)
    return image_path


def _build_fake_sdk(side_effects: list[object], instances: list[object]):
    """Create a fake OpenAI SDK module and client class for the tests."""

    class FakeOpenAIModule:
        OpenAIError = _FakeOpenAIError
        AuthenticationError = _FakeAuthenticationError
        PermissionDeniedError = _FakePermissionDeniedError
        NotFoundError = _FakeNotFoundError
        RateLimitError = _FakeRateLimitError
        APIConnectionError = _FakeAPIConnectionError
        APITimeoutError = _FakeAPITimeoutError
        BadRequestError = _FakeBadRequestError
        APIStatusError = _FakeAPIStatusError

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            self.init_kwargs = kwargs
            self.responses = _FakeResponses(side_effects)
            instances.append(self)

    return FakeOpenAIModule, FakeClient


class _FakeResponses:
    """Tiny fake for `client.responses.create(...)`."""

    def __init__(self, side_effects: list[object]) -> None:
        self.side_effects = list(side_effects)
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        effect = self.side_effects.pop(0)
        if isinstance(effect, Exception):
            raise effect
        return effect


class _FakeOpenAIError(Exception):
    """Base fake SDK error used by the retry tests."""


class _FakeAuthenticationError(_FakeOpenAIError):
    """Authentication failure."""


class _FakePermissionDeniedError(_FakeOpenAIError):
    """Permission failure."""


class _FakeNotFoundError(_FakeOpenAIError):
    """Missing model failure."""


class _FakeRateLimitError(_FakeOpenAIError):
    """Rate limit failure."""


class _FakeAPIConnectionError(_FakeOpenAIError):
    """Connection failure."""


class _FakeAPITimeoutError(_FakeOpenAIError):
    """Timeout failure."""


class _FakeBadRequestError(_FakeOpenAIError):
    """Bad request failure."""


class _FakeAPIStatusError(_FakeOpenAIError):
    """HTTP status failure with a numeric code."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"status {status_code}")
        self.status_code = status_code
