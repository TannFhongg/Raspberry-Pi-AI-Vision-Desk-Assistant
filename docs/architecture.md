# Architecture

## Overview

The Raspberry Pi AI Vision Desk Assistant is built as a modular local pipeline that can be triggered from three entrypoints:

- terminal CLI
- Flask web UI
- GPIO button

## Text Diagram

```text
                +----------------------+
                |   Terminal CLI       |
                |  main.py             |
                +----------+-----------+
                           |
                +----------v-----------+
                |     Flask Web UI     |
                |      app.py          |
                +----------+-----------+
                           |
                +----------v-----------+
                |    GPIO Button       |
                | test_gpio_button.py  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Shared Pipeline      |
                | pipeline/runner.py   |
                +----+-----------+-----+
                     |           |
          +----------v--+     +--v----------------+
          | camera/     |     | vision/           |
          | capture.py  |     | preprocess.py     |
          +----------+--+     +--+----------------+
                     |           |
                     v           v
             static/captured.jpg static/processed.jpg
                           |
                           v
                +----------------------+
                | ai/openai_client.py  |
                | OpenAI Vision API    |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Latest Result File   |
                | data/latest_result.txt
                +----------------------+
```

## Notes

- `camera/capture.py` supports Picamera2 first with OpenCV fallback for USB webcams
- `vision/preprocess.py` keeps preprocessing intentionally light
- `pipeline/runner.py` centralizes capture, preprocess, analyze, and result saving
- `app.py` uses session + PRG for a simple small-screen-friendly dashboard
- `gpio/button.py` listens for a physical press and prevents overlapping runs with a busy flag
