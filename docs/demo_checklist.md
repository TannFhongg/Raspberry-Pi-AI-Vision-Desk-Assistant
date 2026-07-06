# Demo Checklist

## Before Demo

- Confirm Raspberry Pi 5 is powered on and connected to the network
- Confirm camera is connected and working
- Confirm push button is wired to GPIO17 and GND
- Confirm `.env` contains `OPENAI_API_KEY`
- Confirm Flask app can start and `data/latest_result.txt` is writable

## Demo Flow

- Show the Raspberry Pi hardware, camera, and push button
- Show the Flask web UI in a browser
- Capture a document image from the UI
- Analyze the image from the UI
- Show the AI answer in the dashboard
- Press the GPIO button and trigger the full pipeline
- Show the updated `data/latest_result.txt`
- Show the GitHub repo structure and project organization

## Wrap-up

- Explain the full pipeline: capture -> preprocess -> OpenAI Vision -> result
- Explain how Flask UI, terminal CLI, and GPIO all share the same pipeline runner
- Mention future improvements such as background jobs, richer UI, and offline logging
