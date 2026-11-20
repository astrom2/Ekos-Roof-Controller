#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup / test tool.

  python3 roof_calibrate.py grab      # save data/grid.jpg (frame + grid + ROI box)
  python3 roof_calibrate.py esp-state  # what the ESP roof controller reports
  python3 roof_calibrate.py esp-open   # send OPEN  (asks first)
  python3 roof_calibrate.py esp-close  # send CLOSE (asks first)
  python3 roof_calibrate.py esp-stop   # send STOP
  python3 roof_calibrate.py closed    # save CLOSED reference (roof closed!)
  python3 roof_calibrate.py open      # save OPEN reference (roof open, at night)
  python3 roof_calibrate.py test      # live classification + scores (Ctrl+C to stop)
  python3 roof_calibrate.py cozylife-login   # one-time: enable cloud fallback
  python3 roof_calibrate.py switch    # check the switch answers (local + cloud), read-only
  python3 roof_calibrate.py press     # press the roof button once (asks first)
  python3 roof_calibrate.py state     # what Ekos will see now
"""
import os
import sys
import time

import roof_config as C
from roof_common import grab_frame, classify, switch_query, press_button, roof_state, read_json


def need_frame():
    img = grab_frame()
    if img is None:
        sys.exit("ERROR: could not read the camera. Check CAMERA_RTSP in roof_config.py "
                 "and that RTSP is enabled in the EZVIZ app.")
    return img


def cmd_grab():
    import cv2
    img = need_frame()
    h, w = img.shape[:2]
    for i in range(1, 10):
        x, y = int(w * i / 10), int(h * i / 10)
        cv2.line(img, (x, 0), (x, h), (0, 255, 255), 1)
        cv2.line(img, (0, y), (w, y), (0, 255, 255), 1)
        cv2.putText(img, "%.1f" % (i / 10), (x + 3, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        cv2.putText(img, "%.1f" % (i / 10), (3, y - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    x1, y1, x2, y2 = C.ROI
    cv2.rectangle(img, (int(x1 * w), int(y1 * h)), (int(x2 * w) - 1, int(y2 * h) - 1), (0, 0, 255), 3)
    x1, y1, x2, y2 = C.CONTEXT_ROI
    cv2.rectangle(img, (int(x1 * w), int(y1 * h)), (int(x2 * w) - 1, int(y2 * h) - 1), (0, 255, 0), 3)
    out = os.path.join(C.DATA_DIR, "grid.jpg")
    cv2.imwrite(out, img)
    print("Saved %s" % out)
    print("RED   box = ROI %s : must cover ONLY moving roof panels" % (C.ROI,))
    print("GREEN box = CONTEXT_ROI %s : walls/floor that never change (no timestamp)" % (C.CONTEXT_ROI,))
    print("Adjust the numbers in roof_config.py, run grab again, then save the closed reference.")


def cmd_ref(which):
    import cv2
    path = C.CLOSED_REF if which == "closed" else C.OPEN_REF
    input("Make sure the roof is fully %s, then press Enter..." % which.upper())
    img = None
    for _ in range(3):
        img = need_frame()
        time.sleep(1)
    cv2.imwrite(path, img)
    print("Saved %s reference -> %s" % (which, path))
    state, scores = classify(img)
    print("Check: classified as %s  %s" % (state, scores))


def cmd_test():
    print("Rules: CLOSED if sim_closed>=%.2f and tile_min>=%.2f ; OPEN if tile_max<=%.2f ; else UNKNOWN"
          % (C.CLOSED_MIN_SIMILARITY, C.CLOSED_MIN_TILE, C.OPEN_MAX_TILE))
    try:
        while True:
            state, scores = classify(grab_frame())
            print(time.strftime("%H:%M:%S"), state.upper().ljust(8), scores)
            time.sleep(C.GRAB_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        pass


def cmd_esp(cmd=None):
    from roof_common import esp_state, esp_command, SwitchError
    try:
        if cmd:
            if cmd != "stop" and input("This will %s the roof. Telescope parked? type yes: " % cmd.upper()).strip().lower() != "yes":
                return
            esp_command(cmd)
            print("Sent %s." % cmd.upper())
        print("ESP %s says: %s" % (C.ESP_HOST, esp_state()))
    except SwitchError as e:
        print("ESP FAIL: %s" % e)


def cmd_switch():
    from roof_common import _local_exchange, _cloud_exchange, _frame, SwitchError, _shelly
    if C.SWITCH_TYPE == "esp":
        cmd_esp()
        print("(read-only test - nothing was switched)")
        return
    if C.SWITCH_TYPE == "shelly":
        try:
            print("SHELLY %s OK   %s" % (C.SHELLY_IP, _shelly("Switch.GetStatus", id=0)))
        except SwitchError as e:
            print("SHELLY FAIL %s" % e)
        print("(read-only test - nothing was switched)")
        return
    for name, fn in (("LOCAL %s" % C.SWITCH_IP, _local_exchange), ("CLOUD", _cloud_exchange)):
        try:
            reply = fn(_frame(2, {"attr": [0]}))
            print("%-22s OK   data=%s" % (name, (reply.get("msg") or {}).get("data")))
        except SwitchError as e:
            print("%-22s FAIL %s" % (name, e))
    print("(read-only test - nothing was switched)")


def cmd_cozylife_login():
    import getpass
    from roof_common import cozylife_login, SwitchError
    print("CozyLife account login (password is used once and NOT saved)")
    email = input("CozyLife email: ").strip()
    password = getpass.getpass("CozyLife password: ")
    try:
        cfg, devices = cozylife_login(email, password)
    except SwitchError as e:
        sys.exit("Login failed: %s" % e)
    except Exception as e:
        msg = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in msg:
            msg += "\n(macOS: run 'Install Certificates.command' from your Python folder)"
        sys.exit("Login failed: %s" % msg)
    print("Devices on the account:")
    for d in devices:
        print("  - %s  id=%s  online=%s" % (d.get("device_name"), d.get("device_id"), d.get("is_online")))
    if cfg:
        print("Saved roof switch '%s' (relay %s:%s, dpids %s) -> %s"
              % (cfg["name"], cfg["relay_host"], cfg["relay_port"], cfg["dpids"], C.CLOUD_FILE))
    else:
        print("Switch id %s not found - check SWITCH_DEVICE_ID in roof_config.py" % C.SWITCH_DEVICE_ID)


def cmd_press():
    if input("This will PRESS the roof button. Telescope parked? type yes: ").strip().lower() == "yes":
        press_button("manual test")
        print("Pressed.")


def cmd_state():
    st = roof_state()
    raw = read_json(C.STATE_FILE, {}) or {}
    print("Camera now : %s   scores=%s" % (st["live"], raw.get("scores")))
    print("Confirmed  : %s" % st["confirmed"])
    print("Monitor    : %s (data %.0fs old)" % ("OK" if st["fresh"] else "NOT RUNNING", st["age"]))
    print("Ekos sees  : %s" % ("UNPARKED (open)" if st["confirmed"] == "open" else "PARKED (closed)"))


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    {"grab": cmd_grab, "closed": lambda: cmd_ref("closed"), "open": lambda: cmd_ref("open"),
     "test": cmd_test, "switch": cmd_switch, "press": cmd_press, "state": cmd_state,
     "cozylife-login": cmd_cozylife_login,
     "esp-open": lambda: cmd_esp("open"), "esp-close": lambda: cmd_esp("close"),
     "esp-stop": lambda: cmd_esp("stop"), "esp-state": cmd_esp,
     }.get(c, lambda: print(__doc__))()
