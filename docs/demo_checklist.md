# Demo Checklist

## Before Demo

- Confirm Raspberry Pi 5 is powered on and connected to the network
- Confirm the camera is connected and working
- Confirm the push button is wired to the configured GPIO pin and GND
- Confirm `.env` contains a valid `OPENAI_API_KEY`
- Run `python check_hardware.py`
- Confirm `data/latest_result.txt` and `data/ui_state.json` are writable
- Start `python app.py` and open `http://127.0.0.1:5000`
- Preselect a useful demo mode such as `Read Text` or `Solve Problem`

## Demo Flow

- Show the Raspberry Pi hardware, camera, button, and attached display or browser
- Show the minimal home screen with only `Mode` and `Capture`
- Open the mode picker and choose the task that matches the demo image
- Return to home and tap `Capture`
- Narrate the processing screen as it moves through capture, preprocessing, AI analysis, and answer preparation
- Show the final answer on the result screen
- Use `Back` or `New Capture` to show the repeatable flow
- Press the GPIO button from the home screen to demonstrate the same shared pipeline without touch input
- Show the updated `data/latest_result.txt`

## Wrap-up

- Explain the shared pipeline: capture -> preprocess -> OpenAI Vision -> readable result
- Explain that CLI, touchscreen UI, and GPIO all reuse the same pipeline runner
- Mention that the current UI is intentionally minimal and optimized for kiosk-style small-screen use
- Mention follow-up ideas such as result history, richer preview screens, or offline logging
