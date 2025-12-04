#!/usr/bin/env python3
"""
Smart AC temperature suggestion module.

Features:
- suggest_temp(): compute a recommended AC setpoint based on people_count, indoor temp and humidity
- apply_manual_setpoint(value): allow manual override (useful when voice assistant sets a setpoint)
- start_suggestion_thread(): background thread that updates `energy_data["ac_suggestion"]` and
  optionally displays the suggestion on the project's OLED (if `display` is available).

Run standalone: python smart_ac.py

Integration (in-process):
    from smart_ac import start_suggestion_thread
    start_suggestion_thread()

Notes:
- This module attempts to use `display.oled` to render a short message on the OLED. If the
  display package is unavailable (for example when running headless on development machine), it
  will silently skip OLED output.
"""

import threading
from time import sleep

from . import state

import logging
logger = logging.getLogger(__name__)

try:
    import display
except Exception:
    display = None

from PIL import Image, ImageDraw

# Manual override (None means no manual override)
_manual_setpoint = None


def suggest_temp() -> float:
    """Return a more economical suggested AC temperature (°C) based on current project state.

    Heuristic changes for energy savings:
    - If room empty -> raise setpoint to 27°C to save more energy
    - Single person -> slightly warmer (25°C)
    - More people -> slightly cooler but with a smaller per-person penalty to favor economy
    - High humidity -> small additional cooling (reduced from original to save energy)
    - If the room is already close to or cooler than the target, nudge the setpoint warmer
    - Clamp to [18, 27] to avoid aggressive cooling
    """
    p = state.get_people_count()
    ed = state.get_energy_data()
    indoor = ed.get("temperature", 22.0)
    hum = ed.get("humidity", 40.0)

    if _manual_setpoint is not None:
        # Manual override takes precedence. Return integer setpoint.
        logger.debug("Manual AC override active: %s", _manual_setpoint)
        return int(round(_manual_setpoint))

    if p == 0:
        base = 27.0
    elif p == 1:
        base = 25.0
    else:
        # baseline comfort temperature, but favor economy by reducing the per-person cooling impact
        base = 24.0 - min(1.2, 0.15 * (p - 1))

    # Reduce penalty for humidity to avoid over-cooling while still addressing comfort
    if hum > 60:
        base -= 0.5

    # If the room is already at or below the target (or very close), avoid further cooling:
    # nudge the recommendation warmer to save energy.
    if indoor <= base + 0.5:
        base = min(base + 1.0, 27.0)

    # Clamp to reasonable bounds (more economical upper bound)
    base = max(18.0, min(27.0, base))
    return int(round(base))


def apply_manual_setpoint(value: float):
    global _manual_setpoint
    _manual_setpoint = float(value)
    # reflect override in shared state (if available)
    try:
        state.update_energy_data({
            "ac_override": True,
            "ac_current": int(round(_manual_setpoint))
        })
        logger.info("Manual AC setpoint applied: %s", _manual_setpoint)
    except Exception:
        pass


def clear_manual_setpoint():
    global _manual_setpoint
    _manual_setpoint = None
    try:
        state.update_energy_data({"ac_override": False})
    except Exception:
        pass


def display_suggestion_on_oled(sugg: float):
    if display is None:
        return
    try:
        oled = display.oled
    except Exception:
        return

    img = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(img)
    text = f"AC Suggestion:\n{sugg} °C"
    # Basic layout: center vertically
    draw.text((2, 10), text, fill=255)
    oled.image(img)
    oled.show()


def suggestion_loop(interval: int = 10):
    while True:
        # compute recommendation (integer)
        s = suggest_temp()
        state.update_energy_data({"ac_suggestion": int(s)})
        # If a manual override exists, keep ac_current equal to that, otherwise follow recommendation
        if _manual_setpoint is not None:
            state.update_energy_data({"ac_current": int(round(_manual_setpoint)), "ac_override": True})
        else:
            state.update_energy_data({"ac_current": int(s), "ac_override": False})
        try:
            display_suggestion_on_oled(int(s))
        except Exception:
            # Safe-guard: never crash the thread on display errors
            logger.exception("Failed to display AC suggestion on OLED")
        logger.debug("AC suggestion updated: %s (override=%s)", s, _manual_setpoint is not None)
        sleep(interval)


def start_suggestion_thread(interval: int = 10):
    threading.Thread(target=suggestion_loop, args=(interval,), daemon=True).start()
    logger.info("Smart AC suggestion thread started (interval=%s)", interval)


if __name__ == "__main__":
    start_suggestion_thread(5)
    # keep the process alive to let the background thread run
    import time

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
