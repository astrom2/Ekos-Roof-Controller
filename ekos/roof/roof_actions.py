# -*- coding: utf-8 -*-
"""
Actions called by the INDI "Dome Scripting Gateway" scripts (scripts/*.py).

INDI convention for a roll-off roof:
    PARKED   = roof fully CLOSED
    UNPARKED = roof fully OPEN
The driver runs park.py / unpark.py once, then polls status.py every 2 s and
finishes the park/unpark only when status reports the new state. So:
    - park/unpark only PRESS the button (fast, no waiting)
    - status reports what the CAMERA has confirmed
While the roof is travelling, status keeps reporting the previous confirmed
state, so the mount stays locked until the roof is confirmed fully open.
"""
import sys
import time

import roof_config as C
from roof_common import (log, roof_state, last_press, record_press, press_button, switch_query,
                         esp_command, esp_state)


def _press_age():
    p = last_press()
    return time.time() - p.get("ts", 0), p.get("target")


# ------------------------------------------------------------------ status
def status(outfile):
    if C.SWITCH_TYPE == "esp" and C.STATUS_SOURCE == "esp":
        try:
            is_open = esp_state() == "open"
        except Exception as e:
            log.error("status: ESP not reachable (%s) - reporting CLOSED", e)
            is_open = False
        with open(outfile, "w") as f:
            f.write(("0 1 0.0" if is_open else "1 0 0.0") + "\n")
        return 0
    st = roof_state()
    if not st["fresh"]:
        log.warning("status: monitor data is %.0fs old (camera monitor not running?)", st["age"])
    is_open = st["confirmed"] == "open"
    # format read by the driver: "<parked> <shutter> <azimuth>"
    line = "0 1 0.0" if is_open else "1 0 0.0"
    with open(outfile, "w") as f:
        f.write(line + "\n")
    return 0


# ------------------------------------------------------------------ ESP8266 (separate OPEN / CLOSE / STOP)
def _wait_other_direction(target):
    """If the roof was sent the other way less than a travel ago, let it finish first."""
    age, last = _press_age()
    if last in ("open", "close") and last != target and age < C.PRESS_COOLDOWN_SECONDS:
        wait = C.PRESS_COOLDOWN_SECONDS - age + 1
        log.warning("%s: roof was sent to '%s' %.0fs ago, waiting %.0fs", target, last, age, wait)
        time.sleep(wait)


def _esp_state_or_none():
    try:
        return esp_state()
    except Exception as e:
        log.warning("ESP state not readable: %s", e)
        return None


def esp_open_roof():
    st = roof_state()
    if st["fresh"] and st["live"] == "open":
        log.info("open: camera already sees the roof open")
        return 0
    if _esp_state_or_none() in ("open", "opening"):
        # never touch the open wire again at the end of travel / while opening
        log.info("open: ESP says the roof is already open/opening - nothing sent")
        return 0
    age, last = _press_age()
    if last == "open" and age < C.PRESS_COOLDOWN_SECONDS:
        log.info("open: already opening (sent %.0fs ago)", age)
        return 0
    _wait_other_direction("open")
    esp_command("open")
    record_press("open")
    return 0


def esp_close_roof():
    st = roof_state()
    if st["fresh"] and st["live"] == "closed":
        log.info("close: camera already sees the roof closed")
        return 0
    if _esp_state_or_none() in ("closed", "closing"):
        log.info("close: ESP says the roof is already closed/closing - nothing sent")
        return 0
    age, last = _press_age()
    if last == "close" and age < C.PRESS_COOLDOWN_SECONDS:
        log.info("close: already closing (sent %.0fs ago)", age)
        return 0
    _wait_other_direction("close")
    # CLOSE is a separate wire, so it is safe even when the camera can't see:
    # Ekos only calls park after the telescope is parked (Mount locks).
    esp_command("close")
    record_press("close")
    return 0


