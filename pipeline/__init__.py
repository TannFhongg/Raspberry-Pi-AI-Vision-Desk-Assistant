"""Shared pipeline orchestration for terminal, Flask, and GPIO entrypoints."""

from pipeline.runner import (
    PipelineError,
    PipelineResult,
    file_exists,
    file_mtime,
    is_processed_fresh,
    resolve_preprocess_options,
    run_analyze,
    run_capture,
    run_capture_analyze,
    run_preprocess,
    save_latest_result,
    should_use_screen_optimization,
)

__all__ = [
    "PipelineError",
    "PipelineResult",
    "file_exists",
    "file_mtime",
    "is_processed_fresh",
    "resolve_preprocess_options",
    "run_analyze",
    "run_capture",
    "run_capture_analyze",
    "run_preprocess",
    "save_latest_result",
    "should_use_screen_optimization",
]
