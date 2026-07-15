# 1366 x 768 display and text-readability migration report

## Outcome

VisionDesk now renders directly into the real application window. The production
reference and mock-render size is 1366 x 768; the former fixed 1200 x 800 canvas,
whole-tree `contentScale`, and non-uniform design-surface assumptions have been
removed. Fullscreen startup still uses Qt's real screen geometry rather than an
offscreen reference surface.

The migration was rendered and regression-tested on Windows in Qt's offscreen
software backend. It has **not** been validated on the physical Raspberry Pi,
11-inch HDMI panel, touchscreen, or GPIO hardware. No claim about physical text
sharpness is made until the hardware checklist is completed.

## Audit findings resolved

- `Main.qml` contained a fixed 1200 x 800 `designCanvas` and scaled the complete
  UI tree. Windowed configuration, preview QML, screenshot tooling, tests, and
  deployment documentation repeated that incorrect target.
- Font sizes and fixed body/panel dimensions were scattered through pages and
  components. Roboto Condensed and forced native rendering were used more widely
  than appropriate for long or interactive text.
- Camera images already preserved aspect ratio, and review crop/perspective data
  was normalized, but camera zoom-touch input used the outer preview frame rather
  than the image's actual painted rectangle.
- There was no persisted text-size setting or runtime display/DPI/font diagnostic
  model.
- Existing screenshots mixed the obsolete target with older miscellaneous sizes.

The detailed pre-change audit and risk analysis is in
`docs/display-1366x768-text-readability-plan.md`.

## Files created

- `docs/display-1366x768-text-readability-plan.md`
- `docs/display-1366x768-text-readability-report.md`
- `docs/1366x768-hardware-validation.md`
- `qt_app/display_integration.py`
- `vision/display_mapping.py`
- `qt_app/qml/theme/DisplayMetrics.qml`
- `qt_app/qml/theme/Typography.qml`
- `qt_app/qml/components/AppText.qml`
- `qt_app/qml/components/BodyText.qml`
- `qt_app/qml/components/HeadingText.qml`
- `qt_app/qml/components/StatusText.qml`
- `tests/test_display_1366x768.py`
- `docs/images/app-screens/04a-settings.png`
- `docs/images/app-screens/04b-large-text.png`
- `docs/images/app-screens/legacy-pre-1366x768/` (29 legacy PNG files)

## Files modified

- Runtime/configuration: `.env.example`, `config/device.yaml`,
  `config/settings.py`, `qt_app/main.py`, `qt_app/app_controller.py`, and
  `qt_app/health_controller.py`.
- Window/theme: `qt_app/qml/Main.qml` and `qt_app/qml/theme/Theme.qml`.
- Shared QML components: `AppHeader.qml`, `AppStatusBadge.qml`, `BrandLogo.qml`,
  `CameraGuideOverlay.qml`, `ClockCard.qml`, `HealthPill.qml`, `InputField.qml`,
  `ModeCard.qml`, `NavigationHint.qml`, `PasswordField.qml`, `PrimaryButton.qml`, `ProgressStep.qml`,
  `ProgressSteps.qml`, `ReviewImageCanvas.qml`, `ScrollableResultCard.qml`,
  `SectionTitle.qml`, `SetupHeaderPill.qml`, `SetupInputField.qml`,
  `SetupMetricChip.qml`, `SetupStepper.qml`, `StatusCard.qml`, `StatusChip.qml`,
  and `StatusPill.qml`.
- Screens: `CameraScreen.qml`, `DeviceHealthScreen.qml`, `ErrorScreen.qml`,
  `HistoryDetailScreen.qml`, `HistoryScreen.qml`, `HomeScreen.qml`,
  `ProcessingScreen.qml`, `ResultScreen.qml`, `ReviewScreen.qml`,
  `SettingsScreen.qml`, and `SetupScreen.qml`.
- Deployment/docs: `install.sh`, `hardware_require.txt`, `README.md`,
  `setup-en.md`, `setup-vi.md`, `docs/ui-commercial-upgrade-plan.md`, and
  `docs/ui-commercial-upgrade-report.md`.
