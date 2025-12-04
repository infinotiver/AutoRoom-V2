#!/usr/bin/env python3
from . import sensors
from .energy import start_energy_thread
from .display import start_face_status_cycle
from .web import run_server
from . import config
from . import state
from .smart_ac import start_suggestion_thread
from . import smart_ac
import logging 

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("main_debug.log")
    ]
)

logger = logging.getLogger(__name__)
logger.info("Starting application: initializing threads and web server")

def get_people_count():
    return state.get_people_count()

if __name__ == "__main__":
    state.reset_state()
    sensors.start_dht_thread()
    start_energy_thread()
    start_face_status_cycle()
    # Start Smart AC suggestion thread so ac_suggestion/current/override are populated
    start_suggestion_thread()
    # Make one immediate suggestion at startup so dashboard shows values without waiting
    try:
        if smart_ac:
            s = smart_ac.suggest_temp()
            ed = state.get_energy_data()
            # If there's already a manual override recorded, don't overwrite ac_current
            if ed.get('ac_override'):
                # Only update suggestion
                state.update_energy_data({"ac_suggestion": int(s)})
            else:
                state.update_energy_data({"ac_suggestion": int(s), "ac_current": int(s), "ac_override": False})
    except Exception:
        logger.exception('Failed to compute initial AC suggestion')
    run_server()  # Blocks here; threads run in background
