"""Command-line hardware diagnostics for the Raspberry Pi AI Vision Desk Assistant."""

from __future__ import annotations

import logging
import sys

from config import SettingsError, load_device_settings
from hardware.device_check import HardwareCheckResult, run_device_checks
from system import configure_logging

LOGGER = logging.getLogger(__name__)


def main() -> int:
    """Run all hardware diagnostics and return a shell-friendly exit code."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        print(
            "Error: python-dotenv is not installed. Activate your virtual environment and run: pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    load_dotenv()
    try:
        settings = load_device_settings()
    except SettingsError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    configure_logging(settings=settings)
    LOGGER.info("Hardware diagnostics startup begin")
    print("Running Raspberry Pi device diagnostics...")
    print(f"Config file: {settings.config_path}")
    print(f"Startup behavior: {settings.startup.behavior}")

    report = run_device_checks(settings=settings, status_callback=_print_result)
    if report.all_required_passed:
        LOGGER.info("Hardware diagnostics completed successfully")
        print("All required hardware checks passed.")
        return 0

    LOGGER.error("Hardware diagnostics completed with failures")
    print("One or more required hardware checks failed.", file=sys.stderr)
    return 1


def _print_result(result: HardwareCheckResult) -> None:
    """Print a human-friendly summary line for each diagnostic result."""
    label_map = {"pass": "PASS", "fail": "FAIL", "skip": "SKIP"}
    label = label_map.get(result.status, result.status.upper())
    print(f"[{label}] {result.name}: {result.message}")


if __name__ == "__main__":
    raise SystemExit(main())
