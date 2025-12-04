#!/usr/bin/env python3
"""Simple JSON-backed state store for people_count and energy_data.

This module provides thread-safe read/write helpers that atomically persist
state to `state.json` in the project directory. It's intentionally small and
dependency-free so it works well on a Raspberry Pi.
"""
import json
import os
import threading
import copy

STATE_FILE = "state.json"
_lock = threading.Lock()

_default_state = {
    "people_count": 0,
    "energy_data": {
        "current_usage": 0.0,
        "total_consumption": 0.0,
        "cost_usd": 0.0,
        "cost_inr": 0.0,
        "temperature": 26.0,
        "humidity": 20.0,
        "cost": 0.0,
        # AC fields: suggestion may be None until the suggestion thread runs
        "ac_suggestion": None,
        "ac_current": None,
        "ac_override": False
    }
}

def reset_state():
    initial_data = {
        "people_count": 0,
        "energy_data": {
            "temperature":26.0,
            "humidity": 20.0,
            "current_usage": 0.0,
            "total_consumption": 0.0,
            "cost": 0.0,
            # AC fields default to no suggestion/current until thread runs
            "ac_suggestion": None,
            "ac_current": None,
            "ac_override": False
        }
    }
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(initial_data, f, indent=2)
        print(f"[INFO] State JSON reset: {STATE_FILE}")
    except Exception as e:
        print(f"[ERROR] Failed to reset state JSON: {e}")
        
def _read_from_disk():
    if not os.path.exists(STATE_FILE):
        return copy.deepcopy(_default_state)
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        # If the file is corrupted or unreadable, fall back to defaults.
        return copy.deepcopy(_default_state)


def _write_to_disk(state: dict):
    # Atomic write: write to tmp then replace
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.flush()
        try:
            os.fsync(fh.fileno())
        except Exception:
            pass
    os.replace(tmp, STATE_FILE)


def get_state() -> dict:
    """Return a deep copy of the full state (people_count + energy_data)."""
    with _lock:
        s = _read_from_disk()
        return copy.deepcopy(s)


def save_state(state: dict):
    """Persist the provided state dict to disk."""
    with _lock:
        _write_to_disk(state)


def get_people_count() -> int:
    return int(get_state().get("people_count", 0))


def set_people_count(value: int):
    st = get_state()
    st["people_count"] = max(0, int(value))
    save_state(st)


def incr_people(delta: int = 1) -> int:
    st = get_state()
    pc = int(st.get("people_count", 0)) + int(delta)
    pc = max(0, pc)
    st["people_count"] = pc
    save_state(st)

    # Recompute AC suggestion immediately when people count changes so UI and state
    # reflect the new recommendation without waiting for the background thread.
    try:
        # Import smart_ac lazily to avoid circular imports when modules import state
        try:
            from . import smart_ac
        except Exception:
            import smart_ac

        s = smart_ac.suggest_temp()
        ed = st.get("energy_data", {})
        # If a manual override is active, only update the suggestion.
        if ed.get("ac_override"):
            ed["ac_suggestion"] = int(s)
        else:
            ed["ac_suggestion"] = int(s)
            ed["ac_current"] = int(s)
            ed["ac_override"] = False
        st["energy_data"] = ed
        save_state(st)
    except Exception:
        # If smart_ac isn't available or something fails, silently continue.
        pass

    return pc


def get_energy_data() -> dict:
    return copy.deepcopy(get_state().get("energy_data", copy.deepcopy(_default_state["energy_data"])))


def update_energy_data(updates: dict) -> dict:
    st = get_state()
    ed = st.get("energy_data", {})
    ed.update(updates or {})
    st["energy_data"] = ed
    save_state(st)
    return copy.deepcopy(ed)
