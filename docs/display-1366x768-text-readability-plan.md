# 1366 x 768 display and text-readability migration plan

## Audit scope

VisionDesk is a PySide6 6.11 / Qt Quick Controls application rooted at
`qt_app/qml/Main.qml`. The audit covered the QML shell, shared components, every
screen, Python startup and controllers, typed configuration, camera/review image
mapping, mock rendering tools, automated tests, installer/deployment scripts,
existing screenshots, and project documentation.

## Findings and affected files

| Area | Files | Audit finding and required change |
| --- | --- | --- |
| Window and shell | `qt_app/qml/Main.qml`, `qt_app/main.py`, `qt_app/runtime.py`, `config/device.yaml` | The active shell uses a fixed 1200 x 800 `designCanvas` and scales the complete tree to the fullscreen viewport. Windowed mode also defaults to 1200 x 800. Replace this with a direct, responsive 1366 x 768 window and actual fullscreen screen geometry. |
| Metrics and type | `qt_app/qml/theme/Theme.qml`, all `qt_app/qml/components/*.qml`, all `qt_app/qml/screens/*.qml` | Color and spacing tokens exist, but font sizes, line heights, footer/body heights, panel widths, and many control dimensions are scattered. Add shared display metrics and typography roles, then migrate screens to responsive fill/minimum/preferred sizing. |
| Fonts | `qt_app/qml/fonts/`, `Theme.qml`, `qt_app/main.py`, `install.sh` | Body text currently uses bundled Roboto; headings and branding use bundled Roboto Condensed. Many long labels use the condensed face. Prefer Noto Sans, then Inter, DejaVu Sans, and the legal bundled Roboto fallback for body text. Keep Roboto Condensed only for the brand and short large headings. Install and verify Noto Sans through the Raspberry Pi installer without making startup depend on it. |
| Text rendering | Most QML screens/components | Rendering is inconsistent: many static items force `Text.NativeRendering`, while others use Qt's default. There is no shared hinting policy. Add an `auto`/`qt`/`native` policy, default safely to Qt rendering, use vertical hinting, and apply it through shared text components and rich-result text. Native rendering remains an opt-in hardware comparison because transformed/animated text can rasterize poorly. |
| Accessibility | `config/settings.py`, `config/device.yaml`, `qt_app/app_controller.py`, `SettingsScreen.qml` | No persisted text-size preference exists. Add Standard, Large, and Extra Large roles that change typography tokens only; do not scale the UI or reduce touch targets. Scrollable content must absorb larger text. |
| Header/footer | `AppHeader.qml`, `AppStatusBadge.qml`, screen footer rows | The header is responsive horizontally but inherits the scaled canvas. Footers use repeated button sizes and screen-specific fixed body heights. Use shared header/footer/touch metrics and fill-height bodies so content cannot sit behind navigation. |
| Setup | `SetupScreen.qml`, setup components, `tools/ui_preview/SetupWizardPreview.qml` | Setup correctly uses a `Flickable` and does not fabricate pending diagnostic cards, but its body/footer reserve and many card sizes were tuned for 800 px. Retain focus autoscroll, use the 768 px body height, and keep footer clearance based on metrics. |
| Home/dialogs | `HomeScreen.qml`, `ModeCard.qml` | Five mode cards already use a 3-column grid, but the card container is fixed at 430 px and dialogs contain many fixed widths/heights. Use the wider viewport, fill available height, readable body type, title/sentence case actions, scrolling for large text, and unchanged logical navigation order. |
| Camera | `CameraScreen.qml`, `CameraGuideOverlay.qml`, `camera/live_preview.py` | Camera images use `PreserveAspectFit`, but the screen uses a 480 px fixed viewport and 300 px side panel. Preview-zoom touch mapping divides by the full frame, not the actual painted image rectangle, so letterbox touches can shift the source crop. Map through the actual painted bounds and keep guide overlays aligned to those bounds. |
| Review | `ReviewScreen.qml`, `ReviewImageCanvas.qml`, `CaptureReviewController`, `vision/review_processing.py` | Crop and perspective overlays already use normalized source coordinates and `paintedWidth`/`paintedHeight`; backend crop/rotation mapping is resolution-independent. Preserve this model, expose/test painted-rectangle helpers, enlarge handles to minimum touch size, and fit the complete adjustment panel within the shorter screen. Display-only zoom must not alter submitted coordinates. |
| Results/history/errors | `ResultScreen.qml`, `ScrollableResultCard.qml`, `History*.qml`, `ErrorScreen.qml` | Result text scrolls, but body line-height is only 1.28 and several result/detail sizes are literal. History metadata reaches 13 px and many long strings elide. Move to readable body/metadata roles, 1.35-1.45 line height, responsive panels, and retain detail navigation. Error recovery already omits stack traces; make technical codes secondary. |
| Settings/health/diagnostics | `SettingsScreen.qml`, `DeviceHealthScreen.qml`, `HealthController`, new display diagnostic helper | Device Health has plain-language cards but no display/DPI diagnostics or technical-details separation. Add non-sensitive screen/platform/font diagnostics and a collapsible/scrollable Technical Details section. |
| Mock screenshots/tests | `tools/capture_ui_screenshots.py`, `tools/ui_preview/*.qml`, `tests/` | Active renders and fixtures use 1200 x 800. Existing documentation assets mix 1200 x 800 with older 1500 x 1000 images. Make 1366 x 768 the only production capture size, archive legacy assets, add layout/typography/mapping/config tests, and retain all functional tests. |
| Deployment/docs | `install.sh`, `hardware_require.txt`, `README.md`, `setup-en.md`, `setup-vi.md`, `docs/*.md` | Documentation still describes 1200 x 800 as the design canvas and the installer does not install/verify Noto Sans. Replace production claims, explicitly identify 1200 x 800 as an obsolete assumption, and add an honest physical-hardware checklist. |

