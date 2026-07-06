"""OpenCV preprocessing helpers for the captured camera image."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

DEFAULT_INPUT_PATH = "static/captured.jpg"
DEFAULT_OUTPUT_PATH = "static/processed.jpg"
DEFAULT_MAX_DIMENSION = 1600
OPENCV_INSTALL_HINT = (
    "OpenCV is not available. On Raspberry Pi OS, install it with: "
    "sudo apt install -y python3-opencv and create the virtual environment with: "
    "python3 -m venv --system-site-packages .venv"
)


class ImagePreprocessError(Exception):
    """Friendly error raised when image preprocessing fails."""


@dataclass(slots=True)
class PreprocessResult:
    """Metadata about a completed preprocessing run."""

    input_path: Path
    output_path: Path
    original_size: tuple[int, int]
    processed_size: tuple[int, int]
    grayscale_applied: bool


def preprocess_image(
    input_path: str = DEFAULT_INPUT_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    grayscale: bool = False,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
) -> PreprocessResult:
    """Load an image, apply safe OpenCV preprocessing, and save the result."""
    if max_dimension <= 0:
        raise ImagePreprocessError("max_dimension must be greater than 0.")

    cv2 = _import_cv2()
    source = _validate_input_path(input_path)
    destination = Path(output_path)
    _prepare_output_path(destination)
    temporary_output = _build_temporary_output_path(destination)

    try:
        # OpenCV loads color images in BGR channel order, which is the format used below.
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise ImagePreprocessError(
                f"Could not load image from '{source}'. Make sure static/captured.jpg exists and is a valid image."
            )

        original_height, original_width = image.shape[:2]

        # Step 1: Resize only when the image is large, to keep details while reducing payload size.
        image = resize_if_too_large(image, max_dimension=max_dimension, cv2_module=cv2)

        # Step 2: Convert color safely for the selected processing mode.
        if grayscale:
            image = convert_to_grayscale(image, cv2_module=cv2)

        # Step 3: Improve contrast gently so text and edges are easier to read.
        image = improve_contrast(image, cv2_module=cv2, grayscale=grayscale)

        # Step 4: Apply a light unsharp mask to recover detail without over-processing.
        image = apply_light_sharpening(image, cv2_module=cv2)

        saved = cv2.imwrite(str(temporary_output), image)
        if not saved:
            raise ImagePreprocessError(
                f"OpenCV could not save the processed image to '{destination}'."
            )

        _validate_output_file(temporary_output)
        _finalize_output_file(temporary_output, destination)

        processed_height, processed_width = image.shape[:2]
        return PreprocessResult(
            input_path=source,
            output_path=destination,
            original_size=(original_width, original_height),
            processed_size=(processed_width, processed_height),
            grayscale_applied=grayscale,
        )
    except ImagePreprocessError:
        _cleanup_temporary_file(temporary_output)
        raise


def resize_if_too_large(image, max_dimension: int, cv2_module):
    """Shrink the image if its longest side is above the configured limit."""
    height, width = image.shape[:2]
    longest_side = max(width, height)
    if longest_side <= max_dimension:
        return image

    scale = max_dimension / float(longest_side)
    new_width = max(1, int(round(width * scale)))
    new_height = max(1, int(round(height * scale)))
    return cv2_module.resize(image, (new_width, new_height), interpolation=cv2_module.INTER_AREA)


def convert_to_grayscale(image, cv2_module):
    """Convert the BGR image to single-channel grayscale when requested."""
    return cv2_module.cvtColor(image, cv2_module.COLOR_BGR2GRAY)


def improve_contrast(image, cv2_module, grayscale: bool):
    """Apply gentle CLAHE contrast improvement while protecting natural colors."""
    clahe = cv2_module.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    if grayscale:
        return clahe.apply(image)

    # Convert BGR to LAB so contrast changes affect brightness more than color balance.
    lab_image = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2_module.split(lab_image)
    lightness = clahe.apply(lightness)
    merged = cv2_module.merge((lightness, a_channel, b_channel))

    # Convert back to BGR before saving so the output colors stay correct.
    return cv2_module.cvtColor(merged, cv2_module.COLOR_LAB2BGR)


def apply_light_sharpening(image, cv2_module):
    """Use a mild unsharp mask to keep details crisp without introducing harsh artifacts."""
    blurred = cv2_module.GaussianBlur(image, (0, 0), 1.0)
    return cv2_module.addWeighted(image, 1.15, blurred, -0.15, 0)


def _import_cv2():
    """Import OpenCV lazily so other phases do not fail at startup."""
    try:
        import cv2
    except ImportError as exc:
        raise ImagePreprocessError(OPENCV_INSTALL_HINT) from exc

    return cv2


def _validate_input_path(input_path: str) -> Path:
    """Confirm that the source image exists and is a file."""
    source = Path(input_path)
    if not source.exists():
        raise ImagePreprocessError(
            f"No input image found at '{input_path}'. Capture an image first so static/captured.jpg exists."
        )
    if not source.is_file():
        raise ImagePreprocessError(
            f"'{input_path}' is not a file. Please provide a valid input image path."
        )
    return source


def _prepare_output_path(output_path: Path) -> None:
    """Create the output directory and confirm the destination is a file path."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if output_path.exists():
            if output_path.is_dir():
                raise ImagePreprocessError(
                    f"Output path '{output_path}' is a directory. Please provide a file path."
                )
    except ImagePreprocessError:
        raise
    except OSError as exc:
        raise ImagePreprocessError(
            f"Could not prepare output path '{output_path}'. {exc}"
        ) from exc


def _validate_output_file(output_path: Path) -> None:
    """Confirm that the saved processed file exists and is not empty."""
    if not output_path.exists():
        raise ImagePreprocessError(
            f"Preprocessing finished but '{output_path}' was not created."
        )
    if output_path.stat().st_size <= 0:
        raise ImagePreprocessError(
            f"Preprocessing finished but '{output_path}' is empty."
        )


def _build_temporary_output_path(output_path: Path) -> Path:
    """Create a temporary processed-image path in the target directory."""
    try:
        temporary_file = tempfile.NamedTemporaryFile(
            delete=False,
            dir=output_path.parent,
            prefix=f".{output_path.stem}-",
            suffix=output_path.suffix,
        )
        temporary_file.close()
    except OSError as exc:
        raise ImagePreprocessError(
            f"Could not create a temporary file for '{output_path}'. {exc}"
        ) from exc

    return Path(temporary_file.name)


def _finalize_output_file(source_path: Path, destination_path: Path) -> None:
    """Replace the old processed image only after the new one is valid."""
    try:
        source_path.replace(destination_path)
    except OSError as exc:
        _cleanup_temporary_file(source_path)
        raise ImagePreprocessError(
            f"Preprocessing succeeded but could not move the image to '{destination_path}'. {exc}"
        ) from exc


def _cleanup_temporary_file(path: Path) -> None:
    """Remove a temporary processed-image file after a failed run."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass
