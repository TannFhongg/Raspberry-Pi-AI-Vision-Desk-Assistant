# Processing Screen Context

This file captures the most important context behind `UI_PROCESS.png`.

## Why this screen matters now

The active goal objective for the repository is centered on the `Processing` screen.

Current expectation:

- follow the Figma direction closely
- keep the screen kiosk-friendly at `1200x800`
- show real pipeline progress
- continue automatically to the result screen when done

## Current processing steps

The UI currently uses three visual progress steps:

1. `Image captured`
2. `Processing`
3. `Result`

## Backend progress states

The current pipeline-facing states include:

- `CAPTURING`
- `PREPROCESSING`
- `ANALYZING`
- `RETRY_QUEUED`
- `DONE`
- `ERROR`

Current short status copy in [`app.py`](../app.py):

- `CAPTURING` -> `Capturing image...`
- `PREPROCESSING` -> `Preprocessing image...`
- `ANALYZING` -> `Sending to AI...`
- `RETRY_QUEUED` -> `Saved for retry`
- `DONE` -> `Result ready`
- `ERROR` -> `Error`

## Mode-specific processing titles

The processing card title and subtitle change with the selected mode:

- `Read Text` -> `Reading Text` / `Reading printed text`
- `Summarize Document` -> `Summarizing Document` / `Analyzing structure and text`
- `Analyze Image` -> `Analyzing Image` / `Understanding the captured image`
- `Professional Assistant` -> `Professional Assistant` / `Organizing a professional response`
- `Solve Problem` -> `Solving Problem` / `Working through the problem step by step`

## Recommended screenshot timing

The strongest `UI_PROCESS.png` capture is usually during `PREPROCESSING` or `ANALYZING`.

That moment typically shows:

- step 1 complete
- step 2 active
- step 3 pending

This is the clearest visual proof that the app is running a real pipeline instead of a static loading page.

## What should stay true in the screenshot

- VisionDesk header is visible
- health pills use real health data
- current mode matches the actual selected mode
- live status text is believable for the current stage
- `CAPTURE` and `BACK` are disabled during the active run

## Relevant source files

- [`app.py`](../app.py)
- [`templates/index.html`](../templates/index.html)
- [`static/style.css`](../static/style.css)
