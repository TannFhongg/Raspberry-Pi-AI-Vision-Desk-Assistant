"""Render the native Qt/QML screens with mock data and save review screenshots.

Run from the repository root:
    .venv\\Scripts\\python.exe tools\\capture_ui_screenshots.py
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import sys
import tempfile

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

# Must be set before importing Qt so the tool is safe on a CI machine without
# a desktop session. A visible window is not required for QQuickWindow.grabWindow.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image, ImageDraw, ImageFont
from PySide6.QtCore import QEventLoop, QObject, QTimer, QUrl
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from qt_app.app_controller import AppController
from qt_app.image_provider import CachedImageStore, VisionDeskImageProvider
from qt_app.mock_backend import build_mock_preview_bytes
from qt_app.runtime import RuntimePaths, VisionDeskRuntime
from camera.capabilities import CameraCapabilities
from system.error_mapping import map_public_error

SCREEN_ORDER = (
    "01-setup",
    "01a-setup-running",
    "01b-setup-results",
    "01c-setup-scrolled",
    "02-ready-header",
    "03-wifi-unavailable-header",
    "04-device-health",
    "05-camera-document-guide",
    "06-camera-computer-screen",
    "07-review-and-adjust",
    "08-crop-active",
    "09-perspective-correction-preview",
    "10-image-quality-warning",
    "11-unsupported-camera-control",
    "12-processing",
    "13-result",
    "14-history",
    "15-history-detail",
    "16-error",
)
LEGACY_SCREENSHOT_NAMES = ("01b-setup-scrolled",)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Capture VisionDesk Qt/QML review screenshots.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("debug/ui-screenshots"),
        help="Directory for PNG screenshots (default: debug/ui-screenshots).",
    )
    return parser.parse_args()


def _wait(milliseconds: int = 180) -> None:
    """Let Qt create the requested Loader item before grabbing the window."""
    loop = QEventLoop()
    QTimer.singleShot(milliseconds, loop.quit)
    loop.exec()


def _build_runtime(workspace: Path) -> VisionDeskRuntime:
    config_template = Path("config/device.yaml")
    config_path = workspace / "device.yaml"
    shutil.copyfile(config_template, config_path)
    app_root = workspace / "app_root"
    (app_root / "config").mkdir(parents=True)
    shutil.copyfile(config_template, app_root / "config" / "device.yaml")
    paths = RuntimePaths(
        path_mode="development",
        repo_root=workspace,
        releases_dir=workspace / "releases",
        setup_state_path=workspace / "setup_state.json",
        health_status_path=workspace / "health_status.json",
        latest_result_path=workspace / "latest_result.txt",
        result_history_path=workspace / "result_history.json",
        private_data_path=workspace / "private",
        env_file_path=workspace / ".env",
        config_path=config_path,
        logs_dir=workspace / "logs",
        app_root=app_root,
    )
    runtime = VisionDeskRuntime(mock_hardware=True, paths=paths, purge_on_startup=False)
    runtime.settings.setup.completed = False
    runtime.settings.setup.completed_at = ""
    runtime.settings.setup.version = 0
    runtime.settings.retention.purge_on_startup = False
    return runtime


def _completed_setup_check_fixture() -> list[dict[str, object]]:
    """Return explicit mock results for the completed-check documentation shot."""
    return [
        {
            "name": name,
            "status": "pass",
            "message": "Ready for first boot.",
            "required": True,
        }
        for name in ("config", "storage", "display", "network", "camera", "gpio")
    ]


def _save_window(root, destination: Path) -> None:
    image = root.grabWindow()
    if image.isNull():
        raise RuntimeError(f"Could not capture {destination.name}.")
    # Software-rendered Flickables can expose transparent pixels between
    # frames. Composite against the app background for stable opaque PNGs.
    opaque = QImage(image.size(), QImage.Format.Format_ARGB32_Premultiplied)
    opaque.fill(QColor("#F6F8FB"))
    painter = QPainter(opaque)
    painter.drawImage(0, 0, image)
    painter.end()
    if not opaque.save(str(destination), "PNG"):
        raise RuntimeError(f"Could not capture {destination.name}.")


def _repair_scroll_capture_artifact(destination: Path) -> None:
    """Replace only large software-renderer black holes in a scrolled capture."""
    image = Image.open(destination).convert("RGB")
    width, height = image.size
    pixels = image.load()
    visited = bytearray(width * height)
    fill_color = (246, 248, 251)
    for start_y in range(height):
        for start_x in range(width):
            start = start_y * width + start_x
            if visited[start] or max(pixels[start_x, start_y]) > 4:
                continue
            queue = [start]
            visited[start] = 1
            component: list[int] = []
            while queue:
                current = queue.pop()
                component.append(current)
                x, y = current % width, current // width
                for neighbor_x, neighbor_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if neighbor_x < 0 or neighbor_y < 0 or neighbor_x >= width or neighbor_y >= height:
                        continue
                    neighbor = neighbor_y * width + neighbor_x
                    if visited[neighbor] or max(pixels[neighbor_x, neighbor_y]) > 4:
                        continue
                    visited[neighbor] = 1
                    queue.append(neighbor)
            if len(component) >= 4000:
                for current in component:
                    pixels[current % width, current // width] = fill_color
    image.save(destination, "PNG")


def _write_contact_sheet(output_dir: Path) -> None:
    source_images = [output_dir / f"{name}.png" for name in SCREEN_ORDER]
    thumbnail_size = (480, 320)
    label_height = 34
    rows = (len(source_images) + 1) // 2
    canvas = Image.new("RGB", (thumbnail_size[0] * 2, (thumbnail_size[1] + label_height) * rows), "#eef3fa")
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()
    for index, source in enumerate(source_images):
        screenshot = Image.open(source).convert("RGB")
        screenshot.thumbnail(thumbnail_size)
        column = index % 2
        row = index // 2
        x = column * thumbnail_size[0]
        y = row * (thumbnail_size[1] + label_height)
        canvas.paste(screenshot, (x, y))
        draw.text((x + 12, y + thumbnail_size[1] + 10), source.stem[3:].replace("-", " ").title(), fill="#17233a", font=font)
    canvas.save(output_dir / "00-contact-sheet.png", "PNG")


def main() -> int:
    args = _parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    # Preserve any legacy or hand-curated documentation captures in this
    # shared directory; regenerate only this script's named portfolio set.
    for name in (*SCREEN_ORDER, *LEGACY_SCREENSHOT_NAMES, "00-contact-sheet"):
        stale_image = output_dir / f"{name}.png"
        if stale_image.exists():
            stale_image.unlink()

    QQuickStyle.setStyle("Basic")
    app = QApplication.instance() or QApplication(sys.argv)
    runtime_workspace = Path(tempfile.mkdtemp(prefix="visiondesk-ui-capture-"))
    runtime = _build_runtime(runtime_workspace)
    camera_store = CachedImageStore()
    result_store = CachedImageStore()
    review_source_store = CachedImageStore()
    review_preview_store = CachedImageStore()
    controller = AppController(
        runtime,
        camera_store=camera_store,
        result_store=result_store,
        review_source_store=review_source_store,
        review_preview_store=review_preview_store,
    )
    engine = QQmlApplicationEngine()
    engine.addImageProvider(
        "visiondesk",
        VisionDeskImageProvider(
            camera_store=camera_store,
            result_store=result_store,
            review_source_store=review_source_store,
            review_preview_store=review_preview_store,
        ),
    )
    engine.rootContext().setContextProperty("appController", controller)
    engine.load(QUrl.fromLocalFile(str((Path("qt_app/qml/Main.qml")).resolve())))
    if not engine.rootObjects():
        controller.shutdown()
        raise RuntimeError("Could not load qt_app/qml/Main.qml.")
    root = engine.rootObjects()[0]
    root.setWidth(1200)
    root.setHeight(800)
    root.show()
    # The setup wizard's ScrollView needs one full render cycle after its
    # Loader resolves on the software/offscreen backend.  Capturing sooner
    # can produce transparent tiles even though the live kiosk layout is
    # correct.
    _wait(1000)

    def capture(name: str) -> None:
        # Let dynamic QML rows (especially the review capability model) finish
        # a second software-rendered frame before grabbing.
        _wait(700)
        destination = output_dir / f"{name}.png"
        _save_window(root, destination)
        if name == "01c-setup-scrolled":
            _repair_scroll_capture_artifact(destination)

    def recreate_review_screen() -> None:
        """Settle a fresh Review Loader frame on the Qt offscreen backend."""
        controller._set_screen("processing", "ANALYZING", "Preparing review example")
        _wait(250)
        controller._set_screen("review", "REVIEWING", "Review the captured image")
        _wait(1200)

    try:
        capture("01-setup")

        # Render the explicit states shown by the Welcome screen without
        # invoking host diagnostics. The initial screen intentionally has no
        # check rows; the running view has one compact indicator; the result
        # view uses only concrete mock results.
        running_store = controller.setup_controller._begin_action("device_checks")
        if running_store is None:
            raise RuntimeError("Could not prepare the device-check running screenshot.")
        running_store.write_state(
            {
                "current_step": "welcome",
                "steps": {
                    "welcome": {
                        "status": "running",
                        "message": "Running device checks…",
                        "checks": [],
                    }
                },
            }
        )
        controller.setup_controller.refresh_state()
        capture("01a-setup-running")

        running_store.write_device_checks(_completed_setup_check_fixture())
        controller.setup_controller._complete_action("device_checks")
        controller.setup_controller.refresh_state()
        capture("01b-setup-results")

        setup_scroll = root.findChild(QObject, "setupBodyFlickable")
        if setup_scroll is not None:
            content_height = float(setup_scroll.property("contentHeight") or 0)
            viewport_height = float(setup_scroll.property("height") or 0)
            setup_scroll.setProperty("contentY", max(0.0, content_height - viewport_height))
            _wait()
        capture("01c-setup-scrolled")

        setup_state = runtime.setup_state_store.load_state()
        setup_state["setup_complete"] = True
        setup_state["completed_at"] = runtime.timestamp()
        runtime.setup_state_store.write_state(setup_state)
        runtime.settings.setup.completed = True

        controller._set_screen("home", "READY", "VisionDesk is ready.")
        controller.health_controller.refresh()
        capture("02-ready-header")

        controller.health_controller._summary["global_status"] = {"text": "Wi-Fi unavailable", "tone": "warning"}
        controller.viewStateChanged.emit()
        capture("03-wifi-unavailable-header")
        controller.health_controller.refresh()

        controller.openSettings()
        controller.openDeviceHealth()
        capture("04-device-health")

        controller.selectMode("read_text")
        capture("05-camera-document-guide")
        controller.captureReview.setCaptureProfile("computer_screen")
        capture("06-camera-computer-screen")
        controller.captureReview.setCaptureProfile("document")
        controller.capture()
        _wait(500)
        recreate_review_screen()
        capture("07-review-and-adjust")
        controller.captureReview.setCropNormalized(0.12, 0.12, 0.70, 0.70)
        capture("08-crop-active")
        controller.captureReview._perspective_points = ((180.0, 130.0), (1500.0, 120.0), (1510.0, 880.0), (170.0, 900.0))
        # Present a detected boundary awaiting user acceptance. This remains
        # truthful even on a development machine without OpenCV, where an
        # accepted warp is deliberately unavailable rather than faked.
        controller.captureReview._perspective_enabled = False
        controller.captureReview.stateChanged.emit()
        recreate_review_screen()
        capture("09-perspective-correction-preview")
        # Representative mock image-quality fixture for documentation. The
        # application itself derives these messages from non-destructive image
        # checks; this makes the portfolio screenshot deterministic.
        controller.captureReview.warning_model.set_items(
            [
                {
                    "key": "glare",
                    "title": "Strong glare detected",
                    "message": "Retake at a different angle or continue anyway.",
                    "tone": "warning",
                },
                {
                    "key": "blur",
                    "title": "Image may be blurry",
                    "message": "Move closer or use a smaller crop.",
                    "tone": "warning",
                },
            ]
        )
        controller.captureReview._quality_warning_text = "Strong glare and possible blur were detected. Retake, adjust the crop, or continue anyway."
        controller.captureReview.stateChanged.emit()
        capture("10-image-quality-warning")
        # Change the mock capability model while Review is unloaded. This
        # avoids a Qt offscreen-only stale-frame issue and mirrors a fresh
        # camera/session entering review on a different device.
        controller._set_screen("processing", "ANALYZING", "Preparing capability example")
        _wait(250)
        controller.captureReview._capabilities = CameraCapabilities(available=True, message="Mock unsupported-controls fixture")
        controller.captureReview._update_capability_model()
        controller.captureReview.stateChanged.emit()
        controller._set_screen("review", "REVIEWING", "Review the captured image")
        _wait(1200)
        capture("11-unsupported-camera-control")

        controller.pipeline_controller._set_progress(
            progress_state="ANALYZING",
            progress_message="Sending image to OpenAI Vision...",
            progress_error_step=-1,
        )
        controller._refresh_processing_view()
        controller._set_screen("processing", "ANALYZING", controller.processingStatusMessage)
        capture("12-processing")

        result_store.set_bytes(
            build_mock_preview_bytes(
                title="Processed document",
                subtitle="Mock preview for UI review",
            )
        )
        controller._present_result(
            status="Answer Ready",
            answer_text=(
                "The document is a meeting summary.\n\n"
                "• Main action: confirm the delivery timeline.\n"
                "• Owner: Operations team.\n"
                "• Due date: Friday."
            ),
            error_text="",
            history_entry=None,
            application_state="DONE",
        )
        capture("13-result")

        history_entry = {
            "id": "ui-review-entry-001",
            "created_at": "2026-07-14 10:30",
            "selected_mode": "read_text",
            "mode_label": "Read Text",
            "summary": "Meeting summary and action items extracted.",
            "answer": "The document is a meeting summary with one delivery action due Friday.",
            "status": "success",
            "model_used": "gpt-5.4-mini",
            "duration_seconds": 2.8,
            "retry_status": "",
            "error_summary": "",
        }
        controller.history_controller._apply_snapshot({"status": "ok", "entries": [history_entry]})
        controller._set_screen("history", "HISTORY", "Recent saved results")
        capture("14-history")

        controller.history_controller._select_entry(history_entry)
        controller._set_screen("history_detail", "HISTORY_DETAIL", "Viewing saved result")
        capture("15-history-detail")

        controller._present_public_error(map_public_error("network connection is offline", retryable=True))
        capture("16-error")
    finally:
        root.close()
        controller.shutdown()
        runtime.shutdown()
        shutil.rmtree(runtime_workspace, ignore_errors=True)

    _write_contact_sheet(output_dir)
    print(f"Saved {len(SCREEN_ORDER)} UI screenshots and a contact sheet to {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
