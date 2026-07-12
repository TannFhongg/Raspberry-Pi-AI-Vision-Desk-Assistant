"""OpenCV preprocessing helpers for captured camera images."""

from __future__ import annotations

import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vision.enhance_text import enhance_text_image
from vision.perspective import four_point_transform
from vision.screen_detect import detect_screen_region, draw_detected_region
from visiondesk.paths import resolve_visiondesk_paths

_DEFAULT_PATHS = resolve_visiondesk_paths()
DEFAULT_INPUT_PATH = str(_DEFAULT_PATHS.private_current_path / "captured.jpg")
DEFAULT_OUTPUT_PATH = str(_DEFAULT_PATHS.private_current_path / "processed.jpg")
DEFAULT_DEBUG_DIR = str(_DEFAULT_PATHS.debug_dir)
DEFAULT_MAX_DIMENSION = 1600
PREPROCESS_METADATA_SUFFIX = ".meta.json"
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
    warnings: tuple[str, ...] = ()
    screen_detected: bool = False
    perspective_corrected: bool = False
    debug_dir: Path | None = None


def preprocess_image(
    input_path: str = DEFAULT_INPUT_PATH,
    output_path: str = DEFAULT_OUTPUT_PATH,
    grayscale: bool = False,
    max_dimension: int = DEFAULT_MAX_DIMENSION,
    detect_screen: bool = False,
    enhance_text: bool = False,
    debug_dir: str = DEFAULT_DEBUG_DIR,
) -> PreprocessResult:
    """Load an image, preprocess it safely, and save the final result."""
    if max_dimension <= 0:
        raise ImagePreprocessError("max_dimension must be greater than 0.")

    cv2 = _import_cv2()
    source = _validate_input_path(input_path)
    destination = Path(output_path)
    _prepare_output_path(destination)
    temporary_output = _build_temporary_output_path(destination)

    warnings: list[str] = []
    debug_path: Path | None = None
    screen_detected = False
    perspective_corrected = False

    try:
        image = cv2.imread(str(source), cv2.IMREAD_COLOR)
        if image is None:
            raise ImagePreprocessError(
                f"Could not load image from '{source}'. Make sure the captured image exists and is a valid image."
            )

        original_height, original_width = image.shape[:2]
        processed_image = image

        if detect_screen or enhance_text:
            debug_path = Path(debug_dir)
            _prepare_debug_directory(debug_path)
            _save_debug_image(debug_path / "original.jpg", image, cv2)

            detected_overlay = image.copy()
            corrected_image = image.copy()

            if detect_screen:
                detection = detect_screen_region(image, cv2)
                if detection is None:
                    warnings.append(
                        "Screen/document rectangle not detected. Using original image fallback."
                    )
                else:
                    screen_detected = True
                    perspective_corrected = True
                    detected_overlay = draw_detected_region(image, detection.source_points, cv2)
                    corrected_image = four_point_transform(image, detection.source_points, cv2)

            _save_debug_image(debug_path / "detected_screen.jpg", detected_overlay, cv2)

            corrected_image = resize_if_too_large(
                corrected_image,
                max_dimension=max_dimension,
                cv2_module=cv2,
            )
            _save_debug_image(debug_path / "corrected.jpg", corrected_image, cv2)

            if enhance_text:
                processed_image = enhance_text_image(
                    corrected_image,
                    cv2_module=cv2,
                    grayscale=grayscale,
                )
            else:
                processed_image = (
                    convert_to_grayscale(corrected_image, cv2)
                    if grayscale
                    else corrected_image
                )

            _save_debug_image(debug_path / "enhanced.jpg", processed_image, cv2)
        else:
            processed_image = resize_if_too_large(
                image,
                max_dimension=max_dimension,
                cv2_module=cv2,
            )
            if grayscale:
                processed_image = convert_to_grayscale(processed_image, cv2)
            processed_image = improve_contrast(
                processed_image,
                cv2_module=cv2,
                grayscale=grayscale,
            )
            processed_image = apply_light_sharpening(processed_image, cv2)

        saved = cv2.imwrite(str(temporary_output), processed_image)
        if not saved:
            raise ImagePreprocessError(
                f"OpenCV could not save the processed image to '{destination}'."
            )

        _validate_output_file(temporary_output)
        _finalize_output_file(temporary_output, destination)
        write_preprocess_metadata(
            output_path=destination,
            metadata=build_preprocess_metadata(
                input_path=source,
                grayscale=grayscale,
                max_dimension=max_dimension,
                detect_screen=detect_screen,
                enhance_text=enhance_text,
            ),
        )

        processed_height, processed_width = processed_image.shape[:2]
        return PreprocessResult(
            input_path=source,
            output_path=destination,
            original_size=(original_width, original_height),
            processed_size=(processed_width, processed_height),
            grayscale_applied=grayscale,
            warnings=tuple(warnings),
            screen_detected=screen_detected,
            perspective_corrected=perspective_corrected,
            debug_dir=debug_path,
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

    lab_image = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2_module.split(lab_image)
    lightness = clahe.apply(lightness)
    merged = cv2_module.merge((lightness, a_channel, b_channel))
    return cv2_module.cvtColor(merged, cv2_module.COLOR_LAB2BGR)


def apply_light_sharpening(image, cv2_module):
    """Use a mild unsharp mask to keep details crisp without harsh artifacts."""
    blurred = cv2_module.GaussianBlur(image, (0, 0), 1.0)
    return cv2_module.addWeighted(image, 1.15, blurred, -0.15, 0)


def get_preprocess_metadata_path(output_path: str | Path) -> Path:
    """Return the sidecar metadata path for a processed image."""
    destination = Path(output_path)
    return destination.with_name(f"{destination.name}{PREPROCESS_METADATA_SUFFIX}")


def build_preprocess_metadata(
    input_path: str | Path,
    grayscale: bool,
    max_dimension: int,
    detect_screen: bool,
    enhance_text: bool,
) -> dict[str, Any]:
    """Build the metadata payload used for processed-image freshness checks."""
    source = Path(input_path)
    return {
        "schema_version": 1,
        "source_path": str(source.resolve()),
        "source_mtime_ns": source.stat().st_mtime_ns,
        "options": {
            "grayscale": bool(grayscale),
            "max_dimension": int(max_dimension),
            "detect_screen": bool(detect_screen),
            "enhance_text": bool(enhance_text),
        },
    }


def write_preprocess_metadata(output_path: str | Path, metadata: dict[str, Any]) -> Path:
    """Atomically save metadata next to the processed image."""
    metadata_path = get_preprocess_metadata_path(output_path)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_metadata = _build_temporary_file_path(
        metadata_path.parent,
        prefix=f".{metadata_path.stem}-",
        suffix=metadata_path.suffix,
    )

    try:
        temporary_metadata.write_text(
            json.dumps(metadata, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_metadata.replace(metadata_path)
    except OSError as exc:
        _cleanup_temporary_file(temporary_metadata)
        raise ImagePreprocessError(
            f"Could not save preprocessing metadata to '{metadata_path}'. {exc}"
        ) from exc

    return metadata_path


def load_preprocess_metadata(output_path: str | Path) -> dict[str, Any] | None:
    """Read the metadata sidecar for a processed image when present."""
    metadata_path = get_preprocess_metadata_path(output_path)
    if not metadata_path.is_file():
        return None

    try:
        raw_data = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(raw_data, dict):
        return None
    return raw_data


def preprocess_output_matches(
    input_path: str | Path,
    output_path: str | Path,
    grayscale: bool,
    max_dimension: int,
    detect_screen: bool,
    enhance_text: bool,
) -> bool:
    """Return True when processed-image metadata matches the current preprocessing inputs."""
    output_file = Path(output_path)
    input_file = Path(input_path)
    if not output_file.is_file():
        return False
    if not input_file.is_file():
        return True

    existing_metadata = load_preprocess_metadata(output_file)
    if existing_metadata is None:
        return False

    expected_metadata = build_preprocess_metadata(
        input_path=input_file,
        grayscale=grayscale,
        max_dimension=max_dimension,
        detect_screen=detect_screen,
        enhance_text=enhance_text,
    )
    return existing_metadata == expected_metadata


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
            f"No input image found at '{input_path}'. Capture an image first so a source image exists."
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
        if output_path.exists() and output_path.is_dir():
            raise ImagePreprocessError(
                f"Output path '{output_path}' is a directory. Please provide a file path."
            )
    except ImagePreprocessError:
        raise
    except OSError as exc:
        raise ImagePreprocessError(
            f"Could not prepare output path '{output_path}'. {exc}"
        ) from exc


def _prepare_debug_directory(debug_path: Path) -> None:
    """Create the debug directory for intermediate images."""
    try:
        debug_path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ImagePreprocessError(
            f"Could not prepare debug directory '{debug_path}'. {exc}"
        ) from exc


def _save_debug_image(debug_path: Path, image, cv2_module) -> None:
    """Save a debug image and verify it was written."""
    saved = cv2_module.imwrite(str(debug_path), image)
    if not saved:
        raise ImagePreprocessError(f"Could not save debug image to '{debug_path}'.")
    _validate_output_file(debug_path)


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
    return _build_temporary_file_path(
        output_path.parent,
        prefix=f".{output_path.stem}-",
        suffix=output_path.suffix,
    )


def _build_temporary_file_path(directory: Path, prefix: str, suffix: str) -> Path:
    """Create a temporary file path in the given directory."""
    try:
        temporary_file = tempfile.NamedTemporaryFile(
            delete=False,
            dir=directory,
            prefix=prefix,
            suffix=suffix,
        )
        temporary_file.close()
    except OSError as exc:
        raise ImagePreprocessError(
            f"Could not create a temporary file in '{directory}'. {exc}"
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
