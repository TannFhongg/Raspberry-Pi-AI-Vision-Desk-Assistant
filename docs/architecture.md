# Architecture

## Overview

The current project behaves like a small-device AI capture appliance, not a generic web dashboard. `app.py`, `qt_app.main`, `main.py`, and the GPIO trigger all feed into the same shared pipeline and reuse the same typed device settings.

Current product direction:

- parallel UI migration with Flask on `127.0.0.1:5000` and a native Qt runtime under `qt_app/`
- `1200x800` landscape touchscreen UI
- `1920x1080` still capture plus `640x360` lighter live preview
- private working media, text-only history, and offline retry for transient AI failures
- shared presenter, setup, and result-history helpers for both UI stacks

## Text Diagram

```text
                              +----------------------+
                              | Device Settings      |
                              | config/settings.py   |
                              | config/device.yaml   |
                              +----------+-----------+
                                         |
                     +-------------------+-------------------+------------------+
                     |                   |                   |                  |
                     v                   v                   v                  v
          +----------------------+  +----------------------+  +----------------------+  +----------------------+
          | Terminal CLI         |  | Flask Kiosk UI       |  | Native Qt UI         |  | GPIO Controls        |
          | main.py              |  | app.py               |  | qt_app.main          |  | hardware/button.py   |
          +----------+-----------+  +----------+-----------+  +----------+-----------+  | hardware/led.py      |
                     |                         |                         |              | test_gpio_button.py  |
                     |                         v                         v              +----------+-----------+
                     |              +----------------------+  +----------------------+             |
                     |              | Shared UI Helpers    |  | Live Preview         |<------------+
                     |              | system/ui_presenters |  | camera/live_preview  |
                     |              | system/setup_flow    |  +----------+-----------+
                     |              | system/result_history|             |
                     |              +----------+-----------+             |
                     |                         |                         |
                     +-------------------------+-------------------------+
                                               |
                                               v
                                    +----------------------+
                                    | Shared Pipeline      |
                                    | pipeline/runner.py   |
                                    +-----+-----------+----+
                                          |           |
                                          |           |
                                          v           v
                                +---------+--+   +----+------------------+
                                | camera/    |   | vision/               |
                                | capture.py |   | preprocess.py         |
                                +------+-----+   +----+------------------+
                                       |               |
                                       v               v
                             data/private/current/   debug/
                             captured-*.jpg          corrected.jpg, etc.
                                       |               |
                                       +-------+-------+
                                               |
                                               v
                                      +----------------------+
                                      | ai/openai_client.py  |
                                      | OpenAI Responses API |
                                      +----------+-----------+
                                                 |
                           +---------------------+----------------------+
                           |                                            |
                           v                                            v
                 data/latest_result.txt                    system/offline_retry.py
                 data/result_history.json                  data/private/retry_queue.json
                 data/ui_state.json                        data/private/retry/
                 data/health_status.json

                 +----------------------+                  +--------------------------+
                 | Background Services  |                  | Qt Image Providers       |
                 | system/health.py     |                  | qt_app/image_provider.py |
                 | system/logging.py    |                  +--------------------------+
                 | check_hardware.py    |
                 +----------------------+
```

## Notes

- `pipeline/runner.py` is the source of truth for capture, preprocess, analyze, and result-writing behavior.
- `system/ui_presenters.py`, `system/setup_flow.py`, and `system/result_history.py` are now the canonical behavior-sharing layer between Flask and Qt.
- `camera/live_preview.py` keeps the kiosk preview responsive, supports MJPEG streaming for Flask, and also feeds the native Qt image-provider path.
- `vision/preprocess.py` enables the advanced screen/document path automatically for text-heavy modes when `SCREEN_OPTIMIZATION=auto`.
- `ai/openai_client.py` wraps the OpenAI Responses API with explicit timeout, retry, and retryable-error classification.
- `app.py` persists UI state locally, exposes `/api/ui-state` and `/api/health` for the Flask surface, stores text-only result history, and intentionally disables same-image reanalysis under the privacy-first retention model.
- `qt_app.main` covers `setup`, `home`, `camera`, `processing`, `result`, and `error` without opening an HTTP port for UI state or health polling during normal operation.
- `system/offline_retry.py` keeps copied processed images only for retryable failures and replays them later from private storage.
- `system/health.py` writes CPU, memory, network, and camera snapshots, and defers intrusive camera probes while preview or capture is active.
- `hardware/status.py` provides the shared device state machine: `READY -> MODE_SELECTED -> CAPTURING -> PROCESSING -> DONE | ERROR`.
- `hardware/button.py` and `hardware/led.py` mirror the same state machine so the physical controls behave like the touchscreen flow instead of a separate code path.
