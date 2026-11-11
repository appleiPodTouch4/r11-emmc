#!/usr/bin/env python3
"""Boot test10, capture the UEFI screen, repeat until the camera goes away."""
import json, os, re, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT.parent
IMAGE = WORK / "boot-control/boot-r11-emmc-test11.img"
RUNS = ROOT / "runs"
CAM = "http://192.168.31.196:8080/"
FASTBOOT = "/usr/local/bin/fastboot"
OCR = ROOT / "scripts/ocr-bin"
FASTBOOT_TIMEOUT = 300
README = ROOT / "README.md"
STATUS = RUNS / "status.json"

def status(rnd, phase, detail=""):
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps({
        "round": rnd, "phase": phase, "detail": detail,
        "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False))

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

def ensure_ocr():
    if OCR.exists():
        return
    cache = Path("/tmp/r11-ocr-module-cache")
    cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(["swiftc", "-module-cache-path", str(cache), "-O",
                    str(ROOT / "scripts/ocr.swift"), "-o", str(OCR)],
                   check=True)

def ocr_text(path):
    try:
        p = subprocess.run([str(OCR), str(path)], capture_output=True,
                           text=True, timeout=20)
        return p.stdout
    except Exception:
        return ""

def conclusion(frames):
    text = ""
    # The test screen is in the middle of the capture; the last frames are the
    # Fastboot screen again.  Scan the whole round, not just the tail.
    for p in sorted(frames, key=lambda x: x.name):
        t = ocr_text(p)
        low = t.lower()
        if "time out" in low or "never ready" in low or "r11emmc" in low:
            text = t
            if "never ready" in low:
                break
    low = text.lower()
    cmd0 = "success" if "success" in low else "unknown"
    timeouts = low.count("time out")
    never = "yes" if "never ready" in low else "no"
    psm = re.findall(r"ps=([0-9a-f]{8})", low)
    ints = re.findall(r"int=([0-9a-f]{8})", low)
    return (f"CMD0={cmd0} CMD1_timeouts={timeouts} never_ready={never} "
            f"ps={psm[-1] if psm else '?'} int={ints[-1] if ints else '?'}")

def grab_one_frame(path, timeout=8):
    try:
        r = urllib.request.urlopen(CAM, timeout=timeout)
        buf = b""
        end = time.time() + timeout
        while time.time() < end:
            buf += r.read(65536)
            a = buf.find(b"\xff\xd8")
            b = buf.find(b"\xff\xd9", a + 2) if a >= 0 else -1
            if a >= 0 and b > a:
                path.write_bytes(buf[a:b + 2])
                return True
    except Exception:
        pass
    return False

def wait_for_fastboot_text(timeout=FASTBOOT_TIMEOUT):
    """Wait for the literal Fastboot screen, not just a USB device."""
    ensure_ocr()
    end = time.time() + timeout
    tmp = ROOT / "runs" / "fastboot-check.jpg"
    tmp.parent.mkdir(exist_ok=True)
    while time.time() < end:
        if not camera_has_frame():
            time.sleep(3)
            continue
        if grab_one_frame(tmp):
            text = ocr_text(tmp)
            low = text.lower()
            if "fastboot" in low or "已进入" in text or "fastboot" in text:
                return True
        time.sleep(5)
    return False

def append_readme(rnd, conclusion, status="ok"):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    header = "\n## Automation log\n\n| round | time | status | conclusion |\n|---|---|---|---|\n"
    if not README.exists() or "## Automation log" not in README.read_text():
        with README.open("a") as f:
            f.write(header)
    with README.open("a") as f:
        f.write(f"| {rnd} | {stamp} | {status} | {conclusion} |\n")

def main():
    RUNS.mkdir(exist_ok=True)
    cam_fail = 0
    rnd = 0
    while True:
        rnd += 1
        status(rnd, "waiting camera")
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
            status(rnd, "waiting Fastboot text")
            if not wait_for_fastboot_text():
                f.write("no Fastboot text for 300 s; stopped\n")
                append_readme(rnd, "no Fastboot text for 300 s", "stopped")
                print("FASTBOOT TEXT LOST - stop", flush=True)
                return 0
            status(rnd, "booting test image")
            p = subprocess.run([FASTBOOT, "boot", str(IMAGE)],
                               capture_output=True, text=True)
            f.write(p.stdout + p.stderr + "\n")
        status(rnd, "capturing screen")
        subprocess.run([sys.executable, str(ROOT / "scripts/camera_capture.py"),
                        str(d / "frames"), "55", "1"], check=False)
        ensure_ocr()
        c = conclusion(sorted((d / "frames").glob("*.jpg")))
        with log.open("a") as f:
            f.write(f"CONCLUSION {c}\n")
        append_readme(rnd, c)
        status(rnd, "round done", c)
        print(f"round {rnd} CONCLUSION {c}", flush=True)
        # Wait for the Fastboot screen to come back; this is the stop condition.
        if not wait_for_fastboot_text():
            append_readme(rnd, "Fastboot screen not seen for 300 s", "stopped")
            print("FASTBOOT TEXT LOST - stop", flush=True)
            return 0

if __name__ == "__main__":
    sys.exit(main())
