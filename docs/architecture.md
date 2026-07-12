# Architecture

## High-level flow

```text
Qt/QML UI
  -> qt_app.app_controller
  -> setup / history / health / camera / pipeline controllers
  -> shared runtime services
  -> camera / vision / ai / pipeline / hardware / system modules
  -> private local storage + OpenAI
```

## Native UI stack

- `qt_app/main.py` creates the Qt application, image provider, and root controller.
- `qt_app/app_controller.py` is the single facade exposed to QML.
- `qt_app/qml/` contains the kiosk screens and shared components.
- `qt_app/history_controller.py` owns saved-result list/detail state and destructive data actions.

## Shared backend stack

- `qt_app/runtime.py` owns typed settings, retention defaults, private paths, history store, setup store, live preview, and retry queue wiring.
- `system/setup_flow.py` provides reusable setup persistence and completion logic.
- `system/result_history.py` provides text-only history persistence, corruption recovery, single-item delete, and clear-history support.
- `system/ui_presenters.py` provides answer sanitization, result/detail shaping, progress copy, and health/header shaping.
- `system/offline_retry.py` provides durable retry queue behavior with private storage bounds.

## Storage model

- `config/device.yaml`: durable device config
- `.env`: durable secrets
- `data/result_history.json`: saved text-only result history
- `data/latest_result.txt`: latest non-sensitive result summary
- `data/setup_state.json`: temporary setup progress
- `data/private/current/`: current capture working files
- `data/private/retry/`: queued retry media
- `data/private/retry_queue.json`: queued retry metadata
- `data/private/quarantine/`: corrupt persisted files and leftovers

## Privacy model

- result history stores text and safe metadata only
- private media stays under `data/private/`
- startup purge trims transient data
- delete-all-data clears user content without deleting device config or `.env`
- persisted writes use atomic file replacement helpers
