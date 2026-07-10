# Architecture

## Overview

The current project is a small-device AI capture appliance. The Flask UI is no longer a general-purpose dashboard with preview panels; it is a touchscreen-first state machine that drives the same shared pipeline used by the CLI and GPIO flows.

Phase 8 adds a typed device configuration layer, hardware-aware camera control resolution, and a standalone diagnostics path for real Raspberry Pi deployment. The current UI is now optimized for a `480x320` landscape touchscreen, includes smoother MJPEG live preview, recent-result recall, a health-status bar, and an offline retry queue for transient AI failures.

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
           static/captured.jpg      static/processed.jpg
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
         latest visible answer         data/offline_retry_queue.json
         or queued status              data/offline_retry/

   +----------------------+                     +--------------------------+
   | GPIO Button          |                     | Flask Touch UI           |
   | gpio/button.py       |                     | app.py                   |
   +----------+-----------+                     +------------+-------------+
              |                                                |
              |                                                v
              |                                      data/ui_state.json
              |                                      data/result_history.json
              |                                      data/result_history_assets/
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
- `system/offline_retry.py` stores retryable AI failures on disk and replays them later from the processed image copy when connectivity returns.
- `config/settings.py` loads `config/device.yaml` and applies environment overrides so hardware values are no longer hardcoded across entrypoints.
- `hardware/camera_config.py` resolves autofocus-capable Picamera2 modes, best-fit still resolutions, and best-effort OpenCV controls.
- `hardware/device_check.py` runs standalone diagnostics for camera, display, internet, OpenAI API reachability, and GPIO readiness.
- `ai/modes.py` and `ai/context.py` now separate mode metadata from hidden OpenAI request instructions so the device can switch between professional assistant behaviors cleanly.
- `app.py` persists selected mode and current screen in `data/ui_state.json`, tracks recent successful answers in `data/result_history.json`, and renders screen-specific sections from `templates/index.html`.
- `app.py` also keeps a RAM thumbnail cache for history cards and supports analyze-only jobs that reuse the same saved image under another mode.
- The hardware mode-button handler now branches by screen context: it still selects a mode from `home`, but on a saved `result` it can trigger same-image re-analysis instead of forcing a recapture.
- The touchscreen `result` view is now intentionally answer-first: the touch re-analysis panel and the GPIO helper text were removed there so the answer box keeps more vertical room, while `history_detail` still exposes the touch re-analysis controls.
- The `result` and `history_detail` layouts also use a tighter header and health-bar stack so more of the `480x320` screen is reserved for readable assistant output.
- The current touchscreen state machine is `home -> processing -> result/error`, with `history` and `history_detail` screens for reopening recent answers.
- `/capture`, `/capture-analyze`, and `/analyze` are compatibility routes that currently all start the same background `run_capture_analyze` job.
- `camera/live_preview.py` keeps a background preview worker alive and now exposes a browser-friendly MJPEG stream for smoother live framing.
- The current touchscreen layout uses a landscape-first visual system: title, health pills, live preview or answer box, and touch-friendly actions.
- `static/style.css` now targets kiosk-safe `480x320` landscape rendering with visible scrollbars, live-preview emphasis, and classified error styling.
- `history` now behaves more like a visual gallery than a plain text log because each entry can render a cached thumbnail in RAM.
- `gpio/button.py` can run standalone or call back into Flask through `trigger_action` so the physical button mirrors the touch workflow without overlapping jobs.
