# UI commercial upgrade plan

## Audit scope and findings

The production UI is a PySide6/Qt Quick application rooted at
`qt_app/qml/Main.qml`.  It renders into a fixed 1200 x 800 design canvas and
uniformly scales that canvas when fullscreen.  `AppController` is the QML
facade.  It composes dedicated setup, camera, health, GPIO, history, and
pipeline controllers over `VisionDeskRuntime`.

### Relevant implementation

| Area | Current files | Finding |
| --- | --- | --- |
| App shell and theme | `qt_app/qml/Main.qml`, `qt_app/qml/theme/Theme.qml` | The shell reserves a 20 px outer margin, a global header and divider, then gives screens the remaining height. |
| Global header | `qt_app/qml/components/AppHeader.qml`, `SetupMetricChip.qml`, `qt_app/health_controller.py`, `system/ui_presenters.py` | `AppHeader` repeats five technical health chips (SYS, CPU, RAM, Wi-Fi, Camera). `HealthSummaryBuilder` is the shared source of those data. |
| Setup | `qt_app/qml/screens/SetupScreen.qml`, `qt_app/setup_controller.py` | Setup puts a loader inside a clipped `Item` in a fixed card. The welcome/device-check step uses a fixed 182 px lead and a fill-height three-by-two grid. Its lower cards can be hidden because the footer consumes the rest of the screen and the body cannot scroll. |
| Camera and capture | `qt_app/qml/screens/CameraScreen.qml`, `qt_app/camera_controller.py`, `camera/live_preview.py`, `camera/capture.py` | Camera has a live image provider and a direct Capture action. It has no capture profile, zoom region, review state, crop canvas, or capability model. |
| Processing/AI | `qt_app/pipeline_controller.py`, `pipeline/runner.py`, `vision/preprocess.py`, `ai/openai_client.py` | The active worker calls `run_capture_analyze`, which captures, preprocesses, then calls OpenAI in a single job. The final request is currently sent before any human review. |
| Perspective support | `vision/perspective.py`, `vision/screen_detect.py` | Reusable four-point transform primitives exist, but no user-visible document boundary proposal/review flow exists. |
| Device health | `system/health.py`, `qt_app/health_controller.py` | A shared monitor produces CPU temperature, memory, Wi-Fi and camera snapshots. It is already rate-limited by configured monitor and camera-probe intervals, but it has no dedicated user-facing health screen. |
| Navigation | `qt_app/qml/Main.qml`, `qt_app/gpio_controller.py`, screen `handleNavigation()` methods | Keyboard arrows/Enter/Escape and GPIO are mapped to logical actions. Each screen implements its own navigation index. Setup has no logical focus handler/autoscroll; native input fields remain touch-first. |
| Mock/runtime/config | `qt_app/runtime.py`, `qt_app/mock_backend.py`, `config/settings.py`, `config/device.yaml` | Mock mode has a live image and a mock health snapshot. Camera settings have static preferences but no detected capability abstraction. Retention already places working media under the private data root. |
| Tests and UI previews | `tests/`, `test_*.py`, `tools/ui_preview/`, `tools/capture_ui_screenshots.py`, `docs/images/app-screens/` | Backend coverage exists for preview coordination, preprocessing, perspective geometry, status presenters, setup, pipeline and deployment. Existing screenshot tooling renders 1200 x 800 QML preview fixtures. |

## Existing layout and workflow

The current normal flow is:

```text
Home mode selection -> Camera live preview -> Capture + preprocess + OpenAI -> Processing -> Result
```

The target flow changes the middle section to:

```text
Home mode selection -> Live preview -> Capture -> Review and adjust -> Confirm -> Processing -> Result
```

The review screen becomes the only transition that may start an OpenAI request.
The selected mode remains the existing canonical five-mode model. Capture
profiles are an independent `document`, `computer_screen`, or `diagram`
setting.

## Status model proposal

