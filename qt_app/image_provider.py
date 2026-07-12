"""QML image providers backed by private in-memory image caches."""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtQuick import QQuickImageProvider


class CachedImageStore:
    """Thread-safe in-memory image cache used by QML image providers."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._image = QImage()
        self._revision = 0

    @property
    def revision(self) -> int:
        """Return the monotonically increasing image revision."""
        with self._lock:
            return self._revision

    def clear(self) -> None:
        """Remove the cached image and advance the revision."""
        with self._lock:
            self._image = QImage()
            self._revision += 1

    def set_bytes(self, data: bytes | bytearray | memoryview) -> bool:
        """Update the cache from encoded image bytes."""
        image = QImage()
        if not image.loadFromData(bytes(data)):
            return False
        with self._lock:
            self._image = image
            self._revision += 1
        return True

    def set_path(self, path: str | Path | None) -> bool:
        """Update the cache from an on-disk private image path."""
        if path is None:
            return False
        try:
            data = Path(path).read_bytes()
        except OSError:
            return False
        return self.set_bytes(data)

    def image(self) -> QImage:
        """Return a detached copy of the current image."""
        with self._lock:
            if self._image.isNull():
                return QImage()
            return self._image.copy()


class VisionDeskImageProvider(QQuickImageProvider):
    """Serve cached images to QML via `image://visiondesk/...` URLs."""

    def __init__(self, *, camera_store: CachedImageStore, result_store: CachedImageStore) -> None:
        super().__init__(QQuickImageProvider.Image)
        self._camera_store = camera_store
        self._result_store = result_store

    def requestImage(self, image_id: str, size: QSize, requested_size: QSize) -> QImage:
        del requested_size
        normalized_id = str(image_id).split("?", 1)[0].strip().lower()
        if normalized_id == "camera/live":
            image = self._camera_store.image()
        elif normalized_id == "result/latest":
            image = self._result_store.image()
        else:
            image = QImage()
        if size is not None and not image.isNull():
            size.setWidth(image.width())
            size.setHeight(image.height())
        return image

