#!/usr/bin/env python3
import pigpio
from time import time, sleep
import threading
import board
import adafruit_dht
import logging
from . import config
from . import state

logger = logging.getLogger(__name__)

# ---------- pigpio setup ----------
pi = pigpio.pi()
if not pi.connected:
    logger.error("pigpiod not running. Start with: sudo systemctl start pigpiod")
    raise Exception("Start pigpiod: sudo systemctl start pigpiod")

# ---------- DHT setup ----------
try:
    dhtDevice = adafruit_dht.DHT11(board.D4)
    logger.debug("Initialized DHT11 on board.D4")
except Exception as e:
    dhtDevice = None
    logger.exception("Failed to initialize DHT device: %s", e)

# ---------- GPIO setup ----------
pi.set_mode(config.L1_PIN, pigpio.INPUT)
pi.set_pull_up_down(config.L1_PIN, pigpio.PUD_UP)
pi.set_mode(config.L2_PIN, pigpio.INPUT)
pi.set_pull_up_down(config.L2_PIN, pigpio.PUD_UP)
for pin in config.LED_PINS:
    pi.set_mode(pin, pigpio.OUTPUT)

l1_last_tick = 0
l2_last_tick = 0

def update_leds():
    try:
        pc = state.get_people_count()
        print(f"[DEBUG] Accessing people_count from LED update func: {pc}")
        logger.debug("Accessed people_count: %s", pc)

        out_state = 0 if pc >= 1 else 1
        print(f"[DEBUG] Determined LED output state: {out_state}")

        for pin in config.LED_PINS:
            try:
                pi.write(pin, out_state)
                logger.debug("Wrote %s to LED pin %s", out_state, pin)
            except Exception as e_pin:
                logger.exception("Failed to write to LED pin %s: %s", pin, e_pin)

        logger.info("LEDs updated: state=%s, people_count=%s", out_state, pc)

    except Exception as e:
        logger.exception("Error in update_leds(): %s", e)
        print(f"[ERROR] update_leds() failed: {e}")



def process_lasers():
    t1 = config.laser_times["L1"]
    t2 = config.laser_times["L2"]
    if t1 == 0 or t2 == 0:
        return

    dt = t2 - t1
    if abs(dt) > config.TIME_THRESHOLD:
        config.laser_times["L1"] = 0
        config.laser_times["L2"] = 0
        return

    if dt > 0:
        new_pc = state.incr_people(1)
        logger.info("Entry detected L1->L2, people_count=%s", new_pc)
    elif dt < 0:
        new_pc = state.incr_people(-1)
        logger.info("Exit detected L2->L1, people_count=%s", new_pc)

    config.laser_times["L1"] = 0
    config.laser_times["L2"] = 0
    update_leds()

# ---------- Callbacks ----------
def l1_callback(gpio, level, tick):
    global l1_last_tick
    if tick - l1_last_tick < config.DEBOUNCE_MS * 1000:
        return
    l1_last_tick = tick
    if level == 0:
        config.laser_times["L1"] = time()
        logger.debug("L1 triggered at %s", config.laser_times['L1'])
        process_lasers()

def l2_callback(gpio, level, tick):
    global l2_last_tick
    if tick - l2_last_tick < config.DEBOUNCE_MS * 1000:
        return
    l2_last_tick = tick
    if level == 0:
        config.laser_times["L2"] = time()
        logger.debug("L2 triggered at %s", config.laser_times['L2'])
        process_lasers()

pi.callback(config.L1_PIN, pigpio.EITHER_EDGE, l1_callback)
pi.callback(config.L2_PIN, pigpio.EITHER_EDGE, l2_callback)

update_leds()  # initial LED state

# ---------- DHT Thread ----------
DHT_READ_INTERVAL = 10  # seconds between reads

def read_dht_sensor():
    last_fail_logged = False
    while True:
        try:
            if dhtDevice is None:
                logger.warning("DHT device not initialized; skipping read")
            else:
                temp = dhtDevice.temperature
                hum = dhtDevice.humidity
                if temp is not None and hum is not None:
                    state.update_energy_data({
                        "temperature": round(temp, 1),
                        "humidity": round(hum, 1)
                    })
                    ed = state.get_energy_data()
                    logger.debug("DHT read success: temp=%s, hum=%s",
                                 ed.get("temperature"),
                                 ed.get("humidity"))
                    last_fail_logged = False
        except RuntimeError as e:
            if not last_fail_logged:
                logger.warning("DHT transient read error: %s", e)
                last_fail_logged = True
        except Exception as e:
            logger.exception("Unexpected error while reading DHT sensor: %s", e)
        sleep(DHT_READ_INTERVAL)

def start_dht_thread():
    threading.Thread(target=read_dht_sensor, daemon=True).start()
    logger.info("DHT read thread started")
