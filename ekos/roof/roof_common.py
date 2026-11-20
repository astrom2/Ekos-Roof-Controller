# -*- coding: utf-8 -*-
"""Shared helpers: CozyLife switch, camera grab, roof classifier, state files."""
import json
import logging
import os
import socket
import subprocess
import time

import roof_config as C

os.makedirs(C.DATA_DIR, exist_ok=True)

log = logging.getLogger("roof")
if not log.handlers:
    log.setLevel(logging.INFO)
    _h = logging.FileHandler(C.LOG_FILE)
    _h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(process)d] %(message)s"))
    log.addHandler(_h)


# ------------------------------------------------------------------ files
def write_json(path, data):
    tmp = path + ".tmp%d" % os.getpid()
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)  # atomic


def read_json(path, default=None):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


# ------------------------------------------------------------------ CozyLife switch
# Protocol: CRLF-terminated JSON frames {"pv":0,"cmd":2|3,"sn":...,"msg":{...}};
# the device echoes "sn" in its reply. cmd 2 = query, cmd 3 = set.
# Cloud relay: the same frame, url-encoded inside
#   cmd=subscribe&topic=device_<id>&device_id=<id>&device_key=<key>
#   cmd=publish&topic=control_<id>&...&message=<frame>
# (protocol details as documented by github.com/lacherogwu/homeassistant-cozylife, MIT)
from urllib.parse import quote, unquote

_last_sn = [0]


class SwitchError(Exception):
    pass


def _frame(cmd, msg):
    sn = max(int(time.time() * 1000), _last_sn[0] + 1)
    _last_sn[0] = sn
    return {"pv": 0, "cmd": cmd, "sn": str(sn), "msg": msg}


def _lines(sock, deadline):
    buf = b""
    while True:
        remaining = deadline - time.time()
        if remaining <= 0:
            return
        sock.settimeout(remaining)
        try:
            chunk = sock.recv(4096)
        except (socket.timeout, TimeoutError):
            return
        if not chunk:
            return
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            if line.strip():
                yield line.strip()


def _local_exchange(frame):
    data = (json.dumps(frame, separators=(",", ":")) + "\r\n").encode()
    try:
        with socket.create_connection((C.SWITCH_IP, C.SWITCH_PORT), timeout=C.LOCAL_TIMEOUT) as s:
            s.sendall(data)
            for line in _lines(s, time.time() + C.LOCAL_TIMEOUT):
                try:
                    reply = json.loads(line)
                except ValueError:
                    continue
                if reply.get("sn") == frame["sn"]:
                    return reply
    except OSError as e:
        raise SwitchError("local: %s" % e)
    raise SwitchError("local: switch did not answer within %ss" % C.LOCAL_TIMEOUT)


def _cloud_exchange(frame):
    cfg = read_json(C.CLOUD_FILE)
    if not cfg:
        raise SwitchError("cloud: not set up (run: python3 roof_calibrate.py cozylife-login)")
    did, key = cfg["device_id"], cfg["device_key"]
    report = "device_" + did

    def line(**f):
        f.setdefault("device_id", did)
        f.setdefault("device_key", key)
        return ("&".join("%s=%s" % kv for kv in f.items()) + "\r\n").encode()

    msg = quote(json.dumps(frame, separators=(",", ":")), safe="")
    try:
        with socket.create_connection((cfg["relay_host"], int(cfg["relay_port"])), timeout=10) as s:
            s.sendall(line(cmd="subscribe", topic=report))
            s.sendall(line(cmd="publish", topic="control_" + did, message=msg))
            for raw in _lines(s, time.time() + 10):
                fields = {}
                for part in raw.decode("utf-8", "replace").split("&"):
                    k, sep, v = part.partition("=")
                    if sep:
                        fields[k] = v
                if fields.get("cmd") == "publish" and fields.get("num") == "0":
                    raise SwitchError("cloud: switch is offline (relay reached no device)")
                if fields.get("topic") == report and "message" in fields:
                    try:
                        reply = json.loads(unquote(fields["message"]))
                    except ValueError:
                        continue
                    if reply.get("sn") == frame["sn"]:
                        return reply
    except OSError as e:
        raise SwitchError("cloud: %s" % e)
    raise SwitchError("cloud: no answer within 10s")


_local_skip_until = [0.0]


