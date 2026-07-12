"""Qt frontend smoke tests for the native VisionDesk migration."""

from __future__ import annotations

import importlib.util
import threading
from pathlib import Path

import pytest

PY_SIDE6_AVAILABLE = importlib.util.find_spec("PySide6") is not None
pytestmark = pytest.mark.skipif(not PY_SIDE6_AVAILABLE, reason="PySide6 is not installed")

if PY_SIDE6_AVAILABLE:
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtTest import QSignalSpy
    from PySide6.QtWidgets import QApplication

    from qt_app.app_controller import AppController
    from qt_app.gpio_controller import GPIOController
    from qt_app.image_provider import CachedImageStore, VisionDeskImageProvider
    from qt_app.pipeline_controller import PipelineController
    from qt_app.runtime import RuntimePaths, VisionDeskRuntime


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def build_runtime(tmp_path: Path, *, setup_completed: bool) -> VisionDeskRuntime:
    """Create an isolated mock runtime that never touches repo data paths."""
    paths = RuntimePaths(
        ui_state_path=tmp_path / "ui_state.json",
        setup_state_path=tmp_path / "setup_state.json",
        health_status_path=tmp_path / "health_status.json",
        latest_result_path=tmp_path / "latest_result.txt",
        result_history_path=tmp_path / "result_history.json",
        private_data_path=tmp_path / "private",
        ui_preview_dir=tmp_path / "ui-previews",
        env_file_path=tmp_path / ".env",
    )
    runtime = VisionDeskRuntime(
        mock_hardware=True,
        paths=paths,
        purge_on_startup=False,
    )
    runtime.settings.setup.completed = setup_completed
    runtime.settings.setup.completed_at = "2026-07-12T12:00:00" if setup_completed else ""
    runtime.settings.setup.version = 1 if setup_completed else 0
    runtime.settings.config_path = tmp_path / "device.yaml"
    runtime.settings.retention.purge_on_startup = False
    return runtime


def test_app_controller_select_mode_opens_camera(qapp, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    controller = AppController(
        runtime,
        camera_store=CachedImageStore(),
        result_store=CachedImageStore(),
    )

    controller.selectMode("read_text")
    QTimer.singleShot(250, qapp.quit)
    qapp.exec()

    assert controller.selectedMode == "read_text"
    assert controller.currentScreen == "camera"
    assert controller.applicationState in {"CAMERA_PREPARING", "CAMERA_READY"}
    controller.shutdown()


def test_app_controller_reports_backend_busy_while_camera_screen_is_open(qapp, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    controller = AppController(
        runtime,
        camera_store=CachedImageStore(),
        result_store=CachedImageStore(),
    )

    controller.selectMode("read_text")

    assert controller.currentScreen == "camera"
    assert controller.isBackendBusy() is True
    controller.shutdown()


def test_pipeline_capture_lock_blocks_parallel_requests(qapp, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    controller = PipelineController(runtime, result_image_store=CachedImageStore())
    spy = QSignalSpy(controller.payloadReady)

    first_started = controller.start_capture(
        selected_mode="read_text",
        selected_mode_internal="document_reader",
    )
    second_started = controller.start_capture(
        selected_mode="read_text",
        selected_mode_internal="document_reader",
    )

    assert first_started is True
    assert second_started is False
    assert spy.wait(3000)
    assert len(spy) == 1
    controller.close()
    runtime.shutdown()


def test_qml_main_loads_with_mock_runtime(qapp, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
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

    assert engine.rootObjects()
    controller.shutdown()


def test_gpio_signal_delivery_reaches_qt_main_thread(qapp, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    controller = GPIOController(runtime, get_device_state=lambda: "READY")
    spy = QSignalSpy(controller.captureRequested)

    worker = threading.Thread(target=controller._emit_capture_requested, daemon=True)
    worker.start()
    worker.join(timeout=1.0)

    if len(spy) == 0:
        assert spy.wait(1000)
    assert len(spy) == 1
    controller.stop()
    runtime.shutdown()
