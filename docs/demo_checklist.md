# Demo Checklist

## Before Demo

- Confirm the Raspberry Pi 5 is powered on, networked, and using the expected `.env`
- Confirm the USB webcam is connected and visible to OpenCV
- Confirm the main capture button, five mode buttons, and optional back button are wired to the configured GPIO pins
- Run `python check_hardware.py`
- If you are validating software before the live demo, run `python -m pytest -q`
- Confirm `http://127.0.0.1:5000` loads and the home screen matches the `480x320` landscape layout
- Confirm the live preview is updating through `/camera/live-stream.mjpg`
- Confirm `data/latest_result.txt`, `data/ui_state.json`, `data/result_history.json`, and `data/private/retry_queue.json` are writable
- Preselect a useful demo mode such as `Read Text` or `Solve Problem`
- Have one text-heavy sample and one non-text sample ready

## Demo Flow

- Show the Raspberry Pi hardware, webcam, touchscreen, and button panel
- Start on the `home` screen without a selected mode to show the mode picker and health pills
- Choose a mode and show the `MODE_SELECTED` idle state with the live preview
- Frame the subject and trigger `Capture`
- Narrate the progress screen as it moves through `Capturing...`, `Processing...`, and `Thinking...`
- Show the final answer in the result view and scroll the answer area if the reply is long
- Open `Recent Results` to show that successful scans are retained as text-only history
- Open one saved history entry to show the detail view without storing user images
- Trigger a second run with the physical capture button to show that GPIO and touch reuse the same shared pipeline
- If the back button is wired, press it from an idle screen to return to mode selection
- Mention that retryable OpenAI failures can be queued automatically instead of being lost
- Mention that working images stay inside `data/private/` and are purged after successful jobs by default

## Wrap-up

- Explain the shared flow: camera capture -> preprocess -> OpenAI Vision -> readable result
- Explain that CLI, Flask, and GPIO all share `pipeline/runner.py`
- Call out the production-minded improvements: live MJPEG preview, health bar, text-only recent results, offline retry, rotating logs, and delete-all-data controls
- Be explicit that the current product profile is a local-only `480x320` landscape kiosk device, not a general-purpose cloud dashboard
