# Upwork Project Description

Raspberry Pi AI Vision Desk Assistant is a portfolio-ready MVP inspired by real freelance automation and edge-device UX work.

The project combines Raspberry Pi 5 hardware, camera capture, OpenCV preprocessing, OpenAI Vision analysis, a custom touchscreen-first Flask interface, and optional GPIO hardware controls. The system is designed like a focused capture appliance: choose a mode, frame the subject in a live preview, capture an image, watch processing progress, and read the AI response directly on-device. The latest UI iteration is a production-oriented `480x320` landscape touchscreen experience suitable for Chromium kiosk mode on a small Raspberry Pi display, with an answer-first result layout that compresses the header and health bar to preserve reading space.

This project demonstrates practical skills in:

- Raspberry Pi integration
- Python backend development
- Shared pipeline design across CLI, web UI, and GPIO entrypoints
- OpenCV image preprocessing
- OpenAI API integration
- Flask touchscreen UI, kiosk UX, and small-screen state management
- Live MJPEG preview and camera-lifecycle coordination
- Reliability engineering with health monitoring, recent-result recall, RAM thumbnail gallery, same-image re-analysis, and offline retry queue handling
- GPIO hardware interaction
- Deployment, demo packaging, and portfolio presentation
