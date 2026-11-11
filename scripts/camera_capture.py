#!/usr/bin/env python3
"""Capture JPEG frames from the R11 WiFi camera MJPEG stream."""
import os, sys, time, urllib.request

URL = os.environ.get("R11CAM_URL", "http://192.168.31.196:8080/")
outdir = sys.argv[1]
duration = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
interval = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0
os.makedirs(outdir, exist_ok=True)
start = time.time()
last = -1.0
saved = 0
buf = b""
r = urllib.request.urlopen(URL, timeout=10)
while time.time() - start < duration:
    chunk = r.read(65536)
    if not chunk:
        break
    buf += chunk
    while True:
        a = buf.find(b"\xff\xd8")
        if a < 0:
            break
        b = buf.find(b"\xff\xd9", a + 2)
        if b < 0:
            break
        jpg = buf[a:b + 2]
        buf = buf[b + 2:]
        now = time.time() - start
        if now - last >= interval:
            with open(os.path.join(outdir, f"f{now:05.1f}.jpg"), "wb") as f:
                f.write(jpg)
            saved += 1
            last = now
print(f"saved {saved} frames")
