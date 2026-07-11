# Screenshot Guide

Use this guide when filling the four PNG files in this folder.

## `UI_HOME.png`

Recommended state:

- `home` screen
- no selected mode yet
- all five mode cards visible

What should be visible:

- VisionDesk branding in the header
- system health pills: `SYS`, `CPU`, `RAM`, `WIFI`, `CAM`
- clock block
- the five action cards:
  - `READ TEXT`
  - `SUMMARIZE DOCUMENT`
  - `ANALYZE IMAGE`
  - `PROFESSIONAL ASSISTANT`
  - `SOLVE PROBLEM`

Why this matters:

- It shows the kiosk entry point before the capture flow begins.

## `UI_PREVIEW.png`

Recommended state:

- `camera` screen
- one real mode already selected
- live preview running

What should be visible:

- live camera preview
- `CURRENT MODE` pill
- `CAMERA ANALYSIS` area
- `CAPTURE` and `BACK` buttons
- the same health pills and clock style from the home screen

Best mode for consistency:

- `READ TEXT` is usually the easiest demo mode because it produces predictable results.

## `UI_PROCESS.png`

Recommended state:

- `processing` screen during an active job
- ideally during `PREPROCESSING` or `ANALYZING`

What should be visible:

- the large processing card
- mode-specific heading and subtitle
- three progress steps:
  - `Image captured`
  - `Processing`
  - `Result`
- right sidebar with clock, `CURRENT MODE`, and `LIVE STATUS`
- disabled `CAPTURE` and `BACK` controls

Best visual moment:

- Capture while step 1 is complete, step 2 is active, and step 3 is still pending.
- That gives the clearest proof that the pipeline is actually moving.

## `UI_RESULT.png`

Recommended state:

- `result` screen after a successful job
- preview image available
- answer text already rendered

What should be visible:

- captured preview panel on the left
- mode pill
- result title
- answer text area
- `BACK` button

Privacy note:

- If the answer contains sensitive content, replace the sample input before taking the screenshot.

## Capture quality notes

- Keep the screenshots at the natural kiosk ratio when possible.
- Avoid browser UI chrome if you are capturing from the Pi device in fullscreen mode.
- Use a sample subject that looks clean and readable on camera.
- Prefer real health and real processing states over staged edits.
