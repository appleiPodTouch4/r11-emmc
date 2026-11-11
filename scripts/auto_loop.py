#!/usr/bin/env python3
"""Boot test10, capture the UEFI screen, repeat until the camera goes away."""
import os, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT.parent
IMAGE = WORK / "boot-control/boot-r11-emmc-test10.img"
RUNS = ROOT / "runs"
CAM = "http://192.168.31.196:8080/"
FASTBOOT = "/usr/local/bin/fastboot"

def camera_has_frame(timeout=8):
    try:
        r = urllib.request.urlopen(CAM, timeout=timeout)
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            buf += r.read(65536)
            a = buf.find(b"\xff\xd8")
            if a >= 0 and buf.find(b"\xff\xd9", a + 2) > a:
                return True
    except Exception:
        pass
    return False

def fastboot_ready(timeout=120):
    end = time.time() + timeout
    while time.time() < end:
        p = subprocess.run([FASTBOOT, "devices"], capture_output=True, text=True)
        if p.stdout.strip():
            return True
        time.sleep(2)
    return False

def main():
    RUNS.mkdir(exist_ok=True)
    cam_fail = 0
    rnd = 0
    while True:
        rnd += 1
        if not camera_has_frame():
            cam_fail += 1
            print(f"camera missing ({cam_fail}/3)", flush=True)
            if cam_fail >= 3:
                print("CAMERA LOST - stop", flush=True)
                return 0
            time.sleep(5)
            continue
        cam_fail = 0
        d = RUNS / f"round{rnd:03d}"
        d.mkdir(exist_ok=True)
        log = d / "round.log"
        with log.open("w") as f:
            f.write(f"round {rnd}\n")
            if not fastboot_ready():
                f.write("fastboot not ready; skipped\n")
                continue
            p = subprocess.run([FASTBOOT, "boot", str(IMAGE)],
                               capture_output=True, text=True)
            f.write(p.stdout + p.stderr + "\n")
        subprocess.run([sys.executable, str(ROOT / "scripts/camera_capture.py"),
                        str(d / "frames"), "55", "1"], check=False)
        # The test image resets after its countdown; wait for the auto-fastboot loop.
        fastboot_ready(120)
        print(f"round {rnd} captured", flush=True)

if __name__ == "__main__":
    sys.exit(main())
