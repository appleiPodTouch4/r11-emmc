#!/usr/bin/env python3
"""Tiny live status page for the R11 eMMC loop."""
import json, os, sys, time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
README = ROOT / "README.md"
CAM = "http://192.168.31.196:8080/"

def latest_frame():
    fs = list(RUNS.glob("round*/frames/*.jpg"))
    return max(fs, key=lambda p: p.stat().st_mtime) if fs else None

def readme_log():
    if not README.exists():
        return ""
    s = README.read_text()
    i = s.find("## Automation log")
    return s[i:] if i >= 0 else s[-3000:]

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/status.json":
            b = (RUNS / "status.json").read_bytes() if (RUNS / "status.json").exists() else b"{}"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)
            return
        if self.path.startswith("/latest.jpg"):
            f = latest_frame()
            if f:
                b = f.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(b)
            else:
                self.send_error(404)
            return
        status = {}
        try:
            status = json.loads((RUNS / "status.json").read_text())
        except Exception:
            pass
        html = f"""<!doctype html><meta http-equiv=refresh content=2>
<style>body{{background:#111;color:#ddd;font:14px monospace}}pre{{white-space:pre-wrap}}</style>
<h2>R11 eMMC live status</h2>
<pre>{json.dumps(status, indent=2)}</pre>
<img src="/latest.jpg?{time.time()}" style="max-width:45vw;float:right">
<h3>README automation log</h3><pre>{readme_log()}</pre>
<p><a href="{CAM}">open camera</a></p>"""
        b = html.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a):
        pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8099
    HTTPServer(("127.0.0.1", port), H).serve_forever()
