"""Tests for review geometry, safeguards, and non-destructive quality checks."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from camera.capabilities import detect_camera_capabilities
from vision.review_processing import (
    CropRect,
    ReviewAdjustments,
    ReviewProcessingError,
    assess_image_quality,
    clamp_crop,
    crop_from_normalized,
    crop_to_rotated,
    detect_document_quadrilateral,
    render_review_image,
)


def test_crop_coordinate_conversion_round_trips_between_rotation_spaces() -> None:
    original = crop_from_normalized(
        0.20,
        0.10,
        0.40,
        0.50,
        image_width=1000,
        image_height=600,
        rotation_degrees=90,
    )

    assert original == CropRect(x=100, y=240, width=500, height=240)
    displayed = crop_to_rotated(original, 1000, 600, 90)
    assert displayed == CropRect(x=120, y=100, width=240, height=500)


def test_crop_bounds_enforce_minimum_size_inside_original_image() -> None:
    bounded = clamp_crop(CropRect(x=-9, y=90, width=2, height=2), 100, 100, minimum_size=20)

    assert bounded == CropRect(x=0, y=80, width=20, height=20)


def test_review_render_uses_crop_then_rotation_without_stretching(tmp_path: Path) -> None:
    source = tmp_path / "source.jpg"
    confirmed = tmp_path / "confirmed.jpg"
    Image.new("RGB", (400, 200), "#3b82f6").save(source)

    render_review_image(
        source,
        confirmed,
        ReviewAdjustments(crop=CropRect(100, 20, 200, 100), rotation_degrees=90),
    )

    with Image.open(confirmed) as image:
        assert image.size == (100, 200)


def test_quality_heuristics_warn_for_dark_bright_and_small_crop(tmp_path: Path) -> None:
    dark = tmp_path / "dark.jpg"
    Image.new("RGB", (240, 160), "#050505").save(dark)

    warnings = assess_image_quality(dark, crop=CropRect(0, 0, 5, 5))
    keys = {warning["key"] for warning in warnings}

    assert "dark" in keys
    assert "small_crop" in keys


def test_perspective_detection_falls_back_safely_without_opencv(monkeypatch, tmp_path: Path) -> None:
    image = tmp_path / "document.jpg"
    Image.new("RGB", (300, 200), "white").save(image)

    monkeypatch.setattr(
        "vision.review_processing._import_cv2",
        lambda: (_ for _ in ()).throw(ReviewProcessingError("OpenCV unavailable")),
    )

    assert detect_document_quadrilateral(image) is None


def test_mock_capabilities_are_explicit_and_do_not_claim_manual_controls() -> None:
    class Settings:
        class Camera:
            backend = "opencv"
            index = 0

        camera = Camera()

    capabilities = detect_camera_capabilities(Settings(), mock_hardware=True)

    assert capabilities.autofocus is True
    assert capabilities.auto_exposure is True
    assert capabilities.manual_focus is False
    assert capabilities.manual_exposure is False