def _exchange(frame):
    """Local first, then cloud. Returns (reply, 'local'|'cloud').
    After a local failure, local is skipped for 60 s so the ON/OFF of one
    button press are not each delayed by a local timeout.
    Safe to repeat: every command SETS an absolute value (ON or OFF), so if a
    local command did arrive but its reply got lost, re-sending it via the
    cloud changes nothing."""
    local_err = SwitchError("local: skipped (failed moments ago)")
    if time.time() >= _local_skip_until[0] or not C.USE_CLOUD_FALLBACK:
        try:
            return _local_exchange(frame), "local"
        except SwitchError as e:
            if not C.USE_CLOUD_FALLBACK:
                raise
            local_err = e
            _local_skip_until[0] = time.time() + 60
    try:
        reply = _cloud_exchange(frame)
        log.info("switch: used cloud (%s)", local_err)
        return reply, "cloud"
    except SwitchError as e:
        raise SwitchError("%s | %s" % (local_err, e))


def switch_set(on):
    dp = str(C.SWITCH_DPID)
    reply, path = _exchange(_frame(3, {"attr": [C.SWITCH_DPID], "data": {dp: 255 if on else 0}}))
    if reply.get("res") not in (0, None):
        raise SwitchError("switch refused the command via %s: %s" % (path, reply))
    return path


def switch_query():
    """Read the switch state. Never changes anything. Returns (data, path)."""
    if C.SWITCH_TYPE == "shelly":
        return _shelly("Switch.GetStatus", id=0), "shelly"
    reply, path = _exchange(_frame(2, {"attr": [0]}))
    return (reply.get("msg") or {}).get("data"), path


# ------------------------------------------------------------------ Shelly (Gen2/3/4 RPC API)
def _shelly(method, **params):
    import urllib.parse
    import urllib.request
    url = "http://%s/rpc/%s?%s" % (C.SHELLY_IP, method, urllib.parse.urlencode(params))
    try:
        with urllib.request.urlopen(url, timeout=C.LOCAL_TIMEOUT) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        raise SwitchError("shelly %s: %s" % (C.SHELLY_IP, e))


def _shelly_press():
    # One request = ON, and the Shelly itself switches OFF after PULSE_SECONDS,
    # even if the network drops right after this call.
    _shelly("Switch.Set", id=0, on="true", toggle_after=C.PULSE_SECONDS)
    time.sleep(C.PULSE_SECONDS + 1.0)
    for attempt in range(3):  # verify it really released
        try:
            if not _shelly("Switch.GetStatus", id=0).get("output"):
                return "shelly"
            _shelly("Switch.Set", id=0, on="false")
        except SwitchError as e:
            log.error("shelly release check failed (attempt %d): %s", attempt + 1, e)
        time.sleep(1)
    raise SwitchError("shelly: output still ON after press!")


def press_button(reason):
    """Simulate one press of the roof button: ON, wait, OFF."""
    log.info("PRESS roof button (%s)", reason)
    if C.SWITCH_TYPE == "shelly":
        log.info("press done via %s", _shelly_press())
        return
    path = switch_set(True)
    time.sleep(C.PULSE_SECONDS)
    for attempt in range(3):  # the button must never stay held
        try:
            switch_set(False)
            break
        except SwitchError as e:
            log.error("release failed (attempt %d): %s", attempt + 1, e)
            time.sleep(1)
    else:
        raise SwitchError("button pressed but could not be released!")
    log.info("press done via %s", path)


# ------------------------------------------------------------------ ESP8266 (ESPHome web_server)
ESP_NAMES = {"open": "Roof Open", "close": "Roof Close", "stop": "Roof Stop"}


def _esp_request(path, method="GET"):
    import base64
    import urllib.error
    import urllib.parse
    import urllib.request
    url = "http://%s%s" % (C.ESP_HOST, path)
    req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
    tok = base64.b64encode(("%s:%s" % (C.ESP_USER, C.ESP_PASS)).encode()).decode()
    req.add_header("Authorization", "Basic " + tok)
    try:
        with urllib.request.urlopen(req, timeout=C.ESP_TIMEOUT) as r:
            body = r.read().decode(errors="replace")
            return r.status, body
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        raise SwitchError("ESP %s: %s" % (C.ESP_HOST, e))


