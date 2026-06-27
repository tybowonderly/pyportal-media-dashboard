"""Initialize the PyPortal display (parallel ILI9341 — not SPI)."""

import board

_backlight = None


def init_display():
    """Use the firmware display and turn on the backlight."""
    import displayio
    import pwmio

    global _backlight

    # PyPortal TFT uses a parallel bus built into the firmware — not SPI/HX8357.
    # Do NOT call displayio.release_displays() or create a FourWire display.
    display = board.DISPLAY
    print("board.DISPLAY:", display)

    if display is None:
        raise RuntimeError("board.DISPLAY is None — cannot init screen")

    try:
        _backlight = pwmio.PWMOut(board.TFT_BACKLIGHT)
        _backlight.duty_cycle = 65535
        print("backlight on")
    except Exception as exc:
        print("backlight error:", exc)

    try:
        display.auto_refresh = True
    except AttributeError:
        pass

    return display


def show_group(display, group):
    """Attach the root group to the display (once at startup)."""
    if display is None:
        raise RuntimeError("Display init failed")
    display.show(group)