def esp_connect():
    try:
        state = esp_state()
    except Exception as e:
        log.error("connect: ESP roof controller not reachable: %s", e)
        return 1
    st = roof_state()
    if C.STATUS_SOURCE == "camera" and not st["fresh"]:
        log.warning("connect: camera monitor not running (data %.0fs old)", st["age"])
    log.info("connect OK (ESP says %s, camera confirmed=%s live=%s)", state, st["confirmed"], st["live"])
    return 0


def esp_abort():
    # The ESP only touches the wire again if the roof is really moving.
    esp_command("stop")
    record_press("stop")
    return 0


# ------------------------------------------------------------------ open
def open_roof():
    st = roof_state()
    age, target = _press_age()

    if st["live"] == "open" or (st["fresh"] and st["confirmed"] == "open" and st["live"] != "closed"):
        log.info("open: roof already open")
        return 0
    if age < C.PRESS_COOLDOWN_SECONDS and target == "open":
        log.info("open: already opening (pressed %.0fs ago)", age)
        return 0
    if not st["fresh"] or st["live"] != "closed":
        # Single toggle button: pressing while the position is unknown could
        # close the roof instead - never open blind.
        log.error("open REFUSED: camera state is '%s' (fresh=%s). Check camera/ROI.", st["live"], st["fresh"])
        return 1
    if age < C.PRESS_COOLDOWN_SECONDS:
        log.error("open REFUSED: button was pressed %.0fs ago (roof may be moving)", age)
        return 1

    press_button("open")
    record_press("open")
    return 0


# ------------------------------------------------------------------ close
def close_roof():
    st = roof_state()
    age, target = _press_age()

    if st["live"] == "closed":
        log.info("close: roof already closed")
        return 0
    if age < C.PRESS_COOLDOWN_SECONDS and target == "close":
        log.info("close: already closing (pressed %.0fs ago)", age)
        return 0
    if age < C.PRESS_COOLDOWN_SECONDS:
        # roof is travelling the other way: wait for it to finish, then decide
        wait = C.PRESS_COOLDOWN_SECONDS - age + 1
        log.warning("close: roof was opening %.0fs ago, waiting %.0fs", age, wait)
        time.sleep(wait)
        st = roof_state()
        if st["live"] == "closed":
            return 0

    if st["fresh"] and st["live"] == "open":
        press_button("close")
        record_press("close")
        return 0

    # camera can't see the roof right now
    pressed_since = last_press().get("ts", 0) > st["confirmed_ts"]
    if C.ALLOW_BLIND_CLOSE and st["confirmed"] == "open" and not pressed_since:
        log.warning("close: camera state '%s' - BLIND close (last confirmed open, no press since)", st["live"])
        press_button("close (blind)")
        record_press("close")
        return 0

    log.error("close REFUSED: camera state '%s', last confirmed '%s'", st["live"], st["confirmed"])
    return 1


# ------------------------------------------------------------------ misc
def connect():
    try:
        _, path = switch_query()
        if path == "cloud":
            log.warning("connect: switch answered via CLOUD only - power-cycle it to restore local control")
    except Exception as e:
        log.error("connect: CozyLife switch not reachable: %s", e)
        return 1
    st = roof_state()
    if not st["fresh"]:
        log.warning("connect: camera monitor not running (data %.0fs old)", st["age"])
    log.info("connect OK (roof confirmed=%s live=%s)", st["confirmed"], st["live"])
    return 0


def abort():
    # A single toggle button cannot be "stopped" safely (a press may reverse it).
    log.warning("abort requested - ignored (single toggle button)")
    return 0


def run(action):
    try:
        if action == "status":
            return status(sys.argv[1])
        if C.SWITCH_TYPE == "esp":
            table = {"open": esp_open_roof, "close": esp_close_roof, "connect": esp_connect,
                     "abort": esp_abort, "noop": lambda: 0}
        else:
            table = {"open": open_roof, "close": close_roof, "connect": connect,
                     "abort": abort, "noop": lambda: 0}
        return table[action]()
    except Exception as e:
        log.exception("%s failed: %s", action, e)
        return 1
