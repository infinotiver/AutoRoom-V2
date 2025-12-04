#!/usr/bin/env python3
"""
Voice-controlled assistant (web-based)

Run standalone: python voice_assistant.py

This module exposes a tiny HTTP endpoint (/voice) that accepts JSON { "text": "turn off lights" }.
It interprets a small set of commands and manipulates the in-memory globals in `config.py` so it
works when run in the same process as the rest of the application. Keep it as a separate process
or thread depending on your deployment.

Supported commands (simple matching):
- "lights off" / "lights on"  -> sets `people_count` (0 or 1) and calls `update_leds()` if available
- "increase people" / "decrease people" -> adjusts `people_count`
- "set temp to <N>" -> if `smart_ac.apply_manual_setpoint` exists it will call it, otherwise it
  writes the value into `energy_data["temperature"]` (local-only)
- "status" -> returns simple status text

Integration (in-process):
    from voice_assistant import start_voice_server
    start_voice_server()

Notes:
- This file is intentionally standalone and small. If you run it in a separate Python process,
  send recognized voice text as JSON to http://<pi-ip>:8090/voice .
- If you need richer speech recognition, run the STT engine client-side (browser) or use a
  service and POST the recognized text here. Don't embed heavy STT models on the Pi unless you
  have hardware to support it.
"""

import threading
import re
from flask import Flask, request, jsonify
import logging

logger = logging.getLogger(__name__)

# Import project state/actions. These imports assume running in the project root.
try:
    from . import state
except Exception:
    try:
        import state
    except Exception:
        state = None

try:
    from sensors import update_leds
    from display import draw_face
except Exception:
    update_leds = None
    draw_face = None

try:
    import smart_ac
except Exception:
    smart_ac = None

app = Flask(__name__)

def interpret_and_execute(text: str) -> str:
    """Interpret a small set of voice/text commands and execute them.
    Returns a human-readable result string.
    """
    if not state:
        logger.warning("Project imports failed; voice commands will be no-ops")
        return "Project imports failed; cannot modify runtime state."

    t = text.lower()

    if "light" in t or "lights" in t:
        if "off" in t:
            state.set_people_count(0)
            if update_leds:
                update_leds()
            if draw_face:
                draw_face(mouth_open=True)
            logger.info("Voice command: lights off -> people_count=0")
            return "Lights turned OFF (people_count set to 0)"
        if "on" in t:
            # Ensure at least 1
            if state.get_people_count() < 1:
                state.set_people_count(1)
            if update_leds:
                update_leds()
            if draw_face:
                draw_face(mouth_open=True)
            logger.info("Voice command: lights on -> people_count set to 1")
            return "Lights turned ON (people_count set to 1)"

    if "increase people" in t or ("people" in t and "increase" in t) or "add person" in t:
        new_pc = state.incr_people(1)
        if update_leds:
            update_leds()
        logger.info("Voice command: increase people -> %s", new_pc)
        return f"People increased to {new_pc}"

    if "decrease people" in t or "remove person" in t:
        new_pc = state.incr_people(-1)
        if update_leds:
            update_leds()
        logger.info("Voice command: decrease people -> %s", new_pc)
        return f"People decreased to {new_pc}"

    m = re.search(r"set (?:the )?temp(?:erature)? to (\d{1,2}(?:\.\d+)?)", t)
    if m:
        val = float(m.group(1))
        if smart_ac and hasattr(smart_ac, "apply_manual_setpoint"):
            smart_ac.apply_manual_setpoint(val)
            logger.info("Voice command: set temp -> %s via smart_ac", val)
            return f"AC setpoint set to {val}°C (via smart_ac)"
        else:
            # When smart_ac isn't available, write the desired AC setpoint (ac_current)
            # rather than overwriting the sensor `temperature` which represents room temp.
            try:
                state.update_energy_data({"ac_current": int(round(val)), "ac_override": True})
                logger.info("Voice command: set temp -> %s (local AC override)", val)
                return f"AC setpoint set to {val}°C (local override)"
            except Exception:
                # fallback: write temperature if state.update fails for some reason
                try:
                    state.update_energy_data({"temperature": val})
                except Exception:
                    pass
                logger.info("Voice command: set temp -> %s (fallback temperature update)", val)
                return f"Temperature value updated to {val} (fallback)"

    if "status" in t:
        st = state.get_state()
        ed = st.get('energy_data', {})
        s = f"people={st.get('people_count')}, temp={ed.get('temperature')}, hum={ed.get('humidity')}"
        logger.info("Voice status requested: %s", s)
        return s

    return "Command not recognized. Try: 'lights off', 'lights on', 'set temp to 22', 'increase people', 'status'"


@app.route("/voice", methods=["POST"])
def voice():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")
    if not text:
        return jsonify({"error": "no text provided"}), 400
    logger.debug("Voice endpoint received text: %s", text)
    result = interpret_and_execute(text)
    logger.debug("Voice command result: %s", result)
    return jsonify({"result": result})


def run_server():
    # Run on 0.0.0.0 port 8090 by default so it can be reached from other devices.
    app.run(host="0.0.0.0", port=8090)


def start_voice_server():
    threading.Thread(target=run_server, daemon=True).start()


if __name__ == "__main__":
    run_server()
