# Commercial UI upgrade report (historical)

> Historical note: this report predates the corrected 1366 x 768 hardware
> target. Any 1200 x 800 references below describe obsolete captures or the old
> implementation, not the current production resolution.

## Delivered scope

The then-current 1200 x 800 header contained the VisionDesk brand and one concise,
safe status badge. Technical metrics have moved to **Settings -> Device
Health**. Setup has a scrollable, footer-safe content area with focus-aware
autoscroll. Camera capture now pauses at **Review and adjust**: it does not call
the AI service until the user explicitly confirms the rendered image.

The five existing AI workflows remain unchanged. Document, Computer Screen, and
Diagram are separate capture/preprocessing profiles.

## Audit findings

The original shell exposed five technical metric chips in `AppHeader.qml` and
the setup welcome card used a clipped loader/fixed-height grid. The pipeline
combined capture, preprocessing, and OpenAI analysis in one worker, so there
was no safe review point. Existing health snapshots, private-media storage,
logical GPIO actions, OpenCV perspective primitives, mock hardware, and Qt
image providers were reused rather than replaced. The full pre-change audit is
in [ui-commercial-upgrade-plan.md](ui-commercial-upgrade-plan.md).

## Files created

- `camera/capabilities.py` - normalized, best-effort V4L2 and mock capability model.
- `vision/review_processing.py` - crop/rotation mapping, review render path,
  perspective proposal/transform, and non-destructive quality checks.
- `qt_app/capture_review_controller.py` and `qt_app/pipeline_review_worker.py` -
  structured private capture-review session and capture-only worker.
- `qt_app/qml/components/AppStatusBadge.qml`, `CameraGuideOverlay.qml`,
  `FocusScrollHelper.js`, and `ReviewImageCanvas.qml`.
- `qt_app/qml/screens/SettingsScreen.qml`, `DeviceHealthScreen.qml`, and
  `ReviewScreen.qml`.
- `tests/test_global_status.py` and `tests/test_capture_review_processing.py`.
- `docs/ui-commercial-upgrade-plan.md` and this report.

## Principal files modified

- Shell/navigation: `qt_app/qml/Main.qml`, `qt_app/app_controller.py`,
  `qt_app/navigation_controller.py`, and `qt_app/qml/components/AppHeader.qml`.
- Product screens: `CameraScreen.qml`, `SetupScreen.qml`, and `HomeScreen.qml`.
- Backend path: `qt_app/pipeline_controller.py`, `pipeline/runner.py`, and
  `pipeline/__init__.py`.
- Health/images/configuration: `qt_app/health_controller.py`,
  `qt_app/image_provider.py`, `qt_app/main.py`, `config/settings.py`, and
  `config/device.yaml`.
- Support and verification: `system/ui_presenters.py`, `tests/test_qt_app.py`,
  `tools/capture_ui_screenshots.py`, and the two QML preview fixtures.

## Status and Device Health

`resolve_global_status` always chooses one approved label in this order:

1. Critical device error
2. Camera unavailable
3. Wi-Fi unavailable
4. AI service unavailable
5. Setup required
6. Update available
7. Starting
8. Ready

The header never renders raw monitor messages, CPU/RAM percentages, temperature,
paths, stack traces, or credentials. Device Health reads the established health
snapshot on its normal refresh interval, adds a manual Refresh action, and
shows plain-language cards for available CPU temperature, memory, storage,
connection, camera, capability, version, and update data. It does not invent a
CPU-use value when the existing monitor does not provide one.

## Camera review pipeline and privacy

```text
original private frame
  -> optional rotation
  -> normalized crop in original-image coordinates
  -> optional accepted perspective correction
  -> optional enhancement
  -> quality validation
  -> confirmed private image
  -> AI request
```

