"""Shared production diagnostics for installer, updater, and setup flows."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from config import load_device_settings
from hardware.device_check import check_camera, check_gpio_available
from visiondesk.paths import VisionDeskPaths, resolve_visiondesk_paths
from visiondesk.version import __version__


@dataclass(slots=True)
class DiagnosticResult:
    """Serializable result for one production or setup diagnostic check."""

    name: str
    status: str
    message: str
    required: bool = True

    @property
    def passed(self) -> bool:
        return self.status == "pass"

    @property
    def failed(self) -> bool:
        return self.required and self.status == "fail"


def check_python_imports() -> DiagnosticResult:
    """Verify required Python modules import successfully."""
    required_modules = ("PySide6", "yaml", "numpy", "openai", "gpiozero")
    failed: list[str] = []
    for module_name in required_modules:
        try:
            __import__(module_name)
        except Exception as exc:
            failed.append(f"{module_name}: {exc}")
    if failed:
        return DiagnosticResult(
            name="python_imports",
            status="fail",
            message="Required Python imports failed: " + "; ".join(failed),
        )
    return DiagnosticResult(
        name="python_imports",
        status="pass",
        message="Required Python imports succeeded.",
    )


def check_qml_load(*, paths: VisionDeskPaths | None = None) -> DiagnosticResult:
    """Verify the Qt application can load the root QML surface in mock mode."""
    resolved_paths = paths or resolve_visiondesk_paths()
    prior_qt_platform = os.environ.get("QT_QPA_PLATFORM")
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    temp_dir = Path(tempfile.mkdtemp(prefix="visiondesk-qml-smoke-"))
    try:
        from PySide6.QtCore import QUrl
        from PySide6.QtQml import QQmlApplicationEngine
        from PySide6.QtWidgets import QApplication

        from qt_app.app_controller import AppController
        from qt_app.image_provider import CachedImageStore, VisionDeskImageProvider
        from qt_app.runtime import RuntimePaths, VisionDeskRuntime

        app = QApplication.instance() or QApplication(["visiondesk-qml-smoke"])
        smoke_paths = RuntimePaths(
            setup_state_path=temp_dir / "setup_state.json",
            health_status_path=temp_dir / "health_status.json",
            latest_result_path=temp_dir / "latest_result.txt",
            result_history_path=temp_dir / "result_history.json",
            private_data_path=temp_dir / "private",
            env_file_path=temp_dir / "visiondesk.env",
            config_path=resolved_paths.config_path,
            logs_dir=temp_dir / "logs",
            app_root=resolved_paths.app_root,
        )
        runtime = VisionDeskRuntime(
            mock_hardware=True,
            paths=smoke_paths,
            settings=load_device_settings(config_path=resolved_paths.config_path),
            purge_on_startup=False,
        )
        controller = AppController(
            runtime,
            camera_store=CachedImageStore(),
            result_store=CachedImageStore(),
        )
        engine = QQmlApplicationEngine()
        engine.addImageProvider(
            "visiondesk",
            VisionDeskImageProvider(
                camera_store=controller._camera_store,
                result_store=controller._result_store,
            ),
        )
        engine.rootContext().setContextProperty("appController", controller)
        engine.load(QUrl.fromLocalFile(str((resolved_paths.app_root / "qt_app" / "qml" / "Main.qml").resolve())))
        loaded = bool(engine.rootObjects())
        controller.shutdown()
        if not loaded:
            return DiagnosticResult(
                name="qml_load",
                status="fail",
                message="Qt QML engine did not create any root objects.",
            )
        return DiagnosticResult(
            name="qml_load",
            status="pass",
            message="Qt application loaded Main.qml successfully in offscreen smoke mode.",
        )
    except Exception as exc:
        return DiagnosticResult(
            name="qml_load",
            status="fail",
            message=f"Qt QML smoke load failed. {exc}",
        )
    finally:
        if prior_qt_platform is None:
            os.environ.pop("QT_QPA_PLATFORM", None)
        else:
            os.environ["QT_QPA_PLATFORM"] = prior_qt_platform


def check_network_manager_available() -> DiagnosticResult:
    """Verify NetworkManager/nmcli is installed and callable."""
    try:
        completed = subprocess.run(
            ["nmcli", "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5.0,
        )
    except FileNotFoundError:
        return DiagnosticResult(
            name="network_manager",
            status="fail",
            message="nmcli is not installed or not on PATH.",
        )
    except Exception as exc:
        return DiagnosticResult(
            name="network_manager",
            status="fail",
            message=f"Could not verify NetworkManager. {exc}",
        )
    if completed.returncode != 0:
        return DiagnosticResult(
            name="network_manager",
            status="fail",
            message=completed.stderr.strip() or completed.stdout.strip() or "nmcli returned a failure status.",
        )
    return DiagnosticResult(
        name="network_manager",
        status="pass",
        message=completed.stdout.strip() or "NetworkManager is available.",
    )


def check_display_session_available() -> DiagnosticResult:
    """Verify a usable display session signal is present for the kiosk UI."""
    display = str(os.getenv("DISPLAY", "")).strip()
    wayland_display = str(os.getenv("WAYLAND_DISPLAY", "")).strip()
    x11_socket = Path("/tmp/.X11-unix/X0")
    runtime_dir = Path(str(os.getenv("XDG_RUNTIME_DIR", "")).strip() or "/run/user")

    if display and x11_socket.exists():
        return DiagnosticResult(
            name="display_session",
            status="pass",
            message=f"Detected X11 display session {display}.",
        )
    if wayland_display and (runtime_dir / wayland_display).exists():
        return DiagnosticResult(
            name="display_session",
            status="pass",
            message=f"Detected Wayland display session {wayland_display}.",
        )
    if x11_socket.exists():
        return DiagnosticResult(
            name="display_session",
            status="pass",
            message="Detected a reachable X11 socket at /tmp/.X11-unix/X0.",
        )
    return DiagnosticResult(
        name="display_session",
        status="fail",
        message="No active X11 or Wayland display session markers were detected.",
    )


def check_storage_writable(*, paths: VisionDeskPaths | None = None) -> DiagnosticResult:
    """Verify key production directories are writable."""
    resolved_paths = paths or resolve_visiondesk_paths()
    targets = [
        resolved_paths.data_dir,
        resolved_paths.logs_dir,
        resolved_paths.config_dir,
    ]
    failures: list[str] = []
    for target in targets:
        try:
            target.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                dir=target,
                prefix=".visiondesk-write-check-",
                delete=True,
            ):
                pass
        except Exception as exc:
            failures.append(f"{target}: {exc}")
    if failures:
        return DiagnosticResult(
            name="storage_writable",
            status="fail",
            message="Storage write checks failed: " + "; ".join(failures),
        )
    return DiagnosticResult(
        name="storage_writable",
        status="pass",
        message="Config, data, and log directories are writable.",
    )


def check_config_readable(*, config_path: str | Path | None = None) -> DiagnosticResult:
    """Verify the device config can be loaded successfully."""
    target_path = Path(config_path) if config_path is not None else resolve_visiondesk_paths().config_path
    try:
        load_device_settings(config_path=target_path)
    except Exception as exc:
        return DiagnosticResult(
            name="config_readable",
            status="fail",
            message=f"Could not load device config '{target_path}'. {exc}",
        )
    return DiagnosticResult(
        name="config_readable",
        status="pass",
        message=f"Device config '{target_path}' loaded successfully.",
    )


def run_installation_smoke_checks(
    *,
    paths: VisionDeskPaths | None = None,
    skip_hardware: bool = False,
) -> list[DiagnosticResult]:
    """Run the full set of installation/update smoke checks."""
    resolved_paths = paths or resolve_visiondesk_paths()
    settings = load_device_settings(config_path=resolved_paths.config_path)
    results = [
        check_python_imports(),
        check_qml_load(paths=resolved_paths),
        check_config_readable(config_path=resolved_paths.config_path),
        check_storage_writable(paths=resolved_paths),
        check_network_manager_available(),
        check_display_session_available(),
    ]
    if skip_hardware:
        results.append(
            DiagnosticResult(
                name="camera",
                status="skip",
                message="Camera check skipped by request.",
                required=False,
            )
        )
        results.append(
            DiagnosticResult(
                name="gpio",
                status="skip",
                message="GPIO check skipped by request.",
                required=False,
            )
        )
    else:
        camera_result = check_camera(settings)
        gpio_result = check_gpio_available()
        results.append(
            DiagnosticResult(
                name=camera_result.name,
                status=camera_result.status,
                message=camera_result.message,
                required=camera_result.required,
            )
        )
        results.append(
            DiagnosticResult(
                name=gpio_result.name,
                status=gpio_result.status,
                message=gpio_result.message,
                required=gpio_result.required,
            )
        )
    return results


def run_setup_device_checks(*, paths: VisionDeskPaths | None = None) -> list[DiagnosticResult]:
    """Run the device checks shown on the setup welcome step."""
    resolved_paths = paths or resolve_visiondesk_paths()
    settings = load_device_settings(config_path=resolved_paths.config_path)
    camera_result = check_camera(settings)
    gpio_result = check_gpio_available()
    return [
        check_config_readable(config_path=resolved_paths.config_path),
        check_storage_writable(paths=resolved_paths),
        check_network_manager_available(),
        check_display_session_available(),
        DiagnosticResult(
            name=camera_result.name,
            status=camera_result.status,
            message=camera_result.message,
            required=camera_result.required,
        ),
        DiagnosticResult(
            name=gpio_result.name,
            status=gpio_result.status,
            message=gpio_result.message,
            required=gpio_result.required,
        ),
    ]


def diagnostics_summary(results: list[DiagnosticResult]) -> dict[str, Any]:
    """Return a machine-friendly summary of a diagnostics run."""
    return {
        "app_version": __version__,
        "all_required_passed": all(not result.failed for result in results),
        "results": [asdict(result) for result in results],
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run VisionDesk diagnostics.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the diagnostics payload as JSON.",
    )
    parser.add_argument(
        "--skip-hardware",
        action="store_true",
        help="Skip camera and GPIO checks.",
    )
    parser.add_argument(
        "--path-mode",
        choices=("development", "production"),
        default=None,
        help="Override the resolved VisionDesk path mode.",
    )
    parser.add_argument(
        "--setup",
        action="store_true",
        help="Run the setup wizard welcome/device checks instead of the full smoke test set.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint used by install/update scripts."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    paths = resolve_visiondesk_paths(mode=args.path_mode)
    results = (
        run_setup_device_checks(paths=paths)
        if args.setup
        else run_installation_smoke_checks(paths=paths, skip_hardware=args.skip_hardware)
    )
    payload = diagnostics_summary(results)
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    else:
        for result in results:
            prefix = "[OK]" if result.passed else "[SKIP]" if result.status == "skip" else "[FAIL]"
            print(f"{prefix} {result.name}: {result.message}")
    return 0 if payload["all_required_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
