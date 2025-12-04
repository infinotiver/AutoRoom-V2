#!/usr/bin/env python3
import threading
from time import sleep, time
import random
import subprocess
import logging
import board
import adafruit_ssd1306
from PIL import Image, ImageDraw, ImageFont
from . import config
from . import state

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ---------- OLED setup ----------
i2c = board.I2C()
oled = adafruit_ssd1306.SSD1306_I2C(128, 64, i2c)
oled.fill(0)
oled.show()
FONT = ImageFont.load_default()
# Try to load a larger TrueType font for better readability on the OLED.
try:
    LARGE_FONT = ImageFont.truetype("DejaVuSans.ttf", 14)
    MED_FONT = ImageFont.truetype("DejaVuSans.ttf", 12)
    SMALL_FONT = ImageFont.truetype("DejaVuSans.ttf", 9)
except Exception:
    LARGE_FONT = ImageFont.load_default()
    MED_FONT = ImageFont.load_default()
    SMALL_FONT = ImageFont.load_default()


def _get_ip():
    try:
        out = subprocess.check_output(['hostname', '-I'], stderr=subprocess.DEVNULL, timeout=2)
        ip = out.decode('utf-8').strip().split()[0] if out else ''
        return ip
    except Exception:
        logger.exception("Failed to get IP address")
        return ''


def draw_face(blink=False, mouth_open=False):
    img = Image.new("1", (oled.width, oled.height))
    draw = ImageDraw.Draw(img)

    # Eyes
    eye_y, left_x, right_x = 25, 35, 90
    er, pr = 10, 4
    if blink:
        draw.line((left_x-er, eye_y, left_x+er, eye_y), fill=255, width=2)
        draw.line((right_x-er, eye_y, right_x+er, eye_y), fill=255, width=2)
    else:
        draw.ellipse((left_x-er, eye_y-er, left_x+er, eye_y+er), outline=255, fill=255)
        draw.ellipse((right_x-er, eye_y-er, right_x+er, eye_y+er), outline=255, fill=255)
        offset = random.randint(-3,3)
        draw.ellipse((left_x-pr+offset, eye_y-pr, left_x+pr+offset, eye_y+pr), fill=0)
        draw.ellipse((right_x-pr+offset, eye_y-pr, right_x+pr+offset, eye_y+pr), fill=0)

    # Mouth
    my = 50
    if mouth_open:
        draw.rectangle((50, my, 78, my+4), fill=0, outline=255)
    else:
        draw.line((50, my, 78, my), fill=255, width=2)

    oled.image(img)
    oled.show()


def display_status(duration=3.0):
    try:
        ip = _get_ip()
        try:
            people = state.get_people_count()
        except Exception:
            people = None

        # Gather energy data (temp/humidity and AC values)
        try:
            ed = state.get_energy_data()
        except Exception:
            ed = {}

        temp = ed.get('temperature')
        hum = ed.get('humidity')
        ac_sugg = ed.get('ac_suggestion')
        ac_curr = ed.get('ac_current')
        ac_ovr = ed.get('ac_override', False)

        # Prepare lines with chosen fonts. Use larger font for the most important value (people)
        lines = []
        if ip:
            lines.append((f"IP: {ip}", SMALL_FONT))
        if people is not None:
            lines.append((f"People: {people}", LARGE_FONT))
        # Temperature and humidity line
        if temp is not None or hum is not None:
            ttxt = f"T: {temp if temp is not None else '--'}°C  H: {hum if hum is not None else '--'}%"
            lines.append((ttxt, MED_FONT))
        # AC suggestion/current line
        if ac_sugg is not None or ac_curr is not None:
            s = ac_sugg if ac_sugg is not None else '--'
            c = ac_curr if ac_curr is not None else '--'
            ov = 'M' if ac_ovr else 'A'
            actxt = f"AC S:{s}°C C:{c}°C ({ov})"
            lines.append((actxt, MED_FONT))

        if not lines:
            return

        img = Image.new("1", (oled.width, oled.height))
        draw = ImageDraw.Draw(img)

        # Compute bounding boxes for each line using their fonts
        line_bboxes = [draw.textbbox((0,0), text, font=font) for (text, font) in lines]
        line_sizes = [(bbox[2]-bbox[0], bbox[3]-bbox[1]) for bbox in line_bboxes]

        total_h = sum(h for _, h in line_sizes) + (len(lines)-1)*2
        y = max(0, (oled.height - total_h)//2)

        for (text, font), (w,h) in zip(lines, line_sizes):
            x = max(0, (oled.width - w)//2)
            draw.text((x,y), text, font=font, fill=255)
            y += h+2

        oled.image(img)
        oled.show()
        sleep(duration)
        oled.fill(0)
        oled.show()
    except Exception:
        logger.exception("Error in display_status")


def start_face_status_cycle(mouth_open_callback=None, face_duration=5.0, status_duration=3.0, ip_duration=3.0):
    """
    Single thread cycling through face -> status -> IP display.
    mouth_open_callback (optional) returns True/False for mouth state.
    """
    def cycle_loop():
        try:
            while True:
                # ----- Face -----
                mouth_open = False
                if callable(mouth_open_callback):
                    try:
                        mouth_open = bool(mouth_open_callback())
                    except Exception:
                        logger.exception("mouth_open_callback failed")
                        mouth_open = False
                draw_face(blink=False, mouth_open=mouth_open)
                sleep(face_duration)

                # Blink effect at end of face display
                draw_face(blink=True, mouth_open=mouth_open)
                sleep(0.2)

                # ----- Status -----
                display_status(duration=status_duration)

                # ----- IP -----
                ip = _get_ip()
                if ip:
                    img = Image.new("1", (oled.width, oled.height))
                    draw = ImageDraw.Draw(img)
                    bbox = draw.textbbox((0,0), f"IP: {ip}", font=FONT)
                    w,h = bbox[2]-bbox[0], bbox[3]-bbox[1]
                    draw.text(((oled.width-w)//2,(oled.height-h)//2), f"IP: {ip}", font=FONT, fill=255)
                    oled.image(img)
                    oled.show()
                    sleep(ip_duration)
                    oled.fill(0)
                    oled.show()
        except Exception:
            logger.exception("Unhandled error in face-status-IP cycle thread")

    threading.Thread(target=cycle_loop, daemon=True).start()