The review canvas supports move/resize crop handles, Reset Crop, 90-degree
rotation, display zoom, Retake, and Confirm and Analyze. A preview zoom region
on the live screen becomes the initial capture crop, so it is not merely visual
scaling. Crop bounds and a minimum size are enforced. The displayed confirmed
image is the file passed to `run_analyze_confirmed`; the capture-only worker has
no OpenAI call. Retake, cancellation, reset, error, and terminal outcomes clean
the review session's private media under the existing retention policy.

Image warnings are heuristic and non-blocking: Laplacian-variance sharpness,
mean brightness, clipped-bright-region glare, very small crops, and incomplete
document boundaries. Thresholds and profile defaults are in device
configuration. Perspective correction proposes a document quadrilateral and is
only applied after the user accepts it; failure falls back to manual crop.

## Accessibility and controls

Setup uses a `Flickable` whose content height follows real implicit content and
whose bottom padding clears the fixed footer. `FocusScrollHelper` scrolls only
when a focused descendant would be hidden. The new camera/review/settings
screens retain logical keyboard/GPIO actions, visible focus states, large touch
targets, expected Back behavior, and a busy/double-submit guard. Unsupported
autofocus or exposure capabilities display `Not supported by this camera` and
are not represented as silent actions.

## Dependencies

No new package is required. OpenCV is used where available for document
quadrilateral detection and perspective transforms. The established Pillow
dependency provides a safe review-render fallback for crop/rotation/enhancement
when OpenCV is unavailable.

## Tests and commands

Automated coverage was added for safe status priority, crop/rotation mapping,
minimum crop bounds, render order, quality heuristics, perspective fallback,
and explicit mock capability limits. The Qt app test now also proves that a
capture does not create history until Review confirmation and that a second
confirm is ignored.

Commands executed:

```powershell
& .\.venv\Scripts\python.exe -m pytest -q tests/test_capture_review_processing.py tests/test_global_status.py
& .\.venv\Scripts\python.exe -m pytest -q tests/test_qt_app.py
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe tools\capture_ui_screenshots.py --output-dir docs\images\app-screens
```

Result: `224 passed, 5 skipped, 16 subtests passed` in 15.37 seconds. The
focused new-review/status/Qt set also passed `48` tests.

## Screenshots

The historical portfolio-safe mock screenshots were 1200 x 800 in
`docs/images/app-screens/`. The set includes the contact sheet plus:

- initial setup, compact device-check progress, completed setup checks, and setup scrolled (`01-*`), Ready and Wi-Fi unavailable headers;
- Device Health;
- Document and Computer Screen live-preview guides;
- Review, crop, perspective-preview, quality-warning, and unsupported-control
  states;
- Processing, Result, History, History Detail, and Error.

The screenshot script only replaces its own numbered images so pre-existing
documentation captures remain intact. The warning/capability screenshots use
clearly simulated mock fixtures; they do not represent a real customer's image
or physical-camera test.

## Known limitations and Raspberry Pi acceptance checklist

- V4L2 control discovery is best-effort; libcamera-only or unusual USB drivers
  must be checked on the deployed Raspberry Pi.
- The implementation detects and reports autofocus/exposure capability. It does
  not yet offer arbitrary per-driver focus/exposure adjustment values because
  V4L2 control ranges and semantics vary.
- Perspective and glare warnings are heuristics, not guarantees. Validate their
  thresholds on the intended document, monitor, and lighting conditions.
- This delivery used mock hardware and offscreen Qt rendering. It does not claim
  physical autofocus, exposure, camera negotiation, GPIO focus navigation, or
  real-world perspective correction has been production-validated.

Current manual acceptance on the Pi must cover: 1366 x 768 kiosk layout at default
and larger text; long SSIDs/messages; all setup outcomes; touch, keyboard, and
GPIO navigation; each capture profile; retake/crop/rotate/zoom/confirm; an
unsupported camera; dark, blurry, glare-heavy, and skewed subjects; Wi-Fi and
AI outage paths; privacy cleanup; history; reset; install/update; and mock mode.
