"""Runtime reliability helpers for logging and device health."""

from importlib import import_module

from system.health import HealthMonitor, collect_health_snapshot, write_health_snapshot
from system.logging import configure_logging
from system.offline_retry import (
    OfflineRetryEntry,
    OfflineRetryQueue,
    OfflineRetryQueueError,
    OfflineRetryQueueFullError,
)
from system.storage import atomic_write_json, atomic_write_text, quarantine_file, safe_rmtree, safe_unlink

_DIAGNOSTIC_EXPORTS = frozenset(
    {
        "DiagnosticResult",
        "diagnostics_summary",
        "run_installation_smoke_checks",
        "run_setup_device_checks",
    }
)


def __getattr__(name: str):
    """Load diagnostics exports lazily so ``python -m system.diagnostics`` is safe."""
    if name not in _DIAGNOSTIC_EXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("system.diagnostics"), name)
    globals()[name] = value
    return value

__all__ = [
    "DiagnosticResult",
    "HealthMonitor",
    "OfflineRetryEntry",
    "OfflineRetryQueue",
    "OfflineRetryQueueError",
    "OfflineRetryQueueFullError",
    "atomic_write_json",
    "atomic_write_text",
    "collect_health_snapshot",
    "configure_logging",
    "diagnostics_summary",
    "quarantine_file",
    "run_installation_smoke_checks",
    "run_setup_device_checks",
    "safe_rmtree",
    "safe_unlink",
    "write_health_snapshot",
]
