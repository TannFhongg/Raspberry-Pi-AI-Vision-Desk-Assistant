"""Entry point for the native PySide6 + Qt Quick VisionDesk frontend."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QTimer, Qt, QUrl
from PySide6.QtGui import QCursor, QGuiApplication
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtWidgets import QApplication

from qt_app.app_controller import AppController
from qt_app.image_provider import CachedImageStore, VisionDeskImageProvider
from qt_app.runtime import VisionDeskRuntime


class FullscreenCursorHider(QObject):
    """Hide the cursor after inactivity when the app is running fullscreen."""

    def __init__(self, app: QApplication, *, enabled: bool) -> None:
        super().__init__()
        self.app = app
        self.enabled = enabled
        self.hidden = False
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.setInterval(5000)
        self.timer.timeout.connect(self._hide_cursor)

    def start(self) -> None:
        """Begin tracking user input for cursor hiding."""
        if not self.enabled:
            return
        self.app.installEventFilter(self)
        self.timer.start()

    def eventFilter(self, watched, event) -> bool:
        del watched
        if not self.enabled:
            return False
        if event.type() in {
            QEvent.MouseMove,
            QEvent.MouseButtonPress,
            QEvent.MouseButtonRelease,
            QEvent.TouchBegin,
            QEvent.TouchUpdate,
            QEvent.TouchEnd,
            QEvent.KeyPress,
        }:
            if self.hidden:
                QApplication.restoreOverrideCursor()
                self.hidden = False
            self.timer.start()
        return False

    def _hide_cursor(self) -> None:
        if not self.enabled:
            return
        QApplication.setOverrideCursor(QCursor(Qt.BlankCursor))
        self.hidden = True


def build_argument_parser() -> argparse.ArgumentParser:
    """Return the CLI parser for the Qt app entry point."""
    parser = argparse.ArgumentParser(description="Run the native VisionDesk Qt frontend.")
    parser.add_argument("--windowed", action="store_true", help="Run in a normal window instead of fullscreen.")
    parser.add_argument(
        "--mock-hardware",
        action="store_true",
        help="Use deterministic mock preview/pipeline services instead of GPIO/camera hardware.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Bootstrap the Qt runtime, controllers, image providers, and QML engine."""
    args = build_argument_parser().parse_args(argv)
    QQuickStyle.setStyle("Basic")
    app = QApplication(argv or sys.argv)
    app.setApplicationName("VisionDesk Qt")
    app.setOrganizationName("VisionDesk")
    QGuiApplication.setQuitOnLastWindowClosed(True)

    runtime = VisionDeskRuntime(mock_hardware=args.mock_hardware)
    camera_store = CachedImageStore()
    result_store = CachedImageStore()
    controller = AppController(
        runtime,
        camera_store=camera_store,
        result_store=result_store,
    )

    engine = QQmlApplicationEngine()
    engine.addImageProvider(
        "visiondesk",
        VisionDeskImageProvider(camera_store=camera_store, result_store=result_store),
    )
    engine.rootContext().setContextProperty("appController", controller)
    main_qml_path = QUrl.fromLocalFile(str((Path(__file__).resolve().parent / "qml" / "Main.qml")))
    engine.load(main_qml_path)
    if not engine.rootObjects():
        controller.shutdown()
        return 1

    root = engine.rootObjects()[0]
    if args.windowed:
        root.setWidth(runtime.screen_width)
        root.setHeight(runtime.screen_height)
        root.show()
    else:
        root.showFullScreen()

    cursor_hider = FullscreenCursorHider(app, enabled=not args.windowed)
    cursor_hider.start()
    app.aboutToQuit.connect(controller.shutdown)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