Retain `HealthSummaryBuilder` as the single source for health inputs. Add a
small presenter-level priority resolver which emits one safe `text`, `tone`,
and `detail_available` value. Its ordered states are:

1. Critical device error
2. Camera unavailable
3. Wi-Fi unavailable
4. AI service unavailable
5. Setup required
6. Update available
7. Starting / connecting
8. Ready

`AppHeader.qml` will use this one status badge instead of repeating metrics.
It must never expose raw monitor text, values, exception text, or paths. CPU,
memory, temperature and camera metadata are retained for Device Health only.

## Reusable UI components proposed

- `AppStatusBadge.qml`: compact dot, approved text, keyboard/GPIO focus state,
  and a safe accessible label.
- `ScrollablePage.qml`: a card/body/footer arrangement using `ScrollView` and
  bottom content padding; exposes `ensureVisible(item)` for logical focus.
- `FocusScrollHelper.js`: maps a focused item's coordinates into a Flickable
  and moves only enough to retain a margin.
- `CaptureProfileSelector.qml`, `CameraGuideOverlay.qml`, and
  `ReviewImageCanvas.qml`: reusable camera-profile, safe-area/thirds guide,
  and image/crop/zoom rendering primitives.
- `DeviceHealthCard.qml`: consistent health state card used by the Device
  Health grid.

## Backend changes required

1. Add a structured capture-session model/controller with states `idle`,
   `previewing`, `capturing`, `captured`, `reviewing`, `adjusting`,
   `validating`, `ready_to_submit`, `submitting`, and `error`.
2. Split the current capture/analyze worker into capture-for-review and
   submit-confirmed-image paths. A session receives unique private paths and
   cleans them on retake, abandon, reset, and completion according to retention
   policy.
3. Add `vision/review_processing.py` for crop/rotation/zoom-region coordinate
   mapping, non-destructive render processing, quality heuristics, document
   quadrilateral detection, and safely optional perspective transformation.
4. Add `camera/capabilities.py` to probe the active backend once, retain only
   verified controls, and expose a normalized capability model. Unsupported
   controls must be explicitly disabled. Mock mode will use a deterministic
   simulated model.
5. Extend `HealthController` from the existing monitor snapshot rather than
   adding a second polling service. Device Health will refresh on demand and
   on the existing timer.
6. Extend typed configuration for capture-profile defaults and quality
   thresholds. No threshold values will be scattered in QML or controller
   code.

## Risks and regression-sensitive areas

- Preview pause/release serializes camera ownership; capture for review must
  retain this contract and resume preview after retake/error.
- Offline retry currently persists a preprocessed image. The confirmed image,
  not the original frame, must be the only retry media.
- Result/history retention and reset paths must clean review session files
  without touching configured credentials or unrelated private data.
- Capability probing cannot assume OpenCV/V4L2 controls are supported by all
  USB cameras or Raspberry Pi camera stacks.
- The fixed design canvas must remain usable at exactly 1200 x 800 and must
  still scale in kiosk mode. Larger text and translations require wrap/layout
  rather than elision of actionable text.
- Existing GPIO action routing works through screen-specific handlers. New
  review/settings handlers must preserve Back behavior and inhibit duplicate
  submission while busy.
- Existing installation, update, release checks, mock hardware mode, and
  current backend tests are release-sensitive and must remain passing.

## Test plan

Automated tests will cover status priority/safe text, Device Health data
presentation, setup scroll/focus helper math, session transitions, crop and
rotation mapping, zoom-to-capture mapping, processing order, quality metrics,
perspective fallback, capability states, mock capabilities, temporary session
cleanup, no AI call before confirmation, confirmed image identity, and
double-submit prevention. Existing test modules remain part of the regression
run.

Visual verification will use the established QML preview/capture tooling at
1200 x 800. It will produce safe fixture screenshots for the requested header,
setup, health, preview, review/crop/perspective/warning, and unsupported-control
states. Manual hardware validation remains required for physical autofocus,
exposure, camera-driver control semantics, GPIO focus navigation, and
real-world document detection.
