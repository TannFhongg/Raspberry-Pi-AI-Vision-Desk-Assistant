# Upwork Project Description

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready MVP inspired by real freelance work at the intersection of embedded UX, computer vision, and AI-assisted workflows.

The project combines Raspberry Pi 5 hardware, USB camera capture, OpenCV preprocessing, OpenAI Vision analysis, a custom Flask touchscreen interface, a native `PySide6 + Qt Quick/QML` frontend for the primary capture flow, and GPIO hardware controls. The current product direction is a local-only capture appliance: select a mode, frame the subject in a live preview, capture the image, watch a compact progress flow, and read the AI result directly on-device.

Current maturity highlights:

- shared pipeline architecture across CLI, Flask UI, native Qt UI, and GPIO triggers
- production-oriented `1200x800` landscape kiosk UX for Raspberry Pi
- native Qt v1 flow for `setup`, `home`, `camera`, `processing`, `result`, and `error`, with Flask kept intact during migration
- lighter `640x360` live preview separated from `1920x1080` still capture
- typed YAML-backed device configuration with environment overrides
- shared presenter, setup, and result-history helpers so Flask and Qt stay behavior-compatible
- health monitoring, rotating logs, and hardware-aware busy-state handling
- text-only recent-result history for better privacy
- offline retry queue for transient network or OpenAI failures
- targeted shared-plus-Qt regression suite at `63 passed, 4 skipped, 23 subtests passed` on 2026-07-12

This project demonstrates practical skills in:

- Raspberry Pi integration
- Python backend development
- Flask kiosk UX plus native Qt/QML migration for an embedded device UI
- OpenCV preprocessing and screen/document correction
- OpenAI API integration
- hardware button and LED control through GPIO
- reliability engineering for edge-device software
- deployment packaging, diagnostics, and portfolio presentation
