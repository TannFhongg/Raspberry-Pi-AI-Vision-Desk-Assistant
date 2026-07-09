# Architecture

## Overview

The current project is a small-device AI capture appliance. The Flask UI is no longer a general-purpose dashboard with preview panels; it is a touchscreen-first state machine that drives the same shared pipeline used by the CLI and GPIO flows.

Phase 8 adds a typed device configuration layer, hardware-aware camera control resolution, and a standalone diagnostics path for real Raspberry Pi deployment. Phase 10 layers on a production portrait touchscreen UI optimized for `320x480` kiosk use.

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
                    v
           +----------------------+
           | hardware/            |
           | camera_config.py     |
           | device_check.py      |
           +----------------------+
                    |
                    v                         v
           static/captured.jpg      static/processed.jpg
                        \                 /
                         \               /
                          \             /
                           v           v
                        +----------------------+
                        | ai/openai_client.py  |
                        | OpenAI Responses API |
                        +----------+-----------+
                                   |
                                   v
                        +----------------------+
                        | data/latest_result   |
                        | answer / error text  |
                        +----------------------+

   +----------------------+                     +--------------------------+
   | GPIO Button          |                     | Flask Touch UI           |
   | gpio/button.py       |                     | app.py                   |
   +----------+-----------+                     +------------+-------------+
              |                                                |
              |                                                v
              |                                      data/ui_state.json
              |                                      templates/index.html
              |                                      static/style.css
              +-------------------------> shared pipeline <---------------+

   +----------------------+
   | check_hardware.py    |
   | device diagnostics   |
   +----------------------+
```

## Notes

- `pipeline/runner.py` centralizes capture, preprocess, analyze, and latest-result saving so CLI, Flask, and GPIO behavior stay aligned.
- `config/settings.py` loads `config/device.yaml` and applies environment overrides so hardware values are no longer hardcoded across entrypoints.
- `hardware/camera_config.py` resolves autofocus-capable Picamera2 modes, best-fit still resolutions, and best-effort OpenCV controls.
- `hardware/device_check.py` runs standalone diagnostics for camera, display, internet, OpenAI API reachability, and GPIO readiness.
- `ai/modes.py` and `ai/context.py` now separate mode metadata from hidden OpenAI request instructions so the device can switch between professional assistant behaviors cleanly.
- `app.py` persists selected mode and current screen in `data/ui_state.json`, then renders a screen-specific section from `templates/index.html`.
- The current touchscreen state machine is `home -> processing -> result/error`, with a separate `mode_select` screen for choosing the active AI mode.
- `/capture`, `/capture-analyze`, and `/analyze` are compatibility routes that currently all start the same background `run_capture_analyze` job.
- The Phase 10 touchscreen layout uses one portrait-first visual system: title, status strip, large content box, and touch-friendly `Capture`, `Mode`, and `Retry` actions.
- `static/style.css` now targets kiosk-safe `320x480` portrait rendering with large fonts, visible scrollbars, and classified error styling rather than the older Figma-derived fixed layout.
- `gpio/button.py` can run standalone or call back into Flask through `trigger_action` so the physical button mirrors the touch workflow without overlapping jobs.