def _esp_entity(domain, name, action=None, method="GET"):
    """ESPHome 2025+ uses the entity name in the URL, older versions the object id."""
    from urllib.parse import quote
    object_id = "".join(c if c.isalnum() else "_" for c in name.lower()).strip("_")
    for ident in (quote(name), object_id):
        path = "/%s/%s%s" % (domain, ident, "/" + action if action else "")
        code, body = _esp_request(path, method)
        if code == 200:
            return body
        if code == 401:
            raise SwitchError("ESP: wrong ESP_USER / ESP_PASS in roof_config.py")
    raise SwitchError("ESP: %s '%s' not found (HTTP %s)" % (domain, name, code))


def esp_command(cmd):
    """cmd = open | close | stop. The ESP itself makes the 1 s touch and the
    interlock; a repeated OPEN/CLOSE while travelling is ignored by the ESP."""
    log.info("ESP command: %s", cmd.upper())
    _esp_entity("button", ESP_NAMES[cmd], "press", "POST")


def esp_state():
    """'open' | 'closed' | 'opening' | 'closing' | 'stopped' | 'unknown' (time estimate)."""
    body = _esp_entity("text_sensor", "Roof State")
    try:
        d = json.loads(body)
        return str(d.get("value", d.get("state", "unknown")))
    except ValueError:
        return "unknown"


CLOUD_API = "https://api-us.doiting.com"


def cozylife_login(email, password):
    """One-time: fetch this switch's cloud key and relay from the CozyLife
    account. The password is only sent to CozyLife (HTTPS) and never stored."""
    import urllib.parse
    import urllib.request
    import uuid
    api = CLOUD_API
    ua = {"User-Agent": "CozyLife/1.20.24 okhttp/4.9.0", "Accept": "application/json"}

    def call(path, form=None, params=None):
        url = api + path + ("?" + urllib.parse.urlencode(params) if params else "")
        data = urllib.parse.urlencode(form).encode() if form else None
        req = urllib.request.Request(url, data=data, headers=ua)
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read().decode("utf-8", "replace"))
        if str(body.get("ret")) != "1":
            raise SwitchError("CozyLife: [%s] %s" % (body.get("ret"), body.get("desc")))
        return body.get("info") or {}

    info = call("/api/app/user/login", form={
        "mail": email, "passwd": password, "imei": uuid.uuid4().hex, "lang": "en",
        "platform": "android", "lat": "23.5880", "lng": "58.3829",
        "package_name": "app.cozylife.app", "package_version": "1200240553",
        "user_term_version": "1.0.0", "user_privacy_version": "1.0.0"})
    token = info.get("token")
    lst = call("/api/v2/app/device_with_group/list",
               params={"token": token, "platform": "android", "lang": "en"})
    devices = []
    for sec in ("device_bind", "device_share"):
        devices += (lst.get(sec) or {}).get("list") or []
    for d in devices:
        if str(d.get("device_id")) == C.SWITCH_DEVICE_ID:
            cfg = {"device_id": str(d["device_id"]), "device_key": str(d["device_key"]),
                   "relay_host": str(d.get("ip") or ""), "relay_port": int(d.get("port") or 0),
                   "name": d.get("device_name"), "dpids": d.get("dpid"),
                   "local_ip": d.get("local_ip")}
            write_json(C.CLOUD_FILE, cfg)
            os.chmod(C.CLOUD_FILE, 0o600)
            return cfg, devices
    return None, devices