- Tests/tools: `tests/test_qt_app.py`, `tools/capture_ui_screenshots.py`,
  `tools/ui_preview/AppScreensPreview.qml`, and
  `tools/ui_preview/SetupWizardPreview.qml`.
- The 19 existing numbered production screenshot files and their contact sheet
  were regenerated at 1366 x 768; Settings and Large Text captures were added.

## Resolution and responsive layout

- Reference size: 1366 x 768, approximately 16:9.
- Windowed runs use configured 1366 x 768 dimensions. Kiosk startup calls
  `showFullScreen()` and obtains diagnostics from the window's actual `QScreen`.
- The root design canvas, `contentScale`, `designWidth`, and `designHeight` were
  removed. There is no root `scale`, `xScale`, or `yScale` transform.
- The direct shell uses anchors and fill sizing. Page bodies consume the space
  between the header and their own footer instead of using heights tuned for
  an 800-pixel-tall surface.
- Home, Camera, Review, Result, History, Settings, Device Health, Setup,
  Processing, and Error layouts were rebalanced for the wider, shorter panel.
  Long result/setup/health/settings content scrolls instead of shrinking text.
- Touch targets remain at least 48 px; standard action buttons are 54 px high.
  Keyboard and GPIO navigation dispatch and logical screen focus order were
  preserved.

## Central display metrics

`DisplayMetrics.qml` defines the 1366 x 768 reference, 24 px outer margin,
50 px application header, 56 px footer, 12-14 px standard gaps, 54 px buttons,
48 px minimum touch target, 326 px side panel, 372 px result-image panel,
3 px focus border, corner radii, and shared icon sizes. `Theme.qml` exposes these
tokens to screens and components so the migration does not introduce per-page
resolution constants.

## Typography, contrast, and rendering

- Body-font selection is runtime-based: Noto Sans, Inter, DejaVu Sans, then
  Roboto. Startup remains non-fatal when a preferred family is absent. The
  bundled OFL Roboto remains the final application fallback.
- Roboto Condensed is limited to the VisionDesk brand and short decorative
  headings. Body, descriptions, buttons, results, settings, setup, errors,
  history, and diagnostics use the selected non-condensed body family.
- Standard pixel roles are Brand 44, Page Title 32, Section Title 23, Card Title
  20, Body 18, Secondary 16, Button 17, Status 16, Result 19, and Caption/
  Technical Metadata 15. Body/result line heights are 1.35/1.42.
- Standard, Large (1.15x), and Extra Large (1.30x) are persisted as typography
  settings. Branding remains stable so a text-size change cannot overrun the
  fixed header. The complete UI tree is never scaled.
- Static text defaults to `Text.QtRendering` with
  `Font.PreferVerticalHinting`. Native rendering is an explicit configurable
  comparison mode, not a blanket default; transformed/animated labels can force
  Qt rendering safely.
- Primary, secondary, and muted text are near-black/dark gray (`#111111`,
  `#333333`, and `#4B5565`). Muted/disabled surfaces were darkened, long actions
  were changed to title/sentence case, and status communication retains text,
  icon/dot, and color together.

## Camera and review coordinate safety

- Camera and review images use aspect-preserving rendering without stretching.
- Camera guides and zoom input now use `paintedX`, `paintedY`, `paintedWidth`,
  and `paintedHeight`, including letterbox/pillarbox offsets and the current
  normalized source region.
- `vision/display_mapping.py` provides tested aspect-fit, display-to-normalized,
  normalized-to-display, and bounded zoom-region helpers.
- Review crop handles reject input outside the painted image, use normalized
  source coordinates, stay in bounds, and meet the touch-target metric.
  Perspective points remain normalized. Review zoom is display-only.
- Existing capture/pipeline tests continue to verify that the confirmed path is
  the exact path submitted for analysis.

## Diagnostics and font deployment

- Startup logs and Device Health > Technical Details expose only non-sensitive
  screen name, geometry, available geometry, device pixel ratio, logical and
  physical DPI, selected font, fallback order, Qt platform, fullscreen geometry,
  and text-rendering policy.
- No Qt scale-factor environment variable is forced. Any fractional Pi scale
  must first be recorded and evaluated on the real hardware.
