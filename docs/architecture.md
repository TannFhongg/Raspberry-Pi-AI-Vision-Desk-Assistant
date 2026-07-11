# Architecture

## Overview

The current project is a small-device AI capture appliance. The Flask UI is no longer a general-purpose dashboard with preview panels; it is a touchscreen-first state machine that drives the same shared pipeline used by the CLI and GPIO flows.

Phase 8 adds a typed device configuration layer, hardware-aware camera control resolution, and a standalone diagnostics path for real Raspberry Pi deployment. The current UI is optimized for a `480x320` landscape touchscreen, includes smoother MJPEG live preview, text-only recent-result recall, a health-status bar, and a private offline retry queue for transient AI failures.

## Text Diagram

```text
                         +----------------------+
                         | Terminal CLI         |
                         | main.py              |
                         +----------+-----------+
                                    |
                                    v
          +-------------------------+-------------------------+
          | Device Settings                                    |
          | config/settings.py + config/device.yaml            |
          +-------------------------+-------------------------+
                                    |
                                    v
          +-------------------------+-------------------------+
          | Shared Pipeline                                    |
          | pipeline/runner.py                                 |
          +-------------+-------------------+------------------+
                        |                   |
             +----------v---+     +---------v-----------+
             | camera/      |     | vision/             |
             | capture.py   |     | preprocess.py       |
             +------+-------+     +----------+----------+
                    |                         |
                    v                         v
   data/private/current/      data/private/current/
      captured.jpg               processed.jpg
                    |                         |
                    +------------+------------+
                                 |
                                 v
                        +----------------------+
                        | ai/openai_client.py  |
                        | OpenAI Responses API |
                        +----------+-----------+
                                   |
                    +--------------+--------------+
                    |                             |
                    v                             v
         data/latest_result.txt        system/offline_retry.py
         latest visible answer         data/private/retry_queue.json
         or queued status              data/private/retry/

   +----------------------+                     +--------------------------+
   | GPIO Button          |                     | Flask Touch UI           |
   | gpio/button.py       |                     | app.py                   |
   +----------+-----------+                     +------------+-------------+
              |                                                |
              |                                                v
              |                                      data/ui_state.json
              |                                      data/result_history.json
              |                                      text-only history
              |                                      templates/index.html
              |                                      static/style.css
              |                                      camera/live_preview.py
              +-------------------------> shared pipeline <---------------+

   +----------------------+
   | check_hardware.py    |
   | device diagnostics   |
   +----------------------+
```

## Notes

- `pipeline/runner.py` centralizes capture, preprocess, analyze, and latest-result saving so CLI, Flask, and GPIO behavior stay aligned.
- `system/offline_retry.py` stores retryable AI failures on disk and replays them later from the private processed image copy when connectivity returns.
- `config/settings.py` loads `config/device.yaml` and applies environment overrides so hardware values are no longer hardcoded across entrypoints.
- `hardware/camera_config.py` validates the USB camera request and documents best-effort OpenCV control handling.
- `hardware/device_check.py` runs standalone diagnostics for camera, display, internet, OpenAI API reachability, and GPIO readiness.
- `ai/modes.py` and `ai/context.py` now separate mode metadata from hidden OpenAI request instructions so the device can switch between professional assistant behaviors cleanly.
- `app.py` persists selected mode and current screen in `data/ui_state.json`, tracks recent successful answers in `data/result_history.json`, and renders screen-specific sections from `templates/index.html`.
- `app.py` keeps recent-history storage text-only by default, purges private working media after successful jobs, and exposes a local two-step `Delete All Data` action.
- The `result` and `history_detail` layouts also use a tighter header and health-bar stack so more of the `480x320` screen is reserved for readable assistant output.
- The current touchscreen state machine is `home -> processing -> result/error`, with `history` and `history_detail` screens for reopening recent answers.
- `/capture`, `/capture-analyze`, and `/analyze` are compatibility routes that currently all start the same background `run_capture_analyze` job.
- `camera/live_preview.py` keeps a background preview worker alive and now exposes a browser-friendly MJPEG stream for smoother live framing.
- The current touchscreen layout uses a landscape-first visual system: title, health pills, live preview or answer box, and touch-friendly actions.
- `static/style.css` now targets kiosk-safe `480x320` landscape rendering with visible scrollbars, live-preview emphasis, and classified error styling.
- `history` now behaves as a text-only retention log with status, answer summary, model, duration, and retry metadata.
- `gpio/button.py` can run standalone or call back into Flask through `trigger_action` so the physical button mirrors the touch workflow without overlapping jobs.
