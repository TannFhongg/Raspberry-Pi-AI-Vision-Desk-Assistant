"""Reusable OpenAI vision client for the Phase 1 terminal MVP."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from ai.prompts import build_prompt

DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"
MAX_IMAGE_SIZE_MB = 10
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
SUPPORTED_IMAGE_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


class VisionClientError(Exception):
    """Friendly application-level error for image analysis failures."""


class OpenAIVisionClient:
    """Small wrapper around the OpenAI Responses API for image analysis."""

    def __init__(self, api_key: str | None = None, default_model: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise VisionClientError(
                "Missing OpenAI API key. Set OPENAI_API_KEY in your .env file before running the test."
            )

        self.default_model = default_model or os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
        self._openai, openai_client_class = _import_openai_sdk()
        self.client = openai_client_class(api_key=self.api_key)

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
            prompt = build_prompt(mode, extra_instruction)
        except ValueError as exc:
            raise VisionClientError(str(exc)) from exc

        mime_type = self._get_mime_type(image_file)
        data_url = self._build_data_url(image_file, mime_type)
        selected_model = model or self.default_model

        try:
            response = self.client.responses.create(
                model=selected_model,
                input=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": prompt},
                            {"type": "input_image", "image_url": data_url},
                        ],
                    }
                ],
                text={"verbosity": "low"},
            )
        except self._openai.AuthenticationError as exc:
            raise VisionClientError(
                "Authentication failed. Check that OPENAI_API_KEY is correct and active."
            ) from exc
        except self._openai.PermissionDeniedError as exc:
            raise VisionClientError(
                f"Permission denied for model '{selected_model}'. Verify your API project has access to this model."
            ) from exc
        except self._openai.NotFoundError as exc:
            raise VisionClientError(
                f"Model '{selected_model}' was not found. Check the model name in your .env file or --model argument."
            ) from exc
        except self._openai.RateLimitError as exc:
            raise VisionClientError(
                "OpenAI rate limit or quota reached. Wait a moment, then try again, or check your billing and usage limits."
            ) from exc
        except self._openai.APIConnectionError as exc:
            raise VisionClientError(
                "Could not connect to OpenAI. Check your internet connection and try again."
            ) from exc
        except self._openai.APITimeoutError as exc:
            raise VisionClientError("The OpenAI request timed out. Please try again.") from exc
        except self._openai.BadRequestError as exc:
            raise VisionClientError(
                "OpenAI rejected the request. Check that the image is valid and the request settings are correct."
            ) from exc
        except self._openai.APIStatusError as exc:
            raise VisionClientError(
                f"OpenAI API error (status {exc.status_code}). Please try again in a moment."
            ) from exc
        except self._openai.OpenAIError as exc:
            raise VisionClientError(f"OpenAI SDK error: {exc}") from exc

        answer = (response.output_text or "").strip()
        if not answer:
            raise VisionClientError("The model returned an empty response. Try a different image or mode.")

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
