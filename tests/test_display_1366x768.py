"""Display, typography, and coordinate safety tests for the production panel."""

from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from config.settings import load_device_settings, update_device_config
from qt_app.display_integration import BODY_FONT_FALLBACK_ORDER, select_body_font_family
from vision.display_mapping import (
    DisplayRect,
    aspect_fit_rect,
    display_to_normalized,
    normalized_to_display,
    recenter_zoom_region,
)


def test_primary_reference_resolution_is_1366x768() -> None:
    config = yaml.safe_load(Path("config/device.yaml").read_text(encoding="utf-8"))
    metrics = Path("qt_app/qml/theme/DisplayMetrics.qml").read_text(encoding="utf-8")

    assert config["display"]["size"] == {"width": 1366, "height": 768}
    assert "referenceWidth: 1366" in metrics
    assert "referenceHeight: 768" in metrics


def test_active_ui_has_no_legacy_canvas_or_whole_tree_scale() -> None:
    active_paths = [
        Path("qt_app/qml/Main.qml"),
        Path("tools/capture_ui_screenshots.py"),
        Path("tools/ui_preview/AppScreensPreview.qml"),
        Path("tools/ui_preview/SetupWizardPreview.qml"),
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in active_paths)

    for legacy in ("designCanvas", "contentScale", "designWidth", "designHeight", "setWidth(1200)", "setHeight(800)"):
        assert legacy not in combined
    assert "scale:" not in Path("qt_app/qml/Main.qml").read_text(encoding="utf-8")
    assert "root.setWidth(1366)" in combined
    assert "root.setHeight(768)" in combined


def test_typography_and_touch_metrics_are_centralized() -> None:
    typography = Path("qt_app/qml/theme/Typography.qml").read_text(encoding="utf-8")
    metrics = Path("qt_app/qml/theme/DisplayMetrics.qml").read_text(encoding="utf-8")
    app_text = Path("qt_app/qml/components/AppText.qml").read_text(encoding="utf-8")
    button = Path("qt_app/qml/components/PrimaryButton.qml").read_text(encoding="utf-8")

    for role in ("brand", "pageTitle", "sectionTitle", "cardTitle", "body", "secondaryBody", "button", "status", "resultContent", "caption", "technicalMetadata"):
        assert f"property int {role}" in typography
    assert "minimumTouchTarget: 48" in metrics
    assert "font.hintingPreference: root.theme.hintingPreference" in app_text
    assert "renderType: root.forceQtRendering ? Text.QtRendering : root.theme.textRenderType" in app_text
    assert "implicitHeight: root.theme.controlHeight" in button


def test_body_font_fallback_order_and_installer_support() -> None:
    installer = Path("install.sh").read_text(encoding="utf-8")

    assert BODY_FONT_FALLBACK_ORDER == ("Noto Sans", "Inter", "DejaVu Sans", "Roboto")
    assert "fonts-noto-core" in installer
    assert "fontconfig" in installer
    assert "fc-match" in installer
    assert select_body_font_family(["Arial", "DejaVu Sans", "Roboto"], default="system") == "DejaVu Sans"
    assert select_body_font_family(["Arial"], default="system") == "system"


def test_text_size_setting_persists_without_scaling_the_ui(tmp_path: Path) -> None:
    config_path = tmp_path / "device.yaml"
    config_path.write_text(Path("config/device.yaml").read_text(encoding="utf-8"), encoding="utf-8")

    update_device_config({"display": {"text_size": "extra_large"}}, config_path=config_path, env={})
    settings = load_device_settings(config_path=config_path, env={})

    assert settings.display.text_size == "extra_large"
    theme = Path("qt_app/qml/theme/Typography.qml").read_text(encoding="utf-8")
    assert 'textSize === "extra_large" ? 1.30' in theme
    assert "scale:" not in Path("qt_app/qml/Main.qml").read_text(encoding="utf-8")


def test_aspect_fit_mapping_handles_letterboxing_and_round_trip() -> None:
    container = DisplayRect(20, 40, 900, 500)
    painted = aspect_fit_rect(container, 1920, 1080)

    assert painted.width == pytest.approx(888.8889)
    assert painted.height == pytest.approx(500)
    assert painted.x > container.x
    normalized = display_to_normalized(painted.x + painted.width * 0.25, painted.y + painted.height * 0.75, painted)
    assert normalized == pytest.approx((0.25, 0.75))
    display = normalized_to_display(*normalized, painted)
    assert display == pytest.approx((painted.x + painted.width * 0.25, painted.y + painted.height * 0.75))


def test_aspect_fit_mapping_handles_pillarboxing_and_clamps_input() -> None:
    painted = aspect_fit_rect(DisplayRect(0, 0, 700, 520), 600, 1000)

    assert painted.height == 520
    assert painted.width == 312
    assert painted.x == 194
    assert display_to_normalized(-50, 9999, painted) == (0.0, 1.0)


def test_zoom_region_mapping_uses_current_source_region() -> None:
    painted = DisplayRect(100, 60, 800, 450)
    region = DisplayRect(0.20, 0.10, 0.50, 0.50)

    moved = recenter_zoom_region(700, 285, painted, region)

    assert (moved.x, moved.y, moved.width, moved.height) == pytest.approx((0.325, 0.1, 0.5, 0.5))


def test_camera_and_review_qml_use_actual_painted_image_bounds() -> None:
    camera = Path("qt_app/qml/screens/CameraScreen.qml").read_text(encoding="utf-8")
    review = Path("qt_app/qml/components/ReviewImageCanvas.qml").read_text(encoding="utf-8")

    for source in (camera, review):
        assert "paintedWidth" in source
        assert "paintedHeight" in source
        assert "Image.PreserveAspectFit" in source
    assert "normalizedPaintedX" in camera
    assert "previewZoomX" in camera
    assert "containsImagePoint" in review
    assert "perspectivePoints" in review


def test_all_major_screens_reserve_a_non_overlapping_footer_or_scroll() -> None:
    screen_names = ("CameraScreen", "ReviewScreen", "ResultScreen", "HistoryScreen", "HistoryDetailScreen", "ErrorScreen", "SettingsScreen", "DeviceHealthScreen")
    for name in screen_names:
        source = Path(f"qt_app/qml/screens/{name}.qml").read_text(encoding="utf-8")
        assert "Layout.preferredHeight: root.theme.footerHeight" in source
    setup = Path("qt_app/qml/screens/SetupScreen.qml").read_text(encoding="utf-8")
    assert "root.theme.footerHeight + root.theme.pageSpacing * 2" in setup
