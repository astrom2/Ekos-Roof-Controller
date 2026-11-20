# -*- coding: utf-8 -*-
"""
Jarnan Observatory - roll-off roof settings.
Edit the values marked  <-- CHANGE  then restart the monitor:
    sudo systemctl restart roof-monitor
"""

# ---------------- Which device moves the roof ----------------
# "esp"      = ESP8266 roof controller (separate OPEN / CLOSE / STOP)  <-- current
# "cozylife" = old single-button CozyLife switch
# "shelly"   = Shelly 1 Mini Gen3 (single button)
SWITCH_TYPE = "esp"

# ---------------- ESP8266 roof controller (ESPHome) ----------------
ESP_HOST = "192.168.100.115"        # reserve this IP in the router
ESP_USER = "admin"                  # <-- CHANGE: web_user from secrets.yaml
ESP_PASS = "change-me-web"          # <-- CHANGE: web_password from secrets.yaml
ESP_TIMEOUT = 5                     # seconds

# Where Ekos gets "open / closed" from:
#   "camera" = the camera must confirm (safest, needs the camera calibrated)
#   "esp"    = time estimate from the ESP (28 s travel). Use only until the
#              camera is ready: if the roof jams, Ekos will still think it is open.
STATUS_SOURCE = "esp"

# ---------------- Shelly 1 Mini Gen3 ----------------
# Wiring: L/N = power (from the black plug), I = brown, O = white, SW unused.
SHELLY_IP = "192.168.100.XX"        # <-- CHANGE: reserve a static IP in the router

# ---------------- CozyLife switch (the roof button) ----------------
SWITCH_IP = "192.168.100.23"        # static IP of the CozyLife switch (ln_sta in the router)
SWITCH_PORT = 5555                  # CozyLife local TCP port (do not change)
SWITCH_DEVICE_ID = "YOUR_COZYLIFE_DEVICE_ID"   # only for the old CozyLife setup
SWITCH_DPID = 1                     # relay on/off datapoint
PULSE_SECONDS = 1.0                 # how long the "button press" lasts (ON -> wait -> OFF)
LOCAL_TIMEOUT = 5                   # seconds to wait for the switch to answer locally

# If the switch does not answer locally, send the same command through the
# CozyLife cloud (the same path the phone app uses). Needs a one-time:
#     python3 roof_calibrate.py cozylife-login
# Your password is NOT saved - only the device key is.
USE_CLOUD_FALLBACK = True

# ---------------- Camera (EZVIZ TY1) ----------------
# Enable RTSP first in the EZVIZ app (see README). Password = 6-letter
# verification code printed on the camera sticker.
CAMERA_RTSP = "rtsp://admin:ABCDEF@192.168.1.60:554/ch1/main"   # <-- CHANGE

# Region of the image that shows the roof panels, as fractions of the frame
# (x1, y1, x2, y2). Default = top 30% of the frame, full width.
# Run:  python3 roof_calibrate.py grab   to see a grid and adjust.
ROI = (0.0, 0.0, 1.0, 0.30)          # <-- CHANGE after calibration if needed

# A region that does NOT change when the roof opens (walls, floor, parked pier).
# Used as proof that the camera is really seeing: "open" is only accepted if
# this region still looks normal. Avoid the timestamp text.
CONTEXT_ROI = (0.0, 0.55, 1.0, 0.90) # <-- CHECK on grid.jpg

# ---------------- Roof timing ----------------
ROOF_TRAVEL_SECONDS = 28            # measured full open/close time
MOVE_TIMEOUT_SECONDS = 60           # if not confirmed after this -> fault
PRESS_COOLDOWN_SECONDS = 33         # never press again within this time (travel 28 s + margin)

# ---------------- Detection ----------------
GRAB_INTERVAL_SECONDS = 2           # pause between camera snapshots
CONFIRM_FRAMES = 3                  # identical results needed to confirm a state
STALE_SECONDS = 30                  # monitor data older than this = camera lost

# Thresholds. The roof region is split into 8 tiles and each tile is compared
# with the CLOSED reference (1.0 = identical, 0 = nothing in common).
# "roof_calibrate.py test" prints the live numbers to tune these.
CLOSED_MIN_SIMILARITY = 0.45        # average over tiles needed for CLOSED
CLOSED_MIN_TILE = 0.30              # every tile must be at least this for CLOSED
OPEN_MAX_TILE = 0.25                # every tile must be below this for OPEN
CONTEXT_MIN_SIMILARITY = 0.50       # walls region must match at least this for OPEN

# ---------------- Safety ----------------
# If the camera is lost while the roof was last seen OPEN and nobody pressed
# the button since, allow "park" (close) to press anyway. Closing protects the
# equipment from weather, and the mount is already parked by then.
# Opening is NEVER done blind.
ALLOW_BLIND_CLOSE = True

# ---------------- Files ----------------
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATE_FILE = os.path.join(DATA_DIR, "roof_state.json")      # written by monitor
PRESS_FILE = os.path.join(DATA_DIR, "roof_press.json")      # written by park/unpark
CLOSED_REF = os.path.join(DATA_DIR, "ref_closed.png")
OPEN_REF = os.path.join(DATA_DIR, "ref_open.png")       # saved for reference only
LAST_FRAME = os.path.join(DATA_DIR, "last_frame.jpg")
LOG_FILE = os.path.join(DATA_DIR, "roof.log")
CLOUD_FILE = os.path.join(DATA_DIR, "cozylife_cloud.json")  # device key (keep private)
