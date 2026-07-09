"""Optional GPIO LED indicator for device lifecycle feedback."""

from __future__ import annotations

from typing import Any, Callable

from hardware.status import DeviceState, coerce_device_state

LEDFactory = Callable[..., Any]


class LEDIndicatorError(Exception):
    """Raised when the GPIO LED cannot be initialized."""


class LEDIndicator:
    """Single-color LED controller with a silent no-op fallback mode."""

    def __init__(
        self,
        *,
        pin: int | None = None,
        enabled: bool = False,
        active_high: bool = True,
        led_factory: LEDFactory | None = None,
    ) -> None:
        self.pin = pin
        self.enabled = enabled
        self.active_high = active_high
        self.disabled_reason: str | None = None
        self.last_state = DeviceState.READY
        self._device = None

        if not enabled:
            return
        if pin is None:
            raise LEDIndicatorError("GPIO LED pin is required when LED support is enabled.")

        device_factory = led_factory or _import_led_factory()
        try:
            self._device = device_factory(pin, active_high=active_high)
        except Exception as exc:
            raise LEDIndicatorError(
                f"Could not initialize GPIO LED on pin {pin}. {exc}"
            ) from exc

    @classmethod
    def create(
        cls,
        *,
        pin: int | None = None,
        enabled: bool = False,
        active_high: bool = True,
        led_factory: LEDFactory | None = None,
    ) -> "LEDIndicator":
        """Create an LED indicator, falling back to a disabled no-op instance."""
        try:
            return cls(
                pin=pin,
                enabled=enabled,
                active_high=active_high,
                led_factory=led_factory,
            )
        except LEDIndicatorError as exc:
            indicator = cls(
                pin=pin,
                enabled=False,
                active_high=active_high,
                led_factory=led_factory,
            )
            indicator.disabled_reason = str(exc)
            return indicator

    @property
    def available(self) -> bool:
        """Return True when a real GPIO LED device is active."""
        return self._device is not None

    def set_state(self, device_state: DeviceState | str) -> None:
        """Apply the requested device-state pattern to the LED."""
        self.last_state = coerce_device_state(device_state)
        if self._device is None:
            return

        if self.last_state in {DeviceState.READY, DeviceState.DONE}:
            self._device.on()
            return

        if self.last_state == DeviceState.CAPTURING:
            self._device.blink(on_time=0.4, off_time=0.4, background=True)
            return

        if self.last_state == DeviceState.PROCESSING:
            self._device.blink(on_time=0.2, off_time=0.2, background=True)
            return

        self._device.blink(on_time=0.1, off_time=0.1, background=True)

    def close(self) -> None:
        """Release the underlying GPIO LED when present."""
        if self._device is None:
            return
        try:
            self._device.close()
        except Exception:
            pass
        finally:
            self._device = None


def _import_led_factory() -> LEDFactory:
    """Import gpiozero.LED only when hardware LED support is requested."""
    try:
        from gpiozero import LED
    except ImportError as exc:
        raise LEDIndicatorError(
            "gpiozero is not available. Install it with: pip install gpiozero"
        ) from exc
    except Exception as exc:
        raise LEDIndicatorError(f"GPIO LED support is not available on this system. {exc}") from exc
    return LED
