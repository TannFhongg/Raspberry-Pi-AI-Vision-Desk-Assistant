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
from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from qt_app.app_controller import AppController
from qt_app.image_provider import CachedImageStore, VisionDeskImageProvider
from qt_app.mock_backend import build_mock_preview_bytes
from qt_app.runtime import RuntimePaths, VisionDeskRuntime
from system.error_mapping import map_public_error

SCREEN_ORDER = (
    "01-setup",
    "02-home",
    "03-camera",
    "04-processing",
    "05-result",
    "06-history",
    "07-history-detail",
    "08-error",
)


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
    runtime.setup_state_store.write_state(
        {
            "current_step": "welcome",
            "steps": {
                "welcome": {
                    "status": "pass",
                    "message": "Device checks are ready for review.",
                    "checks": [
                        {
                            "name": name,
                            "status": "pass",
                            "message": "Ready for first boot.",
                            "required": True,
                        }
                        for name in ("config", "storage", "display", "network", "camera", "gpio")
                    ],
                }
            },
            "wifi": {
                "scan_status": "pass",
                "available_networks": [{"ssid": "Office", "signal": 82, "security": "WPA2"}],
                "message": "Found 1 Wi-Fi network.",
            },
        }
    )
    return runtime


def _save_window(root, destination: Path) -> None:
    image = root.grabWindow()
    if image.isNull() or not image.save(str(destination), "PNG"):
        raise RuntimeError(f"Could not capture {destination.name}.")


def _write_contact_sheet(output_dir: Path) -> None:
    source_images = [output_dir / f"{name}.png" for name in SCREEN_ORDER]
    thumbnail_size = (480, 320)
    label_height = 34
    canvas = Image.new("RGB", (thumbnail_size[0] * 2, (thumbnail_size[1] + label_height) * 4), "#eef3fa")
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
    for stale_image in output_dir.glob("*.png"):
        stale_image.unlink()

    QQuickStyle.setStyle("Basic")
    app = QApplication.instance() or QApplication(sys.argv)
    runtime_workspace = Path(tempfile.mkdtemp(prefix="visiondesk-ui-capture-"))
    runtime = _build_runtime(runtime_workspace)
    camera_store = CachedImageStore()
    result_store = CachedImageStore()
    controller = AppController(runtime, camera_store=camera_store, result_store=result_store)
    engine = QQmlApplicationEngine()
    engine.addImageProvider(
        "visiondesk",
        VisionDeskImageProvider(camera_store=camera_store, result_store=result_store),
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
    _wait()

    def capture(name: str) -> None:
        _wait()
        _save_window(root, output_dir / f"{name}.png")

    try:
        capture("01-setup")

        controller._set_screen("home", "READY", "VisionDesk is ready.")
        capture("02-home")

        controller.selectMode("read_text")
        capture("03-camera")

        controller.pipeline_controller._set_progress(
            progress_state="ANALYZING",
            progress_message="Sending image to OpenAI Vision...",
            progress_error_step=-1,
        )
        controller._refresh_processing_view()
        controller._set_screen("processing", "ANALYZING", controller.processingStatusMessage)
        capture("04-processing")

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
        capture("05-result")

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
        capture("06-history")

        controller.history_controller._select_entry(history_entry)
        controller._set_screen("history_detail", "HISTORY_DETAIL", "Viewing saved result")
        capture("07-history-detail")

        controller._present_public_error(map_public_error("network connection is offline", retryable=True))
        capture("08-error")
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
