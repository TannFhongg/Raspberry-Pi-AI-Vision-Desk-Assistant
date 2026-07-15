# 1366 x 768 Raspberry Pi and HDMI validation

This checklist must be completed on the intended Raspberry Pi and the exact
11-inch HDMI panel. Offscreen Windows screenshots and automated tests do not
validate physical sharpness, touch alignment, overscan, or display scaling.

## Record the test environment

- Raspberry Pi model and RAM:
- Raspberry Pi OS version and desktop/compositor:
- Qt platform (`wayland` or `xcb`):
- Display make/model and HDMI input:
- Touch controller make/model, if present:
- VisionDesk version/commit:
- Date and tester:

## OS and HDMI output

- [ ] Confirm the active OS output is exactly **1366 x 768** at the intended refresh rate.
- [ ] Confirm desktop/display scaling is **100%**.
- [ ] Open Settings > Device Health > Technical Details and record screen name,
      geometry, available geometry, device pixel ratio, logical DPI, physical
      DPI, Qt platform, fullscreen geometry, and selected body font.
- [ ] Confirm the device pixel ratio is expected. If it is fractional, record
      the exact value and compositor settings; do not force a Qt environment
      variable until its effect is tested.
- [ ] Confirm there is no overscan or clipped desktop edge.
- [ ] Set monitor scaling to **Original**, **PC**, **1:1**, **Just Scan**, or the
      equivalent non-stretching mode.
- [ ] Confirm the panel is not stretching a different HDMI input resolution.

## Text rendering and readability

- [ ] Confirm ordinary Raspberry Pi desktop text is sharp before assessing VisionDesk.
- [ ] Confirm VisionDesk body, button, setup, result, history, status, and error
      text is readable from the normal desk-viewing distance.
- [ ] Confirm the selected body family is Noto Sans, Inter, DejaVu Sans, or the
      bundled Roboto fallback.
- [ ] Test Standard, Large, and Extra Large text sizes. Confirm content scrolls
      instead of shrinking, controls remain reachable, and header/footer actions
      remain visible.
- [ ] Run once with default `display.text_rendering: auto`/QtRendering and record the result.
- [ ] Compare with `UI_TEXT_RENDERING=native`, checking static text and
      animated/zoomed screens for rasterization or pixelation.
- [ ] Record which rendering mode looks best on the exact panel and why:

## Layout and navigation

- [ ] Confirm Setup progress steps, cards, scroll, and fixed footer do not overlap.
- [ ] Confirm all five Home task cards fit and their GPIO focus order is logical.
- [ ] Confirm header branding never overlaps the Ready/status badge.
- [ ] Confirm every footer remains visible and does not cover page content.
- [ ] Confirm long result and history content scrolls and opens in detail view.
- [ ] Confirm error recovery text is readable and no stack trace is shown.
- [ ] Confirm Settings and all Device Health Technical Details are reachable.
- [ ] Confirm keyboard Up/Down/Select/Back behavior and visible focus.
- [ ] Confirm each configured GPIO button follows the same logical focus order.

## Camera, review, and input coordinates

- [ ] Confirm live preview aspect ratio matches the camera without stretching.
- [ ] Confirm preview guides align with the actual painted image, including any
      letterboxing or pillarboxing.
- [ ] Confirm preview zoom pans to the selected source area and stays in bounds.
- [ ] Confirm the Review image matches the captured frame.
- [ ] Confirm crop handles stay within the painted image and remain easy to target.
- [ ] Confirm crop drag coordinates match touch or mouse input at all edges.
- [ ] Confirm perspective boundary lines align with the displayed document.
- [ ] Confirm display-only review zoom does not change the submitted crop.
- [ ] Confirm the image shown after confirmation is the image submitted for analysis.
- [ ] Confirm touchscreen coordinates align at all four corners and the center.

## Sign-off

- [ ] All checks passed, or deviations are recorded below.
- Deviations/known limitations:
- Selected rendering mode:
- Selected text size for deployment:
- Tester signature/date:

Physical display quality is **not yet validated** until this checklist is run on
the exact Raspberry Pi, HDMI panel, and touch/GPIO hardware.