## Current DPI, scaling, and coordinate behavior

- QML currently computes `contentScale = min(Screen.width / 1200,
  Screen.height / 800)` and transforms the complete 1200 x 800 tree. On a
  1366 x 768 screen this produces a 0.96 scale and unused horizontal space;
  text, borders, and icons are rasterized through that transform.
- No code forces `QT_SCALE_FACTOR`, `QT_AUTO_SCREEN_SCALE_FACTOR`, or a custom
  device-pixel ratio. The production launcher selects Wayland or XCB and leaves
  Qt scaling policy to the platform, which is the safe default until physical
  measurement is available.
- Static QML text has a mixture of default Qt rendering and forced native
  rendering. No font hinting preference or platform policy is centralized.
- Live preview and result images use aspect-preserving fill modes. Review crop
  and perspective coordinates are normalized to the source image and drawn
  against the actual painted rectangle. Camera preview zoom touch input is the
  exception: it currently maps against the outer preview frame and must account
  for letterboxing/pillarboxing.

## Proposed implementation

1. Remove the design-canvas transform. Size a windowed run to 1366 x 768 and
   use the real `ApplicationWindow` bounds in fullscreen.
2. Add `DisplayMetrics.qml` and `Typography.qml`; make `Theme.qml` expose their
   tokens. Add shared text wrappers with common font, rendering, hinting,
   wrapping, and line-height behavior.
3. Prefer the first installed body font from Noto Sans, Inter, DejaVu Sans, and
   Roboto. Keep the bundled OFL Roboto fallback and condensed brand face.
4. Add persisted `display.text_size` and configurable
   `display.text_rendering`, with environment overrides for diagnostics. Apply
   Standard/Large/Extra Large to type tokens only.
5. Replace fixed body heights with fill layouts and constrained readable widths.
   Use shared footer/control metrics and sentence/title case for long actions.
6. Map camera touch input through a tested aspect-fit painted rectangle. Keep
   review crop, rotation, perspective, and submission normalized/source-based.
7. Collect screen name, geometry, available geometry, DPR, logical/physical
   DPI, Qt platform, selected/fallback font, and fullscreen geometry after the
   QML window is shown. Log it and expose it in Device Health Technical Details.
8. Install `fonts-noto-core` and `fontconfig`, verify with `fc-match`, and retain
   a non-fatal fallback.
9. Update tests and render all safe mock screenshots at exactly 1366 x 768.

## Regression risks

- Qt layout implicit-size loops or clipped content when Extra Large text is
  combined with fixed-height cards.
- Different QFont fallback names on Windows, XCB, and Wayland.
- Native-rendered text becoming pixelated inside animated or transformed items.
- Letterbox/pillarbox offsets shifting zoom/crop touch coordinates.
- Review display zoom being mistaken for source crop zoom.
- Footer focus targets falling outside a setup `Flickable` viewport.
- Offscreen Qt screenshots differing from Raspberry Pi font rasterization.
- HDMI overscan, TV scaling, or a compositor fractional scale factor masking a
  correct application layout.

## Test plan

- Static checks: 1366 x 768 reference metrics; no active 1200 x 800 literals;
  no whole-tree scale; body font fallback order; centralized type roles; touch
  targets; sentence-case long actions.
- Geometry unit tests: aspect-fit painted rectangles, display/source round trips,
  letterbox and pillarbox clamping, preview zoom region, crop bounds, rotation,
  perspective points, and confirmed-file identity.
- QML/controller tests: main window loads at 1366 x 768; header/footer bounds;
  settings persistence; all text modes; logical GPIO/keyboard order.
- Full regression suite in mock hardware mode.
- Offscreen visual captures for setup, home, camera, review, processing, result,
  history, history detail, error, settings, Device Health, and Large Text.
- Physical validation remains mandatory for DPI, overscan, touchscreen alignment,
  font sharpness, and the Qt-versus-native rendering comparison.
