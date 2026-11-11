#!/usr/bin/env python3
"""Run each test image exactly once, in order, then stop.

Each round is one test.  After its QR result is decoded, the next test image is
booted.  Nothing is repeated unless it is listed again in tests.json.
"""
import json, re, subprocess, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT.parent
RUNS = ROOT / "runs"
CAM = "http://192.168.31.196:8080/"
FASTBOOT = "/usr/local/bin/fastboot"
OCR = ROOT / "scripts/ocr-bin"
QRDEC = ROOT / "scripts/qrdecode-bin"
STATUS = RUNS / "status.json"
README = ROOT / "README.md"
FASTBOOT_TIMEOUT = 300

def status(round_no, test, phase, detail=""):
    STATUS.parent.mkdir(exist_ok=True)
    STATUS.write_text(json.dumps({
        "round": round_no, "test": test, "phase": phase,
        "detail": detail, "time": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False))

def camera_has_frame(timeout=8):
    try:
        r = urllib.request.urlopen(CAM, timeout=timeout)
        buf = b""; end = time.time() + timeout
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
    cache = Path("/tmp/r11-ocr-module-cache"); cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(["swiftc", "-module-cache-path", str(cache), "-O",
                    str(ROOT / "scripts/ocr.swift"), "-o", str(OCR)], check=True)

def ensure_qrdec():
    if QRDEC.exists():
        return
    cache = Path("/tmp/r11-ocr-module-cache"); cache.mkdir(parents=True, exist_ok=True)
    subprocess.run(["swiftc", "-module-cache-path", str(cache), "-O",
                    str(ROOT / "scripts/qrdecode.swift"), "-o", str(QRDEC)], check=True)

def ocr_text(path, full=False):
    try:
        cmd = [str(OCR), str(path)] + (["--full"] if full else [])
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        return p.stdout
    except Exception:
        return ""

def grab_one_frame(path, timeout=8):
    try:
        r = urllib.request.urlopen(CAM, timeout=timeout)
        buf = b""; end = time.time() + timeout
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

def wait_fastboot(timeout=FASTBOOT_TIMEOUT):
    p = subprocess.run([FASTBOOT, "devices"], capture_output=True, text=True)
    if p.stdout.strip():
        return True
    ensure_ocr()
    end = time.time() + timeout
    tmp = RUNS / "fastboot-check.jpg"; tmp.parent.mkdir(exist_ok=True)
    while time.time() < end:
        if camera_has_frame() and grab_one_frame(tmp):
            text = ocr_text(tmp, full=True).lower()
            if "fastboot" in text or "已进入" in text:
                return True
        time.sleep(5)
    return False

def qr_payload(frames):
    ensure_qrdec()
    for p in sorted(frames, key=lambda x: x.name)[::3]:
        try:
            r = subprocess.run([str(QRDEC), str(p)], capture_output=True,
                               text=True, timeout=6)
            for line in r.stdout.splitlines():
                if line.startswith("R11|"):
                    return line.strip()
        except Exception:
            pass
    return ""

def append_readme(no, test, conclusion, status_text="ok"):
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if not README.exists() or "## Automation log" not in README.read_text():
        README.open("a").write("\n## Automation log\n\n| # | test | time | status | conclusion |\n|---|---|---|---|---|\n")
    with README.open("a") as f:
        f.write(f"| {no} | {test} | {stamp} | {status_text} | {conclusion} |\n")

def main():
    tests = json.loads((ROOT / "tests.json").read_text())
    RUNS.mkdir(exist_ok=True)
    for no, test in enumerate(tests, 1):
        name = test["name"]
        image = WORK / test["image"]
        d = RUNS / f"test{no:03d}-{name}"
        d.mkdir(exist_ok=True)
        if not camera_has_frame():
            status(no, name, "camera lost")
            print(f"test {no} {name}: CAMERA LOST", flush=True)
            return 0
        if not wait_fastboot():
            status(no, name, "fastboot lost")
            append_readme(no, name, "no Fastboot text for 300 s", "stopped")
            print(f"test {no} {name}: FASTBOOT LOST", flush=True)
            return 0
        status(no, name, "booting")
        with (d / "round.log").open("w") as f:
            f.write(f"test {no} {name}\n")
            p = subprocess.run([FASTBOOT, "boot", str(image)],
                               capture_output=True, text=True)
            f.write(p.stdout + p.stderr + "\n")
        status(no, name, "capturing")
        subprocess.run([sys.executable, str(ROOT / "scripts/camera_capture.py"),
                        str(d / "frames"), "65", "1"], check=False)
        status(no, name, "decoding QR")
        qr = qr_payload(sorted((d / "frames").glob("*.jpg")))
        c = "QR " + qr if qr else "QR not decoded"
        append_readme(no, name, c, "ok" if qr else "no-qr")
        status(no, name, "done", c)
        print(f"test {no} {name}: {c}", flush=True)
        # Wait for the next test's Fastboot screen before continuing.
        if not wait_fastboot():
            append_readme(no, name, "next Fastboot not seen for 300 s", "stopped")
            print("NEXT FASTBOOT LOST - stop", flush=True)
            return 0
    status(len(tests), "all", "complete")
    print("ALL TESTS COMPLETE", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
