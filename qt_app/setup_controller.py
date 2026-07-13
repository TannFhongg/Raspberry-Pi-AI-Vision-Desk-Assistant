"""Setup-flow controller for the native Qt frontend."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot

from config import update_device_config
from hardware.device_check import check_camera, check_gpio_available, check_openai_reachable
from hardware.setup_gpio import GPIOSetupVerifier, GPIOSetupVerifierError
from qt_app.models import DictListModel
from qt_app.runtime import VisionDeskRuntime
from system.device_setup import (
    DeviceSetupError,
    connect_wifi_network,
    remove_env_value,
    scan_wifi_networks,
    upsert_env_value,
)
from system.diagnostics import run_setup_device_checks
from system.setup_flow import (
    finish_setup,
    mask_secret_value,
    run_setup_camera_test,
    run_setup_openai_key,
    run_setup_wifi_connect,
    sync_setup_gpio_state,
)

LOGGER = logging.getLogger(__name__)
SUPPORTED_GPIO_PINS = frozenset({2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27})


class _MockSetupVerifier:
    """Simple verifier used by `--mock-hardware` setup runs."""

    def __init__(self, required_pins: dict[str, int], **_: Any) -> None:
        self._required = [
            {"label": label, "pin": pin, "pressed": False}
            for label, pin in required_pins.items()
        ]

    def start(self) -> None:
        return None

    def close(self) -> None:
        return None

    def snapshot(self) -> dict[str, Any]:
        return {
            "required": [{**item, "pressed": True} for item in self._required],
            "pressed_labels": [item["label"] for item in self._required],
            "all_pressed": True,
            "validation_issues": [],
        }


class SetupController(QObject):
    """Manage first-boot setup state directly through Qt slots and signals."""

    stateChanged = Signal()
    setupCompleted = Signal(str)
    workerCompleted = Signal()

    def __init__(self, runtime: VisionDeskRuntime, parent=None) -> None:
        super().__init__(parent)
        self.runtime = runtime
        self._state = runtime.setup_state_store.load_state()
        self._warnings: list[str] = runtime.setup_state_store.build_warnings(self._state)
        self._wifi_networks_model = DictListModel(["ssid", "signal", "security"], self)
        self._gpio_requirements_model = DictListModel(["label", "pin", "pressed"], self)
        self._device_checks_model = DictListModel(["name", "status", "message", "required"], self)
        self._gpio_verifier: GPIOSetupVerifier | _MockSetupVerifier | None = None
        self._gpio_timer = QTimer(self)
        self._gpio_timer.setInterval(350)
        self._gpio_timer.timeout.connect(self._sync_gpio_state)
        self.workerCompleted.connect(self.refresh_state)
        self.refresh_state()

    @Property(QObject, constant=True)
    def wifiNetworksModel(self) -> DictListModel:
        return self._wifi_networks_model

    @Property(QObject, constant=True)
    def gpioRequirementsModel(self) -> DictListModel:
        return self._gpio_requirements_model

    @Property(QObject, constant=True)
    def deviceChecksModel(self) -> DictListModel:
        return self._device_checks_model

    @Property(str, notify=stateChanged)
    def currentStep(self) -> str:
        return str(self._state.get("current_step", "welcome"))

    @Property(str, notify=stateChanged)
    def finishMessage(self) -> str:
        return str(self._state.get("finish_message", ""))

    @Property(str, notify=stateChanged)
    def warningsText(self) -> str:
        return "\n".join(self._warnings)

    @Property(bool, notify=stateChanged)
    def hasApiKey(self) -> bool:
        return bool(self._state.get("openai", {}).get("key_present", False))

    @Property(bool, notify=stateChanged)
    def apiKeyVerified(self) -> bool:
        return bool(self._state.get("openai", {}).get("api_key_verified", False))

    @Property(str, notify=stateChanged)
    def maskedApiKey(self) -> str:
        openai_state = self._state.get("openai", {})
        should_show = bool(openai_state.get("key_present")) or self.runtime.setup_is_complete()
        return mask_secret_value(os.getenv("OPENAI_API_KEY", "")) if should_show else ""

    @Property(str, notify=stateChanged)
    def maskedOpenAiKey(self) -> str:
        return self.maskedApiKey

    @Property(str, notify=stateChanged)
    def deviceChecksStatus(self) -> str:
        welcome = self._state.get("steps", {}).get("welcome", {})
        return str(welcome.get("status", "idle"))

    @Property(str, notify=stateChanged)
    def deviceChecksMessage(self) -> str:
        welcome = self._state.get("steps", {}).get("welcome", {})
        return str(welcome.get("message", ""))

    @Property(str, notify=stateChanged)
    def wifiMessage(self) -> str:
        return str(self._state.get("wifi", {}).get("message", ""))

    @Property(str, notify=stateChanged)
    def wifiScanStatus(self) -> str:
        return str(self._state.get("wifi", {}).get("scan_status", "idle"))

    @Property(str, notify=stateChanged)
    def wifiStatus(self) -> str:
        return str(self._state.get("wifi", {}).get("connect_status", "idle"))

    @Property(str, notify=stateChanged)
    def wifiSsid(self) -> str:
        return str(self._state.get("wifi", {}).get("ssid", "")).strip()

    @Property(str, notify=stateChanged)
    def openAiMessage(self) -> str:
        return str(self._state.get("openai", {}).get("message", ""))

    @Property(str, notify=stateChanged)
    def openAiStatus(self) -> str:
        return str(self._state.get("openai", {}).get("status", "idle"))

    @Property(str, notify=stateChanged)
    def cameraMessage(self) -> str:
        return str(self._state.get("camera", {}).get("message", ""))

    @Property(str, notify=stateChanged)
    def cameraStatus(self) -> str:
        return str(self._state.get("camera", {}).get("status", "idle"))

    @Property(str, notify=stateChanged)
    def cameraAutofocusMode(self) -> str:
        return str(self.runtime.settings.camera.autofocus_mode)

    @Property(str, notify=stateChanged)
    def cameraResolutionLabel(self) -> str:
        resolution = self.runtime.settings.camera.resolution
        return f"{resolution.width} x {resolution.height}"

    @Property(str, notify=stateChanged)
    def cameraPreviewFpsLabel(self) -> str:
        target_fps = float(self.runtime.settings.camera.preview.target_fps)
        return f"{target_fps:g}"

    @Property(str, notify=stateChanged)
    def cameraExposureLabel(self) -> str:
        return str(self.runtime.settings.camera.exposure)

    @Property(str, notify=stateChanged)
    def gpioMessage(self) -> str:
        return str(self._state.get("gpio", {}).get("message", ""))

    @Property(str, notify=stateChanged)
    def gpioStatus(self) -> str:
        return str(self._state.get("gpio", {}).get("status", "idle"))

    @Property(bool, notify=stateChanged)
    def gpioActive(self) -> bool:
        return bool(self._state.get("gpio", {}).get("active", False))

    @Property(bool, notify=stateChanged)
    def readyToFinish(self) -> bool:
        return self.runtime.setup_state_store.setup_ready_to_finish(self._state)

    def refresh_state(self) -> None:
        """Reload setup state plus derived warning/model payloads."""
        self._state = self.runtime.setup_state_store.load_state()
        self._warnings = self.runtime.setup_state_store.build_warnings(self._state)
        self._wifi_networks_model.set_items(list(self._state.get("wifi", {}).get("available_networks", [])))
        self._gpio_requirements_model.set_items(list(self._state.get("gpio", {}).get("required", [])))
        self._device_checks_model.set_items(
            list(self._state.get("steps", {}).get("welcome", {}).get("checks", []))
        )
        self.stateChanged.emit()

    @Slot()
    def runDeviceChecks(self) -> None:
        self._run_in_thread(self._device_checks_worker, "setup-device-checks")

    @Slot()
    def goToNextStep(self) -> None:
        step = self.currentStep
        step_order = ["welcome", "wifi", "openai", "camera", "gpio", "finish"]
        try:
            next_step = step_order[min(step_order.index(step) + 1, len(step_order) - 1)]
        except ValueError:
            next_step = step_order[0]
        self.runtime.setup_state_store.write_state({"current_step": next_step})
        self.refresh_state()

    @Slot()
    def goToPreviousStep(self) -> None:
        step = self.currentStep
        step_order = ["welcome", "wifi", "openai", "camera", "gpio", "finish"]
        try:
            next_step = step_order[max(step_order.index(step) - 1, 0)]
        except ValueError:
            next_step = step_order[0]
        self.runtime.setup_state_store.write_state({"current_step": next_step})
        self.refresh_state()

    @Slot(str)
    def goToStep(self, step: str) -> None:
        self.runtime.setup_state_store.write_state({"current_step": step})
        self.refresh_state()

    @Slot()
    def scanWifi(self) -> None:
        self._run_in_thread(self._scan_wifi_worker, "setup-scan-wifi")

    @Slot(str, str, str)
    def connectWifi(self, selected_ssid: str, manual_ssid: str, password: str) -> None:
        self._run_in_thread(
            lambda: self._connect_wifi_worker(selected_ssid, manual_ssid, password),
            "setup-connect-wifi",
        )

    @Slot(str)
    def verifyApiKey(self, api_key: str) -> None:
        self._run_in_thread(lambda: self._verify_api_key_worker(api_key), "setup-openai-key")

    @Slot()
    def clearApiKey(self) -> None:
        self._run_in_thread(self._clear_api_key_worker, "setup-openai-clear")

    @Slot()
    def runCameraTest(self) -> None:
        self._run_in_thread(self._camera_test_worker, "setup-camera-test")

    @Slot()
    def startGpioTest(self) -> None:
        self._start_gpio_test()

    @Slot()
    def stopGpioTest(self) -> None:
        self._stop_gpio_test()

    @Slot()
    def finishSetup(self) -> None:
        succeeded = finish_setup(
            self.runtime.setup_state_store,
            update_device_config=lambda payload: update_device_config(
                payload,
                config_path=self.runtime.settings.config_path,
            ),
            on_completed=self._on_setup_completed,
        )
        if not succeeded:
            self.refresh_state()

    def close(self) -> None:
        """Stop any temporary GPIO setup verifier."""
        self._stop_gpio_verifier()

    def _on_setup_completed(self, completion_timestamp: str) -> None:
        self.runtime.mark_setup_complete(completion_timestamp)
        self.runtime.request_restart()
        self.setupCompleted.emit(completion_timestamp)

    def _run_in_thread(self, target, name: str) -> None:
        worker = threading.Thread(target=self._wrap_worker(target), daemon=True, name=name)
        worker.start()

    def _wrap_worker(self, target):
        def _worker() -> None:
            try:
                target()
            except Exception:
                LOGGER.exception("Setup worker failed")
            self.workerCompleted.emit()

        return _worker

    def _device_checks_worker(self) -> None:
        checks = run_setup_device_checks()
        self.runtime.setup_state_store.write_device_checks([check.__dict__ for check in checks])

    def _scan_wifi_worker(self) -> None:
        try:
            networks = scan_wifi_networks()
            message = (
                f"Found {len(networks)} Wi-Fi network{'s' if len(networks) != 1 else ''}."
                if networks
                else "No nearby Wi-Fi networks were found."
            )
            self.runtime.setup_state_store.write_state(
                {
                    "current_step": "wifi",
                    "finish_message": "",
                    "wifi": {
                        "scan_status": "pass",
                        "available_networks": networks,
                        "message": message,
                    },
                }
            )
        except DeviceSetupError as exc:
            self.runtime.setup_state_store.write_state(
                {
                    "current_step": "wifi",
                    "finish_message": "",
                    "wifi": {
                        "scan_status": "fail",
                        "message": str(exc),
                    },
                }
            )

    def _connect_wifi_worker(self, selected_ssid: str, manual_ssid: str, password: str) -> None:
        run_setup_wifi_connect(
            self.runtime.setup_state_store,
            selected_ssid=selected_ssid,
            manual_ssid=manual_ssid,
            password=password,
            connection_name=(manual_ssid or selected_ssid).strip(),
            connect_wifi_network=connect_wifi_network,
            update_device_config=lambda payload: update_device_config(
                payload,
                config_path=self.runtime.settings.config_path,
            ),
        )

    def _verify_api_key_worker(self, api_key: str) -> None:
        run_setup_openai_key(
            self.runtime.setup_state_store,
            api_key=api_key,
            env_file_path=self.runtime.paths.env_file_path,
            upsert_env_value=upsert_env_value,
            check_openai_reachable=check_openai_reachable,
        )

    def _clear_api_key_worker(self) -> None:
        remove_env_value(self.runtime.paths.env_file_path, "OPENAI_API_KEY")
        os.environ.pop("OPENAI_API_KEY", None)
        self.runtime.setup_state_store.write_state(
            {
                "current_step": "openai",
                "openai": {
                    "status": "idle",
                    "key_present": False,
                    "api_key_verified": False,
                    "message": "OpenAI API key cleared. Enter a new key to continue.",
                },
            }
        )

    def _camera_test_worker(self) -> None:
        run_setup_camera_test(
            self.runtime.setup_state_store,
            check_camera=lambda: check_camera(self.runtime.settings),
        )

    def _validate_gpio_setup(self) -> list[str]:
        issues: list[str] = []
        seen: dict[int, str] = {}
        for item in self.runtime.build_setup_gpio_requirements():
            label = str(item.get("label", "")).strip()
            pin = int(item.get("pin"))
            if pin not in SUPPORTED_GPIO_PINS:
                issues.append(f"GPIO pin {pin} for '{label}' is not supported.")
            if pin in seen:
                issues.append(f"GPIO pin {pin} is duplicated between '{label}' and '{seen[pin]}'.")
            else:
                seen[pin] = label
        if self.runtime.settings.led.enabled and self.runtime.settings.led.pin in seen:
            issues.append(
                f"GPIO pin {self.runtime.settings.led.pin} conflicts with the configured LED pin."
            )
        gpio_availability = check_gpio_available()
        if gpio_availability.failed:
            issues.append(gpio_availability.message)
        return issues

    def _start_gpio_test(self) -> None:
        self._stop_gpio_verifier()
        validation_issues = self._validate_gpio_setup()
        if validation_issues:
            self.runtime.setup_state_store.write_state(
                {
                    "current_step": "gpio",
                    "gpio": {
                        "status": "fail",
                        "message": validation_issues[0],
                        "active": False,
                        "required": self.runtime.build_setup_gpio_requirements(),
                        "pressed_labels": [],
                        "all_pressed": False,
                        "validation_issues": validation_issues,
                    },
                }
            )
            self.refresh_state()
            return

        verifier_class = _MockSetupVerifier if self.runtime.mock_hardware else GPIOSetupVerifier
        try:
            verifier = verifier_class(
                self.runtime.build_setup_required_pin_map(),
                debounce_seconds=self.runtime.settings.button.debounce_seconds,
            )
            verifier.start()
            self._gpio_verifier = verifier
            self.runtime.setup_state_store.write_state(
                {
                    "current_step": "gpio",
                    "finish_message": "",
                    "gpio": {
                        "status": "running",
                        "message": "Press each configured GPIO button once to verify it.",
                        "active": True,
                        "required": self._snapshot_gpio_progress().get(
                            "required",
                            self.runtime.build_setup_gpio_requirements(),
                        ),
                        "pressed_labels": [],
                        "all_pressed": False,
                        "validation_issues": [],
                    },
                }
            )
            self._gpio_timer.start()
        except GPIOSetupVerifierError as exc:
            self.runtime.setup_state_store.write_state(
                {
                    "current_step": "gpio",
                    "finish_message": "",
                    "gpio": {
                        "status": "fail",
                        "message": str(exc),
                        "active": False,
                        "required": self.runtime.build_setup_gpio_requirements(),
                        "pressed_labels": [],
                        "all_pressed": False,
                        "validation_issues": [str(exc)],
                    },
                }
            )
        self.refresh_state()

    def _stop_gpio_test(self) -> None:
        state = self._sync_gpio_state()
        gpio_state = state.get("gpio", {})
        self._stop_gpio_verifier()
        passed = bool(gpio_state.get("all_pressed")) and not list(gpio_state.get("validation_issues", []))
        self.runtime.setup_state_store.write_state(
            {
                "current_step": "finish" if passed else "gpio",
                "finish_message": "",
                "gpio": {
                    "status": "pass" if passed else "fail",
                    "message": gpio_state.get(
                        "message",
                        "All configured GPIO setup buttons were pressed successfully."
                        if passed
                        else "GPIO button verification is incomplete.",
                    ),
                    "active": False,
                    "required": gpio_state.get("required", self.runtime.build_setup_gpio_requirements()),
                    "pressed_labels": gpio_state.get("pressed_labels", []),
                    "all_pressed": bool(gpio_state.get("all_pressed", False)),
                    "validation_issues": gpio_state.get("validation_issues", []),
                },
            }
        )
        self.refresh_state()

    def _stop_gpio_verifier(self) -> None:
        self._gpio_timer.stop()
        verifier = self._gpio_verifier
        self._gpio_verifier = None
        if verifier is not None:
            verifier.close()

    def _snapshot_gpio_progress(self) -> dict[str, Any]:
        verifier = self._gpio_verifier
        if verifier is None:
            return {
                "required": self.runtime.build_setup_gpio_requirements(),
                "pressed_labels": [],
                "all_pressed": False,
                "active": False,
                "message": "GPIO setup test is not running.",
                "validation_issues": [],
            }
        snapshot = verifier.snapshot()
        snapshot["active"] = True
        snapshot["message"] = (
            "All configured GPIO setup buttons were pressed successfully."
            if snapshot.get("all_pressed")
            else "Press each configured GPIO button once to verify it."
        )
        snapshot.setdefault("validation_issues", [])
        return snapshot

    def _sync_gpio_state(self) -> dict[str, Any]:
        if self._gpio_verifier is None:
            return self.runtime.setup_state_store.load_state()
        state = sync_setup_gpio_state(
            self.runtime.setup_state_store,
            self._snapshot_gpio_progress,
        )
        self.refresh_state()
        return state
