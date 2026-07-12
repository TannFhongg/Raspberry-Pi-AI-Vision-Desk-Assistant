"""Qt frontend tests for the native VisionDesk workflow."""

from __future__ import annotations

import importlib.util
import json
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

    from pipeline.runner import PipelineResult
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
    config_template = Path("config/device.yaml").read_text(encoding="utf-8")
    config_path = tmp_path / "device.yaml"
    config_path.write_text(config_template, encoding="utf-8")
    app_root = tmp_path / "app_root"
    (app_root / "config").mkdir(parents=True, exist_ok=True)
    (app_root / "config" / "device.yaml").write_text(config_template, encoding="utf-8")
    paths = RuntimePaths(
        path_mode="development",
        repo_root=tmp_path,
        releases_dir=tmp_path / "releases",
        setup_state_path=tmp_path / "setup_state.json",
        health_status_path=tmp_path / "health_status.json",
        latest_result_path=tmp_path / "latest_result.txt",
        result_history_path=tmp_path / "result_history.json",
        private_data_path=tmp_path / "private",
        env_file_path=tmp_path / ".env",
        config_path=config_path,
        logs_dir=tmp_path / "logs",
        app_root=app_root,
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
    if setup_completed:
        runtime.setup_state_store.write_state(
            {
                "setup_complete": True,
                "completed_at": "2026-07-12T12:00:00",
                "app_version": runtime.app_version,
                "current_step": "finish",
                "wifi": {
                    "connect_status": "pass",
                    "ssid": "Office",
                    "connection_name": "Office",
                    "message": "Connected.",
                },
                "openai": {
                    "status": "pass",
                    "key_present": True,
                    "api_key_verified": True,
                    "message": "Configured.",
                },
                "camera": {
                    "status": "pass",
                    "message": "Camera ready.",
                },
                "gpio": {
                    "status": "pass",
                    "message": "GPIO ready.",
                    "required": runtime.build_setup_gpio_requirements(),
                    "pressed_labels": [item["label"] for item in runtime.build_setup_gpio_requirements()],
                    "all_pressed": True,
                },
            }
        )
    return runtime


def append_history_entry(
    runtime: VisionDeskRuntime,
    *,
    answer: str,
    selected_mode: str = "read_text",
    selected_mode_internal: str = "document_reader",
    status: str = "success",
    model_used: str = "gpt-5.4-mini",
    duration_seconds: float = 1.25,
    retry_status: str = "",
    error_summary: str = "",
) -> dict[str, object]:
    """Persist one deterministic saved result in the shared history store."""
    result = PipelineResult(
        captured_path=None,
        processed_path=None,
        answer=answer,
        mode=selected_mode_internal,
        camera_backend_used="opencv",
        camera_resolution=(1920, 1080),
        status=status,
        model_used=model_used,
        duration_seconds=duration_seconds,
        retry_status=retry_status,
        error_summary=error_summary,
    )
    entry = runtime.result_history_store.append_result(
        result,
        selected_mode,
        selected_mode_internal,
    )
    assert entry is not None
    return entry


def build_controller(tmp_path: Path, *, setup_completed: bool = True) -> tuple[VisionDeskRuntime, AppController]:
    """Create an app controller with isolated cached image stores."""
    runtime = build_runtime(tmp_path, setup_completed=setup_completed)
    controller = AppController(
        runtime,
        camera_store=CachedImageStore(),
        result_store=CachedImageStore(),
    )
    return runtime, controller


def test_app_controller_select_mode_opens_camera(qapp, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)

    controller.selectMode("read_text")
    QTimer.singleShot(250, qapp.quit)
    qapp.exec()

    assert controller.selectedMode == "read_text"
    assert controller.currentScreen == "camera"
    assert controller.applicationState in {"CAMERA_PREPARING", "CAMERA_READY"}
    controller.shutdown()


def test_incomplete_setup_routes_to_setup_screen(qapp, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path, setup_completed=False)

    assert controller.currentScreen == "setup"
    assert controller.applicationState == "SETUP_REQUIRED"
    controller.shutdown()


def test_completed_setup_routes_home_from_authoritative_state(qapp, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path, setup_completed=True)

    assert controller.currentScreen == "home"
    assert controller.applicationState == "READY"
    controller.shutdown()


def test_corrupt_setup_state_routes_to_setup_and_quarantines_file(qapp, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=False)
    runtime.paths.setup_state_path.write_text("{not-json", encoding="utf-8")
    controller = AppController(
        runtime,
        camera_store=CachedImageStore(),
        result_store=CachedImageStore(),
    )

    assert controller.currentScreen == "setup"
    quarantined_files = list(runtime.paths.private_quarantine_path.glob("setup_state-*-invalid-setup-state.json"))
    assert quarantined_files
    controller.shutdown()


def test_app_controller_reports_backend_busy_while_camera_screen_is_open(qapp, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)

    controller.selectMode("read_text")

    assert controller.currentScreen == "camera"
    assert controller.isBackendBusy() is True
    controller.shutdown()


def test_pipeline_capture_lock_blocks_parallel_requests(qapp, qtbot, tmp_path) -> None:
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
    qtbot.waitUntil(lambda: spy.count() == 1, timeout=3000)
    assert spy.count() == 1
    controller.close()
    runtime.shutdown()


def test_qml_main_loads_with_mock_runtime(qapp, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)
    camera_store = controller._camera_store
    result_store = controller._result_store
    engine = QQmlApplicationEngine()
    engine.addImageProvider(
        "visiondesk",
        VisionDeskImageProvider(camera_store=camera_store, result_store=result_store),
    )
    engine.rootContext().setContextProperty("appController", controller)

    engine.load(QUrl.fromLocalFile(str((Path("qt_app/qml/Main.qml")).resolve())))

    assert engine.rootObjects()
    controller.shutdown()


def test_gpio_signal_delivery_reaches_qt_main_thread(qapp, qtbot, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    controller = GPIOController(runtime, get_device_state=lambda: "READY")
    spy = QSignalSpy(controller.captureRequested)

    worker = threading.Thread(target=controller._emit_capture_requested, daemon=True)
    worker.start()
    worker.join(timeout=1.0)

    qtbot.waitUntil(lambda: spy.count() == 1, timeout=1000)
    assert spy.count() == 1
    controller.stop()
    runtime.shutdown()


def test_history_navigation_detail_and_newest_first(qapp, qtbot, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)
    older_entry = append_history_entry(runtime, answer="Older result body.")
    newer_entry = append_history_entry(
        runtime,
        answer="Latest <script>alert(1)</script> **answer**",
        model_used="gpt-5.4-nano",
        duration_seconds=2.5,
    )

    controller.openHistory()

    qtbot.waitUntil(
        lambda: controller.currentScreen == "history"
        and controller.historyEntriesModel.count == 2
        and controller.historyState == "ready",
        timeout=3000,
    )

    newest_item = controller.historyEntriesModel.get(0)
    older_item = controller.historyEntriesModel.get(1)
    assert newest_item["id"] == newer_entry["id"]
    assert older_item["id"] == older_entry["id"]

    controller.openHistoryItem(str(newest_item["id"]))

    qtbot.waitUntil(lambda: controller.currentScreen == "history_detail", timeout=1000)
    assert controller.selectedHistoryId == newer_entry["id"]
    assert controller.selectedHistoryModeLabel == newer_entry["mode_label"]
    assert "<script>" not in controller.selectedHistoryResultHtml
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in controller.selectedHistoryResultHtml

    controller.goBack()
    qtbot.waitUntil(lambda: controller.currentScreen == "history", timeout=1000)
    controller.goBack()
    qtbot.waitUntil(lambda: controller.currentScreen == "home", timeout=1000)
    controller.shutdown()


def test_history_empty_state(qapp, qtbot, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)

    controller.openHistory()

    qtbot.waitUntil(
        lambda: controller.currentScreen == "history" and controller.historyState == "empty",
        timeout=3000,
    )
    assert controller.historyEntriesModel.count == 0
    assert "No saved results yet" in controller.historyMessage
    controller.shutdown()


def test_history_corruption_recovery_state(qapp, qtbot, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    runtime.paths.result_history_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.paths.result_history_path.write_text("{not-json", encoding="utf-8")
    controller = AppController(
        runtime,
        camera_store=CachedImageStore(),
        result_store=CachedImageStore(),
    )

    controller.openHistory()

    qtbot.waitUntil(
        lambda: controller.currentScreen == "history" and controller.historyState == "recovered",
        timeout=3000,
    )
    assert controller.historyEntriesModel.count == 0
    quarantined_files = list(runtime.paths.private_quarantine_path.glob("result_history-*-invalid-history-json.json"))
    assert quarantined_files
    controller.shutdown()


def test_delete_one_history_item(qapp, qtbot, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)
    first_entry = append_history_entry(runtime, answer="First result.")
    second_entry = append_history_entry(runtime, answer="Second result.")

    controller.openHistory()
    qtbot.waitUntil(lambda: controller.historyEntriesModel.count == 2, timeout=3000)

    controller.deleteHistoryItem(first_entry["id"])

    qtbot.waitUntil(
        lambda: controller.historyEntriesModel.count == 1 and controller.historyState == "ready",
        timeout=3000,
    )
    remaining_item = controller.historyEntriesModel.get(0)
    assert remaining_item["id"] == second_entry["id"]
    controller.shutdown()


def test_clear_history(qapp, qtbot, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)
    append_history_entry(runtime, answer="Result to clear.")

    controller.openHistory()
    qtbot.waitUntil(lambda: controller.historyEntriesModel.count == 1, timeout=3000)

    controller.clearHistory()

    qtbot.waitUntil(lambda: controller.historyState == "empty", timeout=3000)
    assert controller.historyEntriesModel.count == 0
    persisted_payload = json.loads(runtime.paths.result_history_path.read_text(encoding="utf-8"))
    assert persisted_payload == []
    controller.shutdown()


def test_delete_all_data_resets_runtime_artifacts_and_returns_home(qapp, qtbot, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)
    append_history_entry(runtime, answer="Stored result.")
    runtime.paths.latest_result_path.write_text("latest result", encoding="utf-8")
    runtime.setup_state_store.write_state({"current_step": "openai"})
    runtime.paths.private_current_path.mkdir(parents=True, exist_ok=True)
    (runtime.paths.private_current_path / "capture.jpg").write_text("capture", encoding="utf-8")
    runtime.paths.private_retry_path.mkdir(parents=True, exist_ok=True)
    (runtime.paths.private_retry_path / "queued.txt").write_text("retry", encoding="utf-8")
    runtime.paths.offline_retry_queue_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.paths.offline_retry_queue_path.write_text("[]", encoding="utf-8")
    runtime.paths.private_quarantine_path.mkdir(parents=True, exist_ok=True)
    (runtime.paths.private_quarantine_path / "leftover.txt").write_text("trash", encoding="utf-8")

    controller.selectMode("read_text")
    qtbot.waitUntil(lambda: controller.currentScreen == "camera", timeout=1000)

    controller.deleteAllData()

    qtbot.waitUntil(
        lambda: controller.currentScreen == "home"
        and controller.selectedMode == ""
        and controller.historyEntriesModel.count == 0,
        timeout=3000,
    )
    assert "All local data deleted" in controller.displayStatus
    assert not runtime.paths.latest_result_path.exists()
    assert runtime.paths.setup_state_path.exists()
    assert not runtime.paths.offline_retry_queue_path.exists()
    assert not runtime.paths.private_current_path.exists()
    assert not runtime.paths.private_retry_path.exists()
    assert list(runtime.paths.private_quarantine_path.iterdir()) == []
    controller.shutdown()


def test_history_qml_payload_hides_sensitive_fields(qapp, qtbot, tmp_path) -> None:
    runtime = build_runtime(tmp_path, setup_completed=True)
    runtime.paths.result_history_path.parent.mkdir(parents=True, exist_ok=True)
    runtime.paths.result_history_path.write_text(
        json.dumps(
            [
                {
                    "id": "entry-1",
                    "created_at": "2026-07-12T10:00:00",
                    "selected_mode": "read_text",
                    "selected_mode_internal": "document_reader",
                    "mode_label": "Read Text",
                    "status": "success",
                    "answer": "Safe answer body.",
                    "summary": "Safe answer body.",
                    "camera_backend_used": "opencv",
                    "camera_resolution": [1920, 1080],
                    "model_used": "gpt-5.4-mini",
                    "duration_seconds": 1.5,
                    "retry_status": "",
                    "error_summary": "",
                    "private_path": "data/private/current/processed.jpg",
                    "secret_value": "sk-secret-123",
                }
            ]
        ),
        encoding="utf-8",
    )
    controller = AppController(
        runtime,
        camera_store=CachedImageStore(),
        result_store=CachedImageStore(),
    )

    controller.openHistory()

    qtbot.waitUntil(lambda: controller.historyEntriesModel.count == 1, timeout=3000)
    history_item = controller.historyEntriesModel.get(0)
    assert "private_path" not in history_item
    assert "secret_value" not in history_item

    controller.openHistoryItem("entry-1")
    qtbot.waitUntil(lambda: controller.currentScreen == "history_detail", timeout=1000)
    assert "data/private/current/processed.jpg" not in controller.selectedHistoryDetailHtml
    assert "sk-secret-123" not in controller.selectedHistoryDetailHtml
    controller.shutdown()


def test_capture_pipeline_appends_history_and_history_screen_reads_it(qapp, qtbot, tmp_path) -> None:
    runtime, controller = build_controller(tmp_path)

    controller.selectMode("read_text")
    qtbot.waitUntil(lambda: controller.currentScreen == "camera", timeout=1000)
    controller.capture()
    qtbot.waitUntil(lambda: controller.currentScreen == "result", timeout=4000)

    stored_entries = runtime.result_history_store.load_entries()
    assert len(stored_entries) == 1
    assert stored_entries[0]["mode_label"] == "Read Text"
    assert stored_entries[0]["answer"]

    controller.openHistory()
    qtbot.waitUntil(
        lambda: controller.currentScreen == "history" and controller.historyEntriesModel.count == 1,
        timeout=3000,
    )
    controller.shutdown()