# ------------------------------------------------------------------ camera
def grab_frame(path=None):
    """Grab one frame from RTSP with ffmpeg. Returns a BGR numpy image or None."""
    import cv2
    path = path or C.LAST_FRAME
    tmp = path + ".grab.jpg"
    cmd = ["ffmpeg", "-loglevel", "error", "-y", "-rtsp_transport", "tcp",
           "-i", C.CAMERA_RTSP, "-frames:v", "1", "-q:v", "3", tmp]
    try:
        subprocess.run(cmd, timeout=15, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except Exception as e:
        log.warning("camera grab failed: %s", e)
        return None
    img = cv2.imread(tmp)
    if img is not None:
        os.replace(tmp, path)
    return img


# ------------------------------------------------------------------ classifier
def roi_edges(img, roi=None):
    """Crop a region and return a blurred edge map (works in IR and daylight)."""
    import cv2
    import numpy as np
    h, w = img.shape[:2]
    x1, y1, x2, y2 = roi or C.ROI
    crop = img[int(y1 * h):int(y2 * h), int(x1 * w):int(x2 * w)]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    tw = 320
    th = max(16, int(gray.shape[0] * tw / max(1, gray.shape[1])))
    gray = cv2.resize(gray, (tw, th), interpolation=cv2.INTER_AREA)
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(gray)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(gray, 30, 90).astype(np.float32) / 255.0
    return cv2.GaussianBlur(edges, (15, 15), 0)


def _similarity(a, b):
    import numpy as np
    if a.shape != b.shape:
        import cv2
        b = cv2.resize(b, (a.shape[1], a.shape[0]))
    a = a - a.mean()
    b = b - b.mean()
    d = float(np.sqrt((a * a).sum() * (b * b).sum()))
    return float((a * b).sum() / d) if d > 1e-9 else 0.0


_ref_cache = {}


def _load_ref(path, roi=None):
    import cv2
    m = os.path.getmtime(path) if os.path.exists(path) else None
    if m is None:
        return None
    key = (path, roi or C.ROI)
    if _ref_cache.get(key, (None,))[0] != m:
        img = cv2.imread(path)
        _ref_cache[key] = (m, roi_edges(img, roi) if img is not None else None)
    return _ref_cache[key][1]


def _tile_sims(e, ref, cols=4, rows=2):
    """Similarity per tile, so a HALF-open roof can never look fully open/closed."""
    import cv2
    if ref.shape != e.shape:
        ref = cv2.resize(ref, (e.shape[1], e.shape[0]))
    h, w = e.shape
    overall = float(ref.mean())
    out = []
    for r in range(rows):
        for c in range(cols):
            ys, ye = r * h // rows, (r + 1) * h // rows
            xs, xe = c * w // cols, (c + 1) * w // cols
            rt = ref[ys:ye, xs:xe]
            if rt.mean() < 0.3 * overall:      # featureless tile in the reference: can't judge it
                continue
            out.append(_similarity(e[ys:ye, xs:xe], rt))
    return out or [0.0]


def classify(img):
    """Return ('open'|'closed'|'unknown', scores dict)."""
    closed_ref = _load_ref(C.CLOSED_REF)
    if img is None or closed_ref is None:
        return "unknown", {"error": "no image" if img is None else "no closed reference"}
    e = roi_edges(img)
    tiles = _tile_sims(e, closed_ref)
    sim = sum(tiles) / len(tiles)
    scores = {"sim_closed": round(sim, 3), "tile_min": round(min(tiles), 3),
              "tile_max": round(max(tiles), 3), "tiles": len(tiles)}
    if len(tiles) < 4:
        scores["warning"] = "roof region has too little detail - enlarge ROI"
        return "unknown", scores

    # CLOSED: the rib pattern matches everywhere in the roof region
    if sim >= C.CLOSED_MIN_SIMILARITY and min(tiles) >= C.CLOSED_MIN_TILE:
        return "closed", scores

    # OPEN needs positive proof that the camera sees normally: the walls/pier
    # (CONTEXT_ROI) must still look like the reference. Otherwise a dark,
    # covered or frozen image would look like "no roof" = open.
    ctx = _similarity(roi_edges(img, C.CONTEXT_ROI), _load_ref(C.CLOSED_REF, C.CONTEXT_ROI))
    scores["context"] = round(ctx, 3)
    if max(tiles) <= C.OPEN_MAX_TILE and ctx >= C.CONTEXT_MIN_SIMILARITY:
        return "open", scores
    return "unknown", scores


# ------------------------------------------------------------------ state for INDI
def roof_state():
    """
    What the camera monitor currently believes.
    Returns dict: live ('open'|'closed'|'unknown'), confirmed ('open'|'closed'|None),
    fresh (bool), age (s).
    """
    st = read_json(C.STATE_FILE, {}) or {}
    age = time.time() - st.get("ts", 0)
    fresh = age <= C.STALE_SECONDS
    return {
        "live": st.get("live", "unknown") if fresh else "unknown",
        "confirmed": st.get("confirmed"),
        "confirmed_ts": st.get("confirmed_ts", 0),
        "fresh": fresh,
        "age": age,
    }


def last_press():
    return read_json(C.PRESS_FILE, {}) or {}


def record_press(target):
    write_json(C.PRESS_FILE, {"ts": time.time(), "target": target})
