# Upwork Project Description

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready MVP inspired by real freelance work at the intersection of embedded UX, computer vision, and AI-assisted workflows.

The project combines Raspberry Pi 5 hardware, USB camera capture, OpenCV preprocessing, OpenAI Vision analysis, a custom Flask touchscreen interface, and GPIO hardware controls. The current product direction is a local-only capture appliance: select a mode, frame the subject in a live preview, capture the image, watch a compact progress flow, and read the AI result directly on-device.

Current maturity highlights:

- shared pipeline architecture across CLI, Flask UI, and GPIO triggers
- production-oriented `480x320` landscape kiosk UI for Raspberry Pi
- lighter `640x360` live preview separated from `1920x1080` still capture
- typed YAML-backed device configuration with environment overrides
- health monitoring, rotating logs, and hardware-aware busy-state handling
- text-only recent-result history for better privacy
- offline retry queue for transient network or OpenAI failures
- automated regression suite currently at `105 passed, 16 subtests passed` on 2026-07-11

This project demonstrates practical skills in:

- Raspberry Pi integration
- Python backend development
- Flask kiosk UX and small-screen state management
- OpenCV preprocessing and screen/document correction
- OpenAI API integration
- hardware button and LED control through GPIO
- reliability engineering for edge-device software
- deployment packaging, diagnostics, and portfolio presentation
