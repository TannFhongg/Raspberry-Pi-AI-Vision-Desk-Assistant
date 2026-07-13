"""Privacy regressions for preprocessing intermediate image retention."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import patch

from vision.preprocess import preprocess_image, purge_debug_images


class _FakeImage:
    shape = (100, 160, 3)

    def copy(self):
        return self


class _FakeCv2:
    IMREAD_COLOR = 1

    def imread(self, _path: str, _mode: int):
        return _FakeImage()

    def imwrite(self, path: str, _image) -> bool:
        Path(path).write_bytes(b"image")
        return True


def _run_preprocess(tmp_path: Path, *, debug_images: bool, debug_root: Path):
    source = tmp_path / "private" / "current" / "captured.jpg"
    output = tmp_path / "private" / "current" / "processed.jpg"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"captured")
    with (
        patch("vision.preprocess._import_cv2", return_value=_FakeCv2()),
        patch("vision.preprocess.detect_screen_region", return_value=None),
    ):
        return preprocess_image(
            input_path=str(source),
            output_path=str(output),
            detect_screen=True,
            debug_dir=str(debug_root),
            debug_images=debug_images,
        )


def test_default_preprocessing_creates_no_debug_or_source_copies(tmp_path) -> None:
    public_static = tmp_path / "static"

    result = _run_preprocess(tmp_path, debug_images=False, debug_root=public_static)

    assert result.debug_dir is None
    assert not public_static.exists()
    assert (tmp_path / "private" / "current" / "processed.jpg").is_file()


def test_debug_opt_in_writes_only_under_private_debug_storage(tmp_path) -> None:
    private_debug = tmp_path / "private" / "debug"
    public_static = tmp_path / "static"

    result = _run_preprocess(tmp_path, debug_images=True, debug_root=private_debug)

    assert result.debug_dir is not None
    assert result.debug_dir.parent == private_debug
    assert sorted(path.name for path in result.debug_dir.iterdir()) == [
        "corrected.jpg",
        "detected_screen.jpg",
        "enhanced.jpg",
        "original.jpg",
    ]
    assert not public_static.exists()


def test_private_debug_retention_purges_expired_job_directories(tmp_path) -> None:
    debug_root = tmp_path / "private" / "debug"
    stale_job = debug_root / "preprocess-stale"
    recent_job = debug_root / "preprocess-recent"
    stale_job.mkdir(parents=True)
    recent_job.mkdir(parents=True)
    old_timestamp = time.time() - 7200
    os.utime(stale_job, (old_timestamp, old_timestamp))

    removed = purge_debug_images(debug_root, retention_hours=1.0, max_jobs=5)

    assert removed == 1
    assert not stale_job.exists()
    assert recent_job.exists()
