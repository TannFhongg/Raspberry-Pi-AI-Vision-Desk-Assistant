"""Temporary GPIO verifier used by the first-boot setup wizard."""

from __future__ import annotations

from typing import Any, Callable

ButtonFactory = Callable[..., Any]


class GPIOSetupVerifierError(Exception):
    """Raised when the setup GPIO verifier cannot be initialized."""


class GPIOSetupVerifier:
    """Track one press on each configured GPIO setup button."""

    def __init__(
        self,
        required_pins: dict[str, int],
        *,
        debounce_seconds: float = 0.15,
        button_factory: ButtonFactory | None = None,
    ) -> None:
        normalized_required_pins: dict[str, int] = {}
        for label, pin in required_pins.items():
            if not isinstance(label, str):
                continue
            try:
                resolved_pin = int(pin)
            except (TypeError, ValueError):
                continue
            if resolved_pin < 0:
                continue
            normalized_required_pins[label] = resolved_pin
        self.required_pins = normalized_required_pins
        self.debounce_seconds = debounce_seconds
        self.button_factory = button_factory
        self._buttons: list[Any] = []
        self._pressed_labels: set[str] = set()

    def start(self) -> None:
        """Initialize the temporary GPIO button listeners."""
        button_class = self.button_factory or _import_button_factory()
        try:
            for label, pin in self.required_pins.items():
                button = button_class(
                    pin,
                    pull_up=True,
                    bounce_time=self.debounce_seconds,
                )
                button.when_released = lambda label=label: self._mark_pressed(label)
                self._buttons.append(button)
        except Exception as exc:
            self.close()
            raise GPIOSetupVerifierError(f"Could not initialize GPIO setup verifier. {exc}") from exc

    def close(self) -> None:
        """Release all temporary GPIO button listeners."""
        for button in self._buttons:
            try:
                button.close()
            except Exception:
                pass
        self._buttons = []

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON-safe snapshot of current setup GPIO progress."""
        required = []
        for label, pin in self.required_pins.items():
            required.append(
                {
                    "label": label,
                    "pin": pin,
                    "pressed": label in self._pressed_labels,
                }
            )
        return {
            "required": required,
            "pressed_labels": sorted(self._pressed_labels),
            "all_pressed": len(self._pressed_labels) >= len(self.required_pins),
        }

    def _mark_pressed(self, label: str) -> None:
        """Record one successful press for the given label."""
        self._pressed_labels.add(label)


def _import_button_factory() -> ButtonFactory:
    """Import gpiozero.Button only when the setup verifier starts."""
    try:
        from gpiozero import Button
    except ImportError as exc:
        raise GPIOSetupVerifierError(
            "gpiozero is not available. Install it with: pip install gpiozero"
        ) from exc
    except Exception as exc:
        raise GPIOSetupVerifierError(f"GPIO is not available on this system. {exc}") from exc
    return Button
