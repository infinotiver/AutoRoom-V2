#!/usr/bin/env python3

import logging
from datetime import datetime

# Constants
L1_PIN, L2_PIN = 18, 15
LED_PINS = [6, 8, 25]  # Working pins on RPi 3B+
DEBOUNCE_MS = 20
TIME_THRESHOLD = 0.3

# Globals (use with caution; threads will modify)
laser_times = {"L1": 0, "L2": 0}


# Logging setup
logging.basicConfig(
    level=logging.DEBUG,  # Can be set to INFO or ERROR based on preference
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Outputs to console
        logging.FileHandler("dashboard_log.txt")  # Logs to a file
    ]
)

