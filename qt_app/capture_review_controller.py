"""QML-facing state model for capture review, crop, and confirmation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Property, Signal, Slot

from camera.capabilities import CameraCapabilities, detect_camera_capabilities
from qt_app.image_provider import CachedImageStore
from qt_app.models import DictListModel
from qt_app.runtime import VisionDeskRuntime
from vision.review_processing import (
    CropRect,
    ReviewAdjustments,
    ReviewProcessingError,
    assess_image_quality,
    clamp_crop,
    crop_from_normalized,
    crop_to_rotated,
    detect_document_quadrilateral,
    image_size,
    render_review_image,
)


PROFILE_ITEMS = (
    {"id": "document", "label": "Document", "description": "Use a page boundary guide and offer perspective correction."},
    {"id": "computer_screen", "label": "Computer Screen", "description": "Use a screen safe area and conservative correction."},
    {"id": "diagram", "label": "Diagram", "description": "Keep lines and labels inside a balanced guide."},
)


class CaptureReviewController(QObject):
    """Keep all review adjustments explicit and private until user confirmation."""

    stateChanged = Signal()
    sourceRevisionChanged = Signal()
    previewRevisionChanged = Signal()
    capabilitiesChanged = Signal()

    def __init__(
        self,
        runtime: VisionDeskRuntime,
        *,
        source_store: CachedImageStore,
        preview_store: CachedImageStore,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self.source_store = source_store
        self.preview_store = preview_store
        self.profile_model = DictListModel(["id", "label", "description"], self)
        self.profile_model.set_items(list(PROFILE_ITEMS))
        self.warning_model = DictListModel(["key", "title", "message", "tone"], self)
        self.capability_model = DictListModel(["key", "label", "supported", "message"], self)
        self._capabilities = detect_camera_capabilities(runtime.settings, mock_hardware=runtime.mock_hardware)
        self._profile = runtime.settings.capture_review.default_profile
        self._state = "idle"
        self._source_path: Path | None = None
        self._confirmed_path: Path | None = None
        self._source_size = (0, 0)
        self._crop: CropRect | None = None
        self._rotation = 0
        self._perspective_points: tuple[tuple[float, float], ...] = ()
        self._perspective_enabled = False
        self._auto_enhance = False
        self._preview_zoom = (0.0, 0.0, 1.0, 1.0)
        self._quality_warning_text = ""
        self._update_capability_model()

    @Property(QObject, constant=True)
    def captureProfilesModel(self) -> DictListModel:
        return self.profile_model

    @Property(QObject, constant=True)
    def imageQualityWarningsModel(self) -> DictListModel:
        return self.warning_model

    @Property(QObject, constant=True)
    def cameraCapabilitiesModel(self) -> DictListModel:
        return self.capability_model

    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(str, notify=stateChanged)
    def captureProfile(self) -> str:
        return self._profile

    @Property(str, notify=stateChanged)
    def captureProfileLabel(self) -> str:
        return next((str(item["label"]) for item in PROFILE_ITEMS if item["id"] == self._profile), "Document")

    @Property(int, notify=sourceRevisionChanged)
    def sourceRevision(self) -> int:
        return self.source_store.revision

    @Property(int, notify=previewRevisionChanged)
    def previewRevision(self) -> int:
        return self.preview_store.revision

    @Property(bool, notify=stateChanged)
    def hasCapturedImage(self) -> bool:
        return self._source_path is not None and self._source_path.is_file()

    @Property(int, notify=stateChanged)
    def sourceImageWidth(self) -> int:
        return self._source_size[0]

    @Property(int, notify=stateChanged)
    def sourceImageHeight(self) -> int:
        return self._source_size[1]

    @Property(int, notify=stateChanged)
    def rotationDegrees(self) -> int:
        return self._rotation

    @Property(bool, notify=stateChanged)
    def cropActive(self) -> bool:
        return self._crop is not None

    @Property(float, notify=stateChanged)
    def cropX(self) -> float:
        return self._display_crop_value("x")

    @Property(float, notify=stateChanged)
    def cropY(self) -> float:
        return self._display_crop_value("y")

    @Property(float, notify=stateChanged)
    def cropWidth(self) -> float:
        return self._display_crop_value("width")

    @Property(float, notify=stateChanged)
    def cropHeight(self) -> float:
        return self._display_crop_value("height")

    @Property(bool, notify=stateChanged)
    def perspectiveAvailable(self) -> bool:
        return len(self._perspective_points) == 4

    @Property(bool, notify=stateChanged)
    def perspectiveActive(self) -> bool:
        return self._perspective_enabled

    @Property("QVariantList", notify=stateChanged)
    def perspectivePoints(self) -> list[dict[str, float]]:
        width, height = self._source_size
        if width <= 0 or height <= 0:
            return []
        return [{"x": x / width, "y": y / height} for x, y in self._perspective_points]

    @Property(bool, notify=stateChanged)
    def autoEnhanceActive(self) -> bool:
        return self._auto_enhance

    @Property(bool, notify=stateChanged)
    def finalImageDiffersFromOriginal(self) -> bool:
        return bool(self._crop is not None or self._rotation or self._perspective_enabled or self._auto_enhance)

    @Property(bool, notify=stateChanged)
    def autofocusSupported(self) -> bool:
        return self._capabilities.autofocus

    @Property(bool, notify=stateChanged)
    def exposureSupported(self) -> bool:
        return self._capabilities.auto_exposure or self._capabilities.manual_exposure

    @Property(str, notify=stateChanged)
    def autofocusSupportMessage(self) -> str:
        return "Autofocus is available" if self.autofocusSupported else "Not supported by this camera"

    @Property(str, notify=stateChanged)
    def exposureSupportMessage(self) -> str:
        return "Exposure control is available" if self.exposureSupported else "Not supported by this camera"

    @Property(float, notify=stateChanged)
    def previewZoomX(self) -> float:
        return self._preview_zoom[0]

    @Property(float, notify=stateChanged)
    def previewZoomY(self) -> float:
        return self._preview_zoom[1]

    @Property(float, notify=stateChanged)
    def previewZoomWidth(self) -> float:
        return self._preview_zoom[2]

    @Property(float, notify=stateChanged)
    def previewZoomHeight(self) -> float:
        return self._preview_zoom[3]

    @Property(bool, notify=stateChanged)
    def previewZoomActive(self) -> bool:
        return self._preview_zoom[2] < 0.999 or self._preview_zoom[3] < 0.999

    @Property(str, notify=stateChanged)
    def qualityWarningText(self) -> str:
        return self._quality_warning_text

    @Property(bool, notify=stateChanged)
    def canSubmit(self) -> bool:
        return self._state in {"reviewing", "adjusting", "ready_to_submit"} and self._confirmed_path is not None and self._confirmed_path.is_file()

    @Slot(str)
    def setCaptureProfile(self, profile: str) -> None:
        normalized = str(profile or "").strip().lower()
        if normalized not in {item["id"] for item in PROFILE_ITEMS}:
            return
        if normalized == self._profile:
            return
        self._profile = normalized
        profile_defaults = self.runtime.settings.capture_review.profiles.get(normalized, {})
        self._auto_enhance = bool(profile_defaults.get("auto_enhance_default", False))
        if self.hasCapturedImage:
            self._detect_perspective_if_relevant()
            self._render_adjusted_preview()
        self.stateChanged.emit()

    @Slot(float, float, float, float)
    def setPreviewZoomRegion(self, x: float, y: float, width: float, height: float) -> None:
        minimum = 0.18
        normalized_width = min(1.0, max(minimum, float(width)))
        normalized_height = min(1.0, max(minimum, float(height)))
        normalized_x = min(max(0.0, float(x)), 1.0 - normalized_width)
        normalized_y = min(max(0.0, float(y)), 1.0 - normalized_height)
        self._preview_zoom = (normalized_x, normalized_y, normalized_width, normalized_height)
        self.stateChanged.emit()

    @Slot()
    def zoomPreviewIn(self) -> None:
        x, y, width, height = self._preview_zoom
        new_width, new_height = max(0.18, width * 0.78), max(0.18, height * 0.78)
        self.setPreviewZoomRegion(x + (width - new_width) / 2, y + (height - new_height) / 2, new_width, new_height)

    @Slot()
    def zoomPreviewOut(self) -> None:
        x, y, width, height = self._preview_zoom
        new_width, new_height = min(1.0, width / 0.78), min(1.0, height / 0.78)
        self.setPreviewZoomRegion(x - (new_width - width) / 2, y - (new_height - height) / 2, new_width, new_height)

    @Slot()
    def resetPreviewZoom(self) -> None:
        self._preview_zoom = (0.0, 0.0, 1.0, 1.0)
        self.stateChanged.emit()

    def begin_capturing(self) -> None:
        self._state = "capturing"
        self.stateChanged.emit()

    def load_captured_image(self, path: str | Path) -> bool:
        """Start a review session only after capture has completed successfully."""
        self.discard(emit=False)
        source = Path(path)
        try:
            size = image_size(source)
        except (OSError, ReviewProcessingError):
            self._state = "error"
            self._quality_warning_text = "VisionDesk could not prepare the captured image for review."
            self.stateChanged.emit()
            return False
        self._source_path = source
        self._source_size = size
        self.source_store.set_path(source)
        self.sourceRevisionChanged.emit()
        self._state = "captured"
        self._rotation = 0
        self._crop = self._crop_from_preview_zoom()
        profile_defaults = self.runtime.settings.capture_review.profiles.get(self._profile, {})
        self._auto_enhance = bool(profile_defaults.get("auto_enhance_default", False))
        self._detect_perspective_if_relevant()
        self._render_adjusted_preview()
        self._state = "reviewing"
        self.stateChanged.emit()
        return True

    @Slot(float, float, float, float)
    def setCropNormalized(self, x: float, y: float, width: float, height: float) -> None:
        if not self.hasCapturedImage:
            return
        self._crop = crop_from_normalized(
            x,
            y,
            width,
            height,
            image_width=self._source_size[0],
            image_height=self._source_size[1],
            # The canvas deliberately stays in original-image space. Rotation
            # is rendered in the final preview; storing the crop here keeps
            # its coordinates stable and avoids touch/pixel drift.
            rotation_degrees=0,
        )
        self._state = "adjusting"
        self._render_adjusted_preview()
        self._state = "reviewing"
        self.stateChanged.emit()

    @Slot()
    def resetCrop(self) -> None:
        if not self.hasCapturedImage:
            return
        self._crop = None
        self._render_adjusted_preview()
        self.stateChanged.emit()

    @Slot()
    def rotateClockwise(self) -> None:
        self._rotate(90)

    @Slot()
    def rotateCounterClockwise(self) -> None:
        self._rotate(-90)

    @Slot()
    def acceptPerspective(self) -> None:
        if not self.perspectiveAvailable:
            return
        previous_enabled = self._perspective_enabled
        self._perspective_enabled = True
        if not self._render_adjusted_preview():
            # Never leave the UI claiming a correction that could not be
            # rendered into the confirmed file (for example, no OpenCV build).
            self._perspective_enabled = previous_enabled
            self._render_adjusted_preview()
            warnings = self.warning_model.items()
            warnings.append(
                {
                    "key": "perspective_unavailable",
                    "title": "Perspective correction is unavailable",
                    "message": "Use crop or retake the image; it will not be distorted automatically.",
                    "tone": "warning",
                }
            )
            self.warning_model.set_items(warnings)
            self._quality_warning_text = "Perspective correction could not be applied. Crop manually or continue without it."
        self.stateChanged.emit()

    @Slot()
    def rejectPerspective(self) -> None:
        if not self.perspectiveAvailable and not self._perspective_enabled:
            return
        self._perspective_enabled = False
        self._render_adjusted_preview()
        self.stateChanged.emit()

    @Slot()
    def resetPerspective(self) -> None:
        self._perspective_enabled = False
        self._detect_perspective_if_relevant()
        self._render_adjusted_preview()
        self.stateChanged.emit()

    @Slot(bool)
    def setAutoEnhance(self, enabled: bool) -> None:
        self._auto_enhance = bool(enabled)
        self._render_adjusted_preview()
        self.stateChanged.emit()

    @Slot()
    def resetAdjustments(self) -> None:
        self._crop = None
        self._rotation = 0
        self._perspective_enabled = False
        self._auto_enhance = False
        self._detect_perspective_if_relevant()
        self._render_adjusted_preview()
        self.stateChanged.emit()

    def mark_validating(self) -> bool:
        if not self.canSubmit:
            return False
        self._state = "validating"
        self.stateChanged.emit()
        return True

    def mark_submitting(self) -> Path | None:
        if self._confirmed_path is None or not self._confirmed_path.is_file():
            return None
        self._state = "submitting"
        self.stateChanged.emit()
        return self._confirmed_path

    def discard(self, *, emit: bool = True) -> None:
        """Remove unconfirmed private media; no image paths are surfaced to QML."""
        for path in (self._source_path, self._confirmed_path):
            if path is None:
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self._source_path = None
        self._confirmed_path = None
        self._source_size = (0, 0)
        self._crop = None
        self._rotation = 0
        self._perspective_points = ()
        self._perspective_enabled = False
        self._auto_enhance = False
        self.warning_model.clear()
        self.source_store.clear()
        self.preview_store.clear()
        self.sourceRevisionChanged.emit()
        self.previewRevisionChanged.emit()
        self._state = "idle"
        if emit:
            self.stateChanged.emit()

    def _rotate(self, delta: int) -> None:
        if not self.hasCapturedImage:
            return
        self._rotation = (self._rotation + delta) % 360
        self._render_adjusted_preview()
        self.stateChanged.emit()

    def _crop_from_preview_zoom(self) -> CropRect | None:
        x, y, width, height = self._preview_zoom
        if width >= 0.999 and height >= 0.999:
            return None
        return crop_from_normalized(
            x,
            y,
            width,
            height,
            image_width=self._source_size[0],
            image_height=self._source_size[1],
        )

    def _detect_perspective_if_relevant(self) -> None:
        self._perspective_points = ()
        self._perspective_enabled = False
        if not self.hasCapturedImage or self._profile != "document":
            return
        try:
            points = detect_document_quadrilateral(self._source_path)
        except ReviewProcessingError:
            points = None
        if points is not None:
            self._perspective_points = points

    def _render_adjusted_preview(self) -> bool:
        if not self.hasCapturedImage or self._source_path is None:
            return False
        confirmed_path = self._source_path.with_name(f"review-{self._source_path.stem}.jpg")
        try:
            render_review_image(
                self._source_path,
                confirmed_path,
                ReviewAdjustments(
                    crop=self._crop,
                    rotation_degrees=self._rotation,
                    perspective_points=self._perspective_points,
                    perspective_enabled=self._perspective_enabled,
                    auto_enhance=self._auto_enhance,
                ),
            )
            self._confirmed_path = confirmed_path
            self.preview_store.set_path(confirmed_path)
            self.previewRevisionChanged.emit()
            warnings = assess_image_quality(
                confirmed_path,
                crop=self._crop,
                thresholds=self.runtime.settings.capture_review.quality_thresholds,
            )
            if self._profile == "document" and not self.perspectiveAvailable:
                warnings.append({"key": "document_edges", "title": "Document edges may be outside the frame", "message": "Use crop or move the camera so all page edges are visible.", "tone": "warning"})
            self.warning_model.set_items(warnings)
            self._quality_warning_text = "" if not warnings else "Review the image-quality notes before continuing."
            return True
        except (OSError, ReviewProcessingError, ValueError):
            self.warning_model.set_items([{"key": "adjustment", "title": "Adjustment preview unavailable", "message": "You can reset adjustments or retake the image.", "tone": "warning"}])
            self._quality_warning_text = "VisionDesk could not apply one of the selected adjustments."
            return False

    def _display_crop_value(self, name: str) -> float:
        width, height = self._source_size
        if self._crop is None or width <= 0 or height <= 0:
            return {"x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0}[name]
        values = {
            "x": self._crop.x / width,
            "y": self._crop.y / height,
            "width": self._crop.width / width,
            "height": self._crop.height / height,
        }
        return float(values[name])

    def _update_capability_model(self) -> None:
        capabilities = self._capabilities
        entries: list[dict[str, Any]] = []
        for key, label, supported in (
            ("autofocus", "Autofocus", capabilities.autofocus),
            ("autofocus_lock", "Autofocus lock", capabilities.autofocus_lock),
            ("manual_focus", "Manual focus", capabilities.manual_focus),
            ("auto_exposure", "Auto exposure", capabilities.auto_exposure),
            ("exposure_compensation", "Exposure adjustment", capabilities.exposure_compensation),
            ("manual_exposure", "Manual exposure", capabilities.manual_exposure),
        ):
            entries.append({"key": key, "label": label, "supported": bool(supported), "message": "Available for this camera" if supported else "Not supported by this camera"})
        self.capability_model.set_items(entries)
        self.capabilitiesChanged.emit()
