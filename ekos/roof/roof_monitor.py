#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Camera monitor (runs all the time as a service).
Every few seconds: grab a frame -> classify roof -> write data/roof_state.json
A state becomes "confirmed" only after CONFIRM_FRAMES identical results.
"""
import time
from collections import deque

import roof_config as C
from roof_common import log, grab_frame, classify, read_json, write_json, last_press


def main():
    prev = read_json(C.STATE_FILE, {}) or {}
    confirmed, confirmed_ts = None, 0
    # keep the previous confirmed state across a quick restart (avoids a false
    # "closed" report while the roof is open and the mount is working)
    if time.time() - prev.get("ts", 0) < 600:
        confirmed, confirmed_ts = prev.get("confirmed"), prev.get("confirmed_ts", 0)
    history = deque(maxlen=C.CONFIRM_FRAMES)
    fault_logged_for = None
    log.info("monitor started (previous confirmed=%s)", confirmed)

    while True:
        img = grab_frame()
        live, scores = classify(img)
        history.append(live)

        if (len(history) == C.CONFIRM_FRAMES and live != "unknown"
                and all(h == live for h in history) and live != confirmed):
            log.info("roof CONFIRMED %s (was %s) scores=%s", live, confirmed, scores)
            confirmed, confirmed_ts = live, time.time()

        # movement watchdog
        p = last_press()
        want = {"open": "open", "close": "closed"}.get(p.get("target"))
        if want and confirmed != want and time.time() - p.get("ts", 0) > C.MOVE_TIMEOUT_SECONDS:
            if fault_logged_for != p.get("ts"):
                log.error("FAULT: roof did not reach '%s' within %ss (live=%s scores=%s)",
                          want, C.MOVE_TIMEOUT_SECONDS, live, scores)
                fault_logged_for = p.get("ts")

        write_json(C.STATE_FILE, {
            "ts": time.time(), "live": live, "scores": scores,
            "camera_ok": img is not None,
            "confirmed": confirmed, "confirmed_ts": confirmed_ts,
        })
        time.sleep(C.GRAB_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
