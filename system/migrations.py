"""Shared release-migration entrypoint used by install/update flows."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass

from visiondesk.paths import VisionDeskPaths, resolve_visiondesk_paths
from visiondesk.version import __version__


@dataclass(slots=True)
class MigrationSummary:
    """Report the migration hooks evaluated for this release."""

    applied: list[str]
    skipped: list[str]
    app_version: str
    path_mode: str


def run_pending_migrations(*, paths: VisionDeskPaths | None = None) -> MigrationSummary:
    """Run any release migrations required before switching the active symlink."""
    resolved_paths = paths or resolve_visiondesk_paths()
    applied: list[str] = []
    skipped = [
        "No schema migrations are currently required for this release.",
    ]
    return MigrationSummary(
        applied=applied,
        skipped=skipped,
        app_version=__version__,
        path_mode=resolved_paths.path_mode,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run pending VisionDesk release migrations.")
    parser.add_argument("--json", action="store_true", help="Print the migration summary as JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    summary = run_pending_migrations()
    if args.json:
        print(json.dumps(asdict(summary), ensure_ascii=True, indent=2))
    else:
        print(f"Migration check complete for VisionDesk {summary.app_version}.")
        for item in summary.applied:
            print(f"Applied: {item}")
        for item in summary.skipped:
            print(f"Skipped: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