- `install.sh` installs `fontconfig` and `fonts-noto-core`, then runs a non-fatal
  `fc-match "Noto Sans"` check. DejaVu Sans and bundled Roboto fallbacks remain.

## Tests and verification

- Split regression run with the offscreen/software Qt backend:
  **196 passed, 5 skipped, 16 subtests passed** outside `test_qt_app.py`, plus
  **43 Qt application tests passed**. This covers 239 passing tests in total.
  On Windows, loading OpenCV preprocessing and the PySide QApplication in one
  pytest process can trigger a native access violation; the two groups pass in
  clean processes and should remain separate in Windows automation.
- `pyside6-qmllint qt_app/qml/Main.qml`: exit 0. It reports expected static
  warnings for the Python-injected `appController` context property and dynamic
  Loader item methods; no QML syntax error was found.
- `python -m compileall -q config qt_app vision`: passed.
- `bash -n install.sh uninstall.sh`: passed.
- `git diff --check`: passed.
- Static searches found no active 1200 x 800 window, QML, config, preview, test,
  or screenshot geometry.
- Screenshot generator: **27 UI screenshots plus one contact sheet** generated.
  All individual current captures were programmatically verified as exactly
  1366 x 768 and the contact sheet was visually inspected.

The new tests cover reference metrics, absence of a root design transform,
typography roles, minimum touch size, font selection/fallback, text preference
persistence, aspect-fit rectangles, letterbox/pillarbox clamping, coordinate
round trips, zoom bounds, camera/review painted-rectangle use, and footer/static
layout invariants. The preserved suite covers setup, navigation, crop, rotation,
perspective correction, quality/capability paths, history, errors, and exact
confirmed-image submission.

## Screenshot output

Current captures are in `docs/images/app-screens/`:

- Setup: `01-setup.png`, `01a-setup-running.png`, `01b-setup-results.png`,
  `01c-setup-scrolled.png`
- Finish Setup validation: `01d-finish-short.png`, `01e-finish-opencv-long.png`,
  `01f-finish-gpio-long.png`, `01g-finish-desktop-mock.png`,
  `01h-finish-scrolled.png`, and `01i-finish-large-text.png`
- Home/header states: `02-ready-header.png`, `03-wifi-unavailable-header.png`
- Settings/accessibility/health: `04a-settings.png`, `04b-large-text.png`,
  `04-device-health.png`
- Camera/review: `05-camera-document-guide.png` through
  `11-unsupported-camera-control.png`
- Processing/result/history/error: `12-processing.png` through `16-error.png`
- Overview: `00-contact-sheet.png`

The 29 superseded files are retained only under
`docs/images/app-screens/legacy-pre-1366x768/` and are clearly non-production.
No production secrets, customer images, credentials, or captured customer
screens are used.

## Remaining 1200/800 literals

No active UI-resolution assumption is retained. Remaining literals are justified:

- README/setup/hardware and the old UI plan/report explicitly identify
  1200 x 800 as the incorrect historical assumption.
- This plan/report describes the removed implementation for audit traceability.
- `1200` in screenshot tooling/preview is a millisecond wait interval.
- Camera exposure value `12000`, pipeline `max_dimension: 1200`, and synthetic
  800-pixel image/mapping fixtures are non-display domain values.
- The migration test intentionally searches for forbidden `setWidth(1200)` and
  `setHeight(800)` strings.

## Known limitations and real-hardware work

- Windows offscreen rendering cannot prove physical font sharpness, the Pi font
  rasterizer, HDMI timing, monitor 1:1 mode, overscan, real DPI accuracy,
  fractional compositor scaling, touchscreen calibration, camera latency, or
  GPIO focus behavior.
- Native versus Qt text rendering remains a physical visual choice. The safe
  production default is Qt rendering until the exact panel is compared.
- Extra Large mode is protected by token scaling and scrolling, but every
  workflow still needs a normal-distance physical usability pass.
- Run `docs/1366x768-hardware-validation.md` on the intended Pi/display and
  record the chosen rendering mode, deployed text size, DPR, DPI, overscan,
  touch alignment, crop/zoom alignment, and GPIO results before release.
