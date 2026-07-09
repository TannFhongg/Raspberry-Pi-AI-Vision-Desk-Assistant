"""Reusable OpenAI vision client for the Phase 1 terminal MVP."""

from __future__ import annotations

import base64
import logging
import os
import time
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from ai.context import build_mode_context
from ai.modes import get_mode, normalize_mode
from config import SettingsError, load_device_settings

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 30.0
DEFAULT_OPENAI_RETRY_ATTEMPTS = 3
DEFAULT_OPENAI_RETRY_BACKOFF_SECONDS = 2.0
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
SUPPORTED_IMAGE_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
LOGGER = logging.getLogger(__name__)


class VisionClientError(Exception):
    """Friendly application-level error for image analysis failures."""


class OpenAIVisionClient:
    """Small wrapper around the OpenAI Responses API for image analysis."""

    def __init__(
        self,
        api_key: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float | None = None,
        retry_attempts: int | None = None,
        retry_backoff_seconds: float | None = None,
        sleep_func=None,
    ) -> None:
        try:
            reliability = load_device_settings().reliability
        except SettingsError as exc:
            LOGGER.warning(
                "Falling back to built-in OpenAI client reliability defaults because device settings could not be loaded: %s",
                exc,
            )
            reliability = None
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise VisionClientError(
                "Missing OpenAI API key. Set OPENAI_API_KEY in your .env file before running the test."
            )

        self.default_model = default_model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self.timeout_seconds = (
            DEFAULT_OPENAI_TIMEOUT_SECONDS
            if reliability is None
            else reliability.openai_timeout_seconds
        )
        if timeout_seconds is not None:
            self.timeout_seconds = float(timeout_seconds)
        self.retry_attempts = (
            DEFAULT_OPENAI_RETRY_ATTEMPTS
            if reliability is None
            else reliability.openai_retry_attempts
        )
        if retry_attempts is not None:
            self.retry_attempts = max(1, int(retry_attempts))
        self.retry_backoff_seconds = (
            DEFAULT_OPENAI_RETRY_BACKOFF_SECONDS
            if reliability is None
            else reliability.openai_retry_backoff_seconds
        )
        if retry_backoff_seconds is not None:
            self.retry_backoff_seconds = max(0.0, float(retry_backoff_seconds))
        self._sleep = time.sleep if sleep_func is None else sleep_func
        self._openai, openai_client_class = _import_openai_sdk()
        self.client = openai_client_class(
            api_key=self.api_key,
            timeout=self.timeout_seconds,
            max_retries=0,
        )

    def analyze_image(
        self,
        image_path: str,
        mode: str,
        extra_instruction: str | None = None,
        model: str | None = None,
    ) -> str:
        """Validate an image, send it to OpenAI, and return the model's answer."""
        image_file = self._validate_image_file(image_path)

        try:
            canonical_mode = normalize_mode(mode)
            instructions = build_mode_context(canonical_mode, extra_instruction)
        except ValueError as exc:
            raise VisionClientError(str(exc)) from exc

        mime_type = self._get_mime_type(image_file)
        data_url = self._build_data_url(image_file, mime_type)
        selected_model = model or self.default_model
        selected_mode = get_mode(canonical_mode)
        LOGGER.info(
            "OpenAI request started mode=%s model=%s image=%s",
            canonical_mode,
            selected_model,
            image_file,
        )

        for attempt in range(1, self.retry_attempts + 1):
            LOGGER.info(
                "OpenAI request attempt=%s/%s mode=%s model=%s",
                attempt,
                self.retry_attempts,
                canonical_mode,
                selected_model,
            )
            try:
                response = self.client.responses.create(
                    model=selected_model,
                    instructions=instructions,
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": f"Analyze this image using the {selected_mode.name} mode.",
                                },
                                {"type": "input_image", "image_url": data_url},
                            ],
                        }
                    ],
                    text={"verbosity": "low"},
                )
                break
            except self._openai.AuthenticationError as exc:
                LOGGER.error(
                    "OpenAI authentication failed mode=%s model=%s",
                    canonical_mode,
                    selected_model,
                    exc_info=True,
                )
                raise VisionClientError(
                    "Authentication failed. Check that OPENAI_API_KEY is correct and active."
                ) from exc
            except self._openai.PermissionDeniedError as exc:
                LOGGER.error(
                    "OpenAI permission denied mode=%s model=%s",
                    canonical_mode,
                    selected_model,
                    exc_info=True,
                )
                raise VisionClientError(
                    f"Permission denied for model '{selected_model}'. Verify your API project has access to this model."
                ) from exc
            except self._openai.NotFoundError as exc:
                LOGGER.error(
                    "OpenAI model not found mode=%s model=%s",
                    canonical_mode,
                    selected_model,
                    exc_info=True,
                )
                raise VisionClientError(
                    f"Model '{selected_model}' was not found. Check the model name in your .env file or --model argument."
                ) from exc
            except self._openai.RateLimitError as exc:
                if self._should_retry(attempt):
                    self._log_retry("rate limit", canonical_mode, selected_model, attempt, exc)
                    continue
                LOGGER.error(
                    "OpenAI rate limit exhausted mode=%s model=%s attempts=%s",
                    canonical_mode,
                    selected_model,
                    self.retry_attempts,
                    exc_info=True,
                )
                raise VisionClientError(
                    "OpenAI rate limit or quota reached after "
                    f"{self.retry_attempts} attempts. Wait a moment, then try again, or check your billing and usage limits."
                ) from exc
            except self._openai.APIConnectionError as exc:
                if self._should_retry(attempt):
                    self._log_retry("connection failure", canonical_mode, selected_model, attempt, exc)
                    continue
                LOGGER.error(
                    "OpenAI connection failed mode=%s model=%s attempts=%s",
                    canonical_mode,
                    selected_model,
                    self.retry_attempts,
                    exc_info=True,
                )
                raise VisionClientError(
                    f"Could not connect to OpenAI after {self.retry_attempts} attempts. "
                    "Check your internet connection and try again."
                ) from exc
            except self._openai.APITimeoutError as exc:
                if self._should_retry(attempt):
                    self._log_retry("timeout", canonical_mode, selected_model, attempt, exc)
                    continue
                LOGGER.error(
                    "OpenAI request timed out mode=%s model=%s attempts=%s",
                    canonical_mode,
                    selected_model,
                    self.retry_attempts,
                    exc_info=True,
                )
                raise VisionClientError(
                    f"The OpenAI request timed out after {self.retry_attempts} attempts. Please try again."
                ) from exc
            except self._openai.BadRequestError as exc:
                LOGGER.error(
                    "OpenAI rejected request mode=%s model=%s",
                    canonical_mode,
                    selected_model,
                    exc_info=True,
                )
                raise VisionClientError(
                    "OpenAI rejected the request. Check that the image is valid and the request settings are correct."
                ) from exc
            except self._openai.APIStatusError as exc:
                if getattr(exc, "status_code", None) is not None and exc.status_code >= 500:
                    if self._should_retry(attempt):
                        self._log_retry(
                            f"server status {exc.status_code}",
                            canonical_mode,
                            selected_model,
                            attempt,
                            exc,
                        )
                        continue
                    LOGGER.error(
                        "OpenAI server error mode=%s model=%s status=%s attempts=%s",
                        canonical_mode,
                        selected_model,
                        exc.status_code,
                        self.retry_attempts,
                        exc_info=True,
                    )
                    raise VisionClientError(
                        f"OpenAI API error (status {exc.status_code}) after {self.retry_attempts} attempts. "
                        "Please try again in a moment."
                    ) from exc

                LOGGER.error(
                    "OpenAI API status failure mode=%s model=%s status=%s",
                    canonical_mode,
                    selected_model,
                    getattr(exc, "status_code", "unknown"),
                    exc_info=True,
                )
                raise VisionClientError(
                    f"OpenAI API error (status {exc.status_code}). Please try again in a moment."
                ) from exc
            except self._openai.OpenAIError as exc:
                LOGGER.error(
                    "OpenAI SDK error mode=%s model=%s",
                    canonical_mode,
                    selected_model,
                    exc_info=True,
                )
                raise VisionClientError(f"OpenAI SDK error: {exc}") from exc

        answer = (response.output_text or "").strip()
        if not answer:
            LOGGER.error(
                "OpenAI returned empty response mode=%s model=%s",
                canonical_mode,
                selected_model,
            )
            raise VisionClientError("The model returned an empty response. Try a different image or mode.")

        LOGGER.info(
            "OpenAI request succeeded mode=%s model=%s attempts=%s",
            canonical_mode,
            selected_model,
            attempt,
        )
        return answer

    def _validate_image_file(self, image_path: str) -> Path:
        """Check that the file exists, has a supported extension, and is small enough."""
        image_file = Path(image_path)
        if not image_file.exists():
            raise VisionClientError(f"No image found at '{image_path}'. Check the file path and try again.")
        if not image_file.is_file():
            raise VisionClientError(f"'{image_path}' is not a file. Please provide a valid image file path.")

        self._get_mime_type(image_file)

        image_size = image_file.stat().st_size
        if image_size > MAX_IMAGE_SIZE_BYTES:
            raise VisionClientError(
                f"Image file is too large. Maximum allowed size for Phase 1 is {MAX_IMAGE_SIZE_MB} MB. "
                "Please resize or compress the image before running this test."
            )

        self._verify_image_contents(image_file)
        return image_file

    def _get_mime_type(self, image_file: Path) -> str:
        """Map a supported file extension to the MIME type expected by the API."""
        extension = image_file.suffix.lower()
        mime_type = SUPPORTED_IMAGE_TYPES.get(extension)
        if not mime_type:
            supported_extensions = ", ".join(SUPPORTED_IMAGE_TYPES.keys())
            raise VisionClientError(
                f"Unsupported image extension '{extension or '[none]'}'. Supported extensions: {supported_extensions}"
            )
        return mime_type

    def _build_data_url(self, image_file: Path, mime_type: str) -> str:
        """Read the image and convert it into a base64 data URL."""
        try:
            image_bytes = image_file.read_bytes()
        except OSError as exc:
            raise VisionClientError(f"Could not read image file '{image_file}'. {exc}") from exc

        encoded_image = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{encoded_image}"

    def _verify_image_contents(self, image_file: Path) -> None:
        """Fail early when the file extension is valid but the image is corrupted."""
        try:
            with Image.open(image_file) as image:
                image.verify()
        except (OSError, UnidentifiedImageError) as exc:
            raise VisionClientError(
                f"Invalid image file '{image_file}'. Please capture a new image and try again."
            ) from exc

    def _should_retry(self, attempt: int) -> bool:
        """Return True when another retry attempt is still available."""
        if attempt >= self.retry_attempts:
            return False

        delay_seconds = self.retry_backoff_seconds * (2 ** (attempt - 1))
        if delay_seconds > 0:
            self._sleep(delay_seconds)
        return True

    def _log_retry(
        self,
        reason: str,
        mode: str,
        model: str,
        attempt: int,
        exc: Exception,
    ) -> None:
        """Log a retryable request failure with structured context."""
        LOGGER.warning(
            "OpenAI request retrying mode=%s model=%s attempt=%s/%s reason=%s error=%s",
            mode,
            model,
            attempt,
            self.retry_attempts,
            reason,
            exc,
        )


def _import_openai_sdk():
    """Import the OpenAI SDK lazily so setup errors can be shown cleanly."""
    try:
        import openai
        from openai import OpenAI
    except ImportError as exc:
        raise VisionClientError(
            "OpenAI SDK is not installed. Activate your virtual environment and run: pip install -r requirements.txt"
        ) from exc

    return openai, OpenAI
