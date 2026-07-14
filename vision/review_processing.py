"""Non-destructive image adjustments used by the capture review workflow.

The review controller owns the original capture.  This module only creates a
new confirmed image, so the file shown as the final preview is exactly the file
that can be handed to the AI client.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any

import numpy as np

from vision.perspective import four_point_transform, order_points


class ReviewProcessingError(Exception):
    """Raised when a review adjustment cannot be rendered safely."""


@dataclass(frozen=True, slots=True)
class CropRect:
    """A crop in original-image coordinates."""

    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True, slots=True)
class ReviewAdjustments:
    """Confirmed user adjustments. Crop coordinates always remain original-space."""

    crop: CropRect | None = None
    rotation_degrees: int = 0
    perspective_points: tuple[tuple[float, float], ...] = ()
    perspective_enabled: bool = False
    auto_enhance: bool = False


DEFAULT_QUALITY_THRESHOLDS: dict[str, float] = {
    "sharpness_warning_variance": 80.0,
    "brightness_dark_mean": 55.0,
    "brightness_bright_mean": 220.0,
    "glare_bright_ratio": 0.12,
    "minimum_crop_area_ratio": 0.035,
}


def normalize_rotation(rotation_degrees: int | float) -> int:
    """Normalize a rotation to the supported clockwise quarter turns."""
    normalized = int(round(float(rotation_degrees))) % 360
    if normalized not in {0, 90, 180, 270}:
        raise ValueError("Review rotation must be a multiple of 90 degrees.")
    return normalized


def image_size(path: str | Path) -> tuple[int, int]:
    """Return `(width, height)` for an image without exposing its contents."""
    try:
        image = _read_image(path)
        height, width = image.shape[:2]
        return int(width), int(height)
    except ReviewProcessingError:
        try:
            from PIL import Image
            with Image.open(path) as image:
                return int(image.width), int(image.height)
        except (ImportError, OSError) as exc:
            raise ReviewProcessingError("VisionDesk could not read the captured image.") from exc


def clamp_crop(crop: CropRect | None, image_width: int, image_height: int, *, minimum_size: int = 32) -> CropRect | None:
    """Keep an original-space crop inside bounds with a usable minimum size."""
    if crop is None:
        return None
    if image_width <= 0 or image_height <= 0:
        raise ValueError("Image dimensions must be positive.")
    min_width = min(max(1, int(minimum_size)), image_width)
    min_height = min(max(1, int(minimum_size)), image_height)
    width = min(image_width, max(min_width, int(crop.width)))
    height = min(image_height, max(min_height, int(crop.height)))
    x = min(max(0, int(crop.x)), image_width - width)
    y = min(max(0, int(crop.y)), image_height - height)
    return CropRect(x=x, y=y, width=width, height=height)


def crop_from_normalized(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    image_width: int,
    image_height: int,
    rotation_degrees: int = 0,
    minimum_size: int = 32,
) -> CropRect:
    """Map a displayed rotated crop into original-image coordinates.

    QML operates in normalized coordinates of the currently displayed
    orientation.  A 90-degree rotation still maps to an axis-aligned rectangle
    in original space, which lets the stored crop remain stable across redraws.
    """
    rotation = normalize_rotation(rotation_degrees)
    display_width, display_height = rotated_size(image_width, image_height, rotation)
    left = max(0.0, min(1.0, float(x))) * display_width
    top = max(0.0, min(1.0, float(y))) * display_height
    right = max(left, min(float(display_width), float(x + width) * display_width))
    bottom = max(top, min(float(display_height), float(y + height) * display_height))
    corners = np.array(
        [[left, top], [right, top], [right, bottom], [left, bottom]], dtype="float32"
    )
    original = rotated_points_to_original(corners, image_width, image_height, rotation)
    min_x = int(np.floor(np.min(original[:, 0])))
    min_y = int(np.floor(np.min(original[:, 1])))
    max_x = int(np.ceil(np.max(original[:, 0])))
    max_y = int(np.ceil(np.max(original[:, 1])))
    return clamp_crop(
        CropRect(min_x, min_y, max_x - min_x, max_y - min_y),
        image_width,
        image_height,
        minimum_size=minimum_size,
    ) or CropRect(0, 0, image_width, image_height)


def crop_to_rotated(crop: CropRect | None, image_width: int, image_height: int, rotation_degrees: int = 0) -> CropRect | None:
    """Map an original-space crop into the displayed rotated image space."""
    clamped = clamp_crop(crop, image_width, image_height)
    if clamped is None:
        return None
    corners = np.array(
        [
            [clamped.x, clamped.y],
            [clamped.x + clamped.width, clamped.y],
            [clamped.x + clamped.width, clamped.y + clamped.height],
            [clamped.x, clamped.y + clamped.height],
        ],
        dtype="float32",
    )
    rotated = original_points_to_rotated(corners, image_width, image_height, rotation_degrees)
    min_x = int(np.floor(np.min(rotated[:, 0])))
    min_y = int(np.floor(np.min(rotated[:, 1])))
    max_x = int(np.ceil(np.max(rotated[:, 0])))
    max_y = int(np.ceil(np.max(rotated[:, 1])))
    rotated_width, rotated_height = rotated_size(image_width, image_height, rotation_degrees)
    return clamp_crop(
        CropRect(min_x, min_y, max_x - min_x, max_y - min_y),
        rotated_width,
        rotated_height,
    )


def rotated_size(image_width: int, image_height: int, rotation_degrees: int = 0) -> tuple[int, int]:
    """Return the dimensions after a quarter-turn rotation."""
    return (image_height, image_width) if normalize_rotation(rotation_degrees) in {90, 270} else (image_width, image_height)


def original_points_to_rotated(points, image_width: int, image_height: int, rotation_degrees: int = 0) -> np.ndarray:
    """Map original coordinates to the displayed clockwise-rotated coordinates."""
    rotation = normalize_rotation(rotation_degrees)
    source = np.asarray(points, dtype="float32").copy()
    x, y = source[:, 0], source[:, 1]
    if rotation == 90:
        return np.column_stack((image_height - y, x)).astype("float32")
    if rotation == 180:
        return np.column_stack((image_width - x, image_height - y)).astype("float32")
    if rotation == 270:
        return np.column_stack((y, image_width - x)).astype("float32")
    return source


def rotated_points_to_original(points, image_width: int, image_height: int, rotation_degrees: int = 0) -> np.ndarray:
    """Map displayed clockwise-rotated coordinates back to original coordinates."""
    rotation = normalize_rotation(rotation_degrees)
    source = np.asarray(points, dtype="float32").copy()
    x, y = source[:, 0], source[:, 1]
    if rotation == 90:
        return np.column_stack((y, image_height - x)).astype("float32")
    if rotation == 180:
        return np.column_stack((image_width - x, image_height - y)).astype("float32")
    if rotation == 270:
        return np.column_stack((image_width - y, x)).astype("float32")
    return source


def detect_document_quadrilateral(image_path: str | Path) -> tuple[tuple[float, float], ...] | None:
    """Find the largest conservative four-corner document candidate, if any."""
    try:
        cv2 = _import_cv2()
    except ReviewProcessingError:
        return None
    image = _read_image(image_path, cv2)
    height, width = image.shape[:2]
    if width < 80 or height < 80:
        return None
    scale = min(1.0, 960.0 / float(max(width, height)))
    preview = image if scale == 1.0 else cv2.resize(image, (round(width * scale), round(height * scale)))
    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = float(preview.shape[0] * preview.shape[1]) * 0.16
    candidates: list[tuple[float, np.ndarray]] = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if area < minimum_area:
            continue
        perimeter = cv2.arcLength(contour, True)
        approximation = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(approximation) != 4 or not cv2.isContourConvex(approximation):
            continue
        points = approximation.reshape(4, 2).astype("float32")
        try:
            ordered = order_points(points)
        except ValueError:
            continue
        candidates.append((area, ordered))
    if not candidates:
        return None
    _area, points = max(candidates, key=lambda candidate: candidate[0])
    if scale != 1.0:
        points /= scale
    return tuple((float(x), float(y)) for x, y in points)


def assess_image_quality(image_path: str | Path, *, crop: CropRect | None = None, thresholds: dict[str, float] | None = None) -> list[dict[str, str]]:
    """Return understandable, non-blocking image quality warnings.

    These are heuristics, not assertions about the image.  Values are retained
    only for the current session and are intentionally not logged.
    """
    try:
        cv2 = _import_cv2()
        image = _read_image(image_path, cv2)
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    except ReviewProcessingError:
        try:
            from PIL import Image
            with Image.open(image_path) as source:
                gray = np.asarray(source.convert("L"), dtype="float32")
        except (ImportError, OSError) as exc:
            raise ReviewProcessingError("VisionDesk could not inspect the captured image.") from exc
        sharpness = float(np.var(np.diff(gray, axis=0))) if gray.shape[0] > 1 else 0.0
    values = dict(DEFAULT_QUALITY_THRESHOLDS)
    values.update({key: float(value) for key, value in (thresholds or {}).items() if value is not None})
    warnings: list[dict[str, str]] = []
    mean_brightness = float(np.mean(gray))
    bright_ratio = float(np.mean(gray >= 245))
    if sharpness < values["sharpness_warning_variance"]:
        warnings.append({"key": "blur", "title": "Image may be blurry", "message": "Retake the image or steady the camera before continuing.", "tone": "warning"})
    if mean_brightness < values["brightness_dark_mean"]:
        warnings.append({"key": "dark", "title": "Image is too dark", "message": "Improve lighting or adjust the screen brightness, then retake if needed.", "tone": "warning"})
    elif mean_brightness > values["brightness_bright_mean"]:
        warnings.append({"key": "bright", "title": "Image is very bright", "message": "Reduce glare or exposure before continuing.", "tone": "warning"})
    if bright_ratio >= values["glare_bright_ratio"]:
        warnings.append({"key": "glare", "title": "Strong glare detected", "message": "Change the camera angle or reduce reflections.", "tone": "warning"})
    if crop is not None:
        full_area = max(1, gray.shape[0] * gray.shape[1])
        crop_area = max(0, crop.width) * max(0, crop.height)
        if crop_area / float(full_area) < values["minimum_crop_area_ratio"]:
            warnings.append({"key": "small_crop", "title": "Move closer or select a smaller region", "message": "The selected subject area may be too small for a reliable answer.", "tone": "warning"})
    return warnings


def render_review_image(
    input_path: str | Path,
    output_path: str | Path,
    adjustments: ReviewAdjustments,
) -> Path:
    """Write the exact adjusted image that will be submitted after confirmation."""
    try:
        cv2 = _import_cv2()
    except ReviewProcessingError:
        return _render_with_pillow(input_path, output_path, adjustments)
    source = _read_image(input_path, cv2)
    source_height, source_width = source.shape[:2]
    rotation = normalize_rotation(adjustments.rotation_degrees)
    rendered = _rotate_image(source, rotation, cv2)
    rendered_crop = crop_to_rotated(adjustments.crop, source_width, source_height, rotation)
    if rendered_crop is not None:
        rendered = rendered[
            rendered_crop.y : rendered_crop.y + rendered_crop.height,
            rendered_crop.x : rendered_crop.x + rendered_crop.width,
        ]
    if adjustments.perspective_enabled and len(adjustments.perspective_points) == 4:
        points = np.asarray(adjustments.perspective_points, dtype="float32")
        points = original_points_to_rotated(points, source_width, source_height, rotation)
        if rendered_crop is not None:
            points[:, 0] -= rendered_crop.x
            points[:, 1] -= rendered_crop.y
        if _points_inside_image(points, rendered.shape[1], rendered.shape[0]):
            rendered = four_point_transform(rendered, points, cv2)
        else:
            raise ReviewProcessingError("The proposed document boundary is outside the selected image.")
    if adjustments.auto_enhance:
        rendered = _enhance_contrast(rendered, cv2)
    if rendered.size == 0:
        raise ReviewProcessingError("The selected crop does not contain an image.")
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_output_path(destination)
    try:
        if not cv2.imwrite(str(temporary), rendered):
            raise ReviewProcessingError("VisionDesk could not save the adjusted image.")
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise ReviewProcessingError("The adjusted image was empty.")
        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _rotate_image(image, rotation: int, cv2_module):
    if rotation == 90:
        return cv2_module.rotate(image, cv2_module.ROTATE_90_CLOCKWISE)
    if rotation == 180:
        return cv2_module.rotate(image, cv2_module.ROTATE_180)
    if rotation == 270:
        return cv2_module.rotate(image, cv2_module.ROTATE_90_COUNTERCLOCKWISE)
    return image


def _render_with_pillow(input_path: str | Path, output_path: str | Path, adjustments: ReviewAdjustments) -> Path:
    """Mock/development fallback when the host lacks OpenCV bindings."""
    try:
        from PIL import Image, ImageEnhance, ImageOps
    except ImportError as exc:
        raise ReviewProcessingError("OpenCV or Pillow is required for image review adjustments.") from exc
    source = Image.open(input_path).convert("RGB")
    source_width, source_height = source.size
    rotation = normalize_rotation(adjustments.rotation_degrees)
    rotated = source.rotate(-rotation, expand=True)
    crop = crop_to_rotated(adjustments.crop, source_width, source_height, rotation)
    if crop is not None:
        rotated = rotated.crop((crop.x, crop.y, crop.x + crop.width, crop.y + crop.height))
    if adjustments.perspective_enabled:
        # Pillow's generic perspective coefficients are not a safe replacement
        # for OpenCV point transforms, so preserve the reviewed crop and warn
        # through the controller rather than silently warping it.
        raise ReviewProcessingError("Perspective correction requires OpenCV on this device.")
    if adjustments.auto_enhance:
        rotated = ImageEnhance.Contrast(ImageOps.autocontrast(rotated)).enhance(1.08)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = _temporary_output_path(destination)
    try:
        rotated.save(temporary, format="JPEG", quality=90)
        if not temporary.is_file() or temporary.stat().st_size <= 0:
            raise ReviewProcessingError("The adjusted image was empty.")
        temporary.replace(destination)
        return destination
    except Exception:
        temporary.unlink(missing_ok=True)
        raise


def _enhance_contrast(image, cv2_module):
    lab = cv2_module.cvtColor(image, cv2_module.COLOR_BGR2LAB)
    lightness, a_channel, b_channel = cv2_module.split(lab)
    clahe = cv2_module.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = cv2_module.merge((clahe.apply(lightness), a_channel, b_channel))
    return cv2_module.cvtColor(enhanced, cv2_module.COLOR_LAB2BGR)


def _points_inside_image(points, width: int, height: int) -> bool:
    return bool(np.all(points[:, 0] >= 0) and np.all(points[:, 1] >= 0) and np.all(points[:, 0] <= width) and np.all(points[:, 1] <= height))


def _read_image(path: str | Path, cv2_module=None):
    cv2 = cv2_module or _import_cv2()
    image = cv2.imread(str(path))
    if image is None or image.size == 0:
        raise ReviewProcessingError("VisionDesk could not read the captured image.")
    return image


def _temporary_output_path(destination: Path) -> Path:
    handle = tempfile.NamedTemporaryFile(delete=False, dir=destination.parent, prefix=f".{destination.stem}-", suffix=destination.suffix)
    handle.close()
    return Path(handle.name)


def _import_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise ReviewProcessingError("OpenCV is required for image review adjustments.") from exc
    return cv2
