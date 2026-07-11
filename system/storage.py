"""Shared filesystem helpers for private runtime data."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any


def atomic_write_text(
    path: str | Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> Path:
    """Atomically replace a text file using a flushed temporary file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    temp_file = tempfile.NamedTemporaryFile(
        delete=False,
        dir=destination.parent,
        prefix=f".{destination.stem}-",
        suffix=f"{destination.suffix}.tmp",
        mode="w",
        encoding=encoding,
    )

    try:
        with temp_file:
            temp_file.write(content)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        Path(temp_file.name).replace(destination)
        return destination
    except Exception:
        safe_unlink(temp_file.name)
        raise


def atomic_write_json(
    path: str | Path,
    payload: Any,
    *,
    encoding: str = "utf-8",
    ensure_ascii: bool = True,
    indent: int = 2,
    trailing_newline: bool = True,
) -> Path:
    """Atomically write JSON to disk."""
    text = json.dumps(payload, ensure_ascii=ensure_ascii, indent=indent)
    if trailing_newline:
        text += "\n"
    return atomic_write_text(path, text, encoding=encoding)


def quarantine_file(
    path: str | Path,
    *,
    quarantine_dir: str | Path,
    reason: str,
) -> Path | None:
    """Move a problematic file into a quarantine directory when possible."""
    source = Path(path)
    if not source.exists():
        return None

    destination_dir = Path(quarantine_dir)
    destination_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_reason = "".join(ch for ch in reason.lower() if ch.isalnum() or ch in {"-", "_"})
    suffix = source.suffix or ".dat"
    destination = destination_dir / f"{source.stem}-{timestamp}-{safe_reason}{suffix}"

    try:
        source.replace(destination)
    except OSError:
        shutil.copy2(source, destination)
        safe_unlink(source)
    return destination


def safe_unlink(path: str | Path | None) -> None:
    """Remove a file if it exists, ignoring best-effort failures."""
    if path is None:
        return

    try:
        Path(path).unlink(missing_ok=True)
    except OSError:
        pass


def safe_rmtree(path: str | Path | None) -> None:
    """Remove a directory tree if it exists, ignoring best-effort failures."""
    if path is None:
        return

    shutil.rmtree(Path(path), ignore_errors=True)
