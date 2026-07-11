# Demo Checklist

## Before Demo

- Confirm Raspberry Pi 5 is powered on and connected to the network
- Confirm the camera is connected and working
- Confirm the push button is wired to the configured GPIO pin and GND
- Confirm `.env` contains a valid `OPENAI_API_KEY`
- Run `python check_hardware.py`
- Confirm `data/latest_result.txt`, `data/ui_state.json`, `data/result_history.json`, and `data/private/retry_queue.json` are writable
- Start `python app.py` and open `http://127.0.0.1:5000`
- If demoing the small display, use the landscape device profile such as `UI_SCREEN_WIDTH=480 UI_SCREEN_HEIGHT=320 UI_DISPLAY_ORIENTATION=landscape`
- Preselect a useful demo mode such as `Read Text` or `Solve Problem`

## Demo Flow

- Show the Raspberry Pi hardware, camera, button, and attached display or browser
- Show the production small-screen home layout with live camera preview, selected mode, `Click Button to Capture`, and the health pills
- Change mode and choose the task that matches the demo image
- Return to the live preview state and frame the subject
- Trigger `Capture`
- Narrate the processing screen as it moves through capture, preprocessing, AI analysis, and the `Thinking...` state
- Show the final answer on the result screen and scroll the answer box if the response is long
- Open `Recent Results` to show that a successful scan can be reopened almost instantly
- Open one saved entry from `Recent Results` to show the text-only history detail and retention metadata
- Use `Capture Again` to show the repeatable flow
- Press the GPIO button from the home screen to demonstrate the same shared pipeline without touch input
- Show the updated `data/latest_result.txt`
- If useful for the demo, briefly explain that transient network or OpenAI outages are now queued automatically for retry instead of being lost immediately
- If asked about privacy, point out that working images now live only in `data/private/` and are purged after successful jobs

## Wrap-up

- Explain the shared pipeline: capture -> preprocess -> OpenAI Vision -> readable result
- Explain that CLI, touchscreen UI, and GPIO all reuse the same pipeline runner
- Mention that the current product direction is optimized for kiosk-style `480x320` landscape touchscreen use
- Mention the smoother MJPEG preview, the text-only recent-results recall path, private media retention, and the offline retry queue as production-minded improvements
