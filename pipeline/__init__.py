"""Shared pipeline orchestration for terminal, Qt, and GPIO entrypoints."""

from pipeline.runner import (
    build_capture_session_paths,
    PipelineError,
    PipelineResult,
    file_exists,
    file_mtime,
    is_processed_fresh,
    resolve_preprocess_options,
    run_analyze,
    run_analyze_confirmed,
    run_capture,
    run_capture_analyze,
    run_preprocess,
    save_latest_result,
    should_use_screen_optimization,
)

__all__ = [
    "PipelineError",
    "PipelineResult",
    "build_capture_session_paths",
    "file_exists",
    "file_mtime",
    "is_processed_fresh",
    "resolve_preprocess_options",
    "run_analyze",
    "run_analyze_confirmed",
    "run_capture",
    "run_capture_analyze",
    "run_preprocess",
    "save_latest_result",
    "should_use_screen_optimization",
]
