# Architecture

## Overview

The current project is a small-device AI capture appliance. The Flask UI is no longer a general-purpose dashboard with preview panels; it is a touchscreen-first state machine that drives the same shared pipeline used by the CLI and GPIO flows.

## Text Diagram

```text
                         +----------------------+
                         | Terminal CLI         |
                         | main.py              |
                         +----------+-----------+
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
```

## Notes

- `pipeline/runner.py` centralizes capture, preprocess, analyze, and latest-result saving so CLI, Flask, and GPIO behavior stay aligned.
- `app.py` persists selected mode and current screen in `data/ui_state.json`, then renders a screen-specific section from `templates/index.html`.
- The current touchscreen state machine is `home -> processing -> result/error`, with a separate `mode_select` screen for choosing the active AI mode.
- `/capture`, `/capture-analyze`, and `/analyze` are compatibility routes that currently all start the same background `run_capture_analyze` job.
- `static/style.css` mixes fixed-position Figma-derived layouts for `home` and `mode_select` with responsive dark card layouts for `processing`, `result`, and `error`.
- `gpio/button.py` can run standalone or call back into Flask through `trigger_action` so the physical button mirrors the touch workflow without overlapping jobs.
