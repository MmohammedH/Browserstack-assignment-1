import os, time, shutil, tempfile, platform, subprocess
from pathlib import Path
from flask import Flask, request, jsonify
import psutil
import requests

app = Flask(__name__)

PORTS = {
    "chrome": 9222,
    "edge": 9224
}


BASE = Path(tempfile.gettempdir()) / "browser_service_profiles"
PROFILES = {
    "chrome": BASE / "chrome_profile",
    "edge": BASE / "edge_profile"
}
BASE.mkdir(parents=True, exist_ok=True)


PROCESSES = {}

def get_browser_path(browser):
    """Return executable path based on OS."""
    system = platform.system().lower()
    if browser == "chrome":
        if system == "windows":
            return r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        elif system == "darwin":
            return "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        else:
            return "google-chrome"
    elif browser == "edge":
        if system == "windows":
            return r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        elif system == "darwin":
            return "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        else:
            return "microsoft-edge"
    return None

def wait_for_debug(port, timeout=10):
    """Wait until debug HTTP endpoint is ready."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=0.5)
            if r.ok:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False

def kill_process_tree(pid):
    """Kill process and its children."""
    try:
        proc = psutil.Process(pid)
        for child in proc.children(recursive=True):
            child.kill()
        proc.kill()
    except psutil.NoSuchProcess:
        pass

@app.route("/start")
def start():
    browser = request.args.get("browser")
    url = request.args.get("url", "http://example.com")
    if browser not in PROFILES:
        return jsonify({"error": "Unsupported browser"}), 400

    exe = get_browser_path(browser)
    if not exe or not Path(exe).exists():
        return jsonify({"error": f"{browser} not found"}), 500

   
    if PROFILES[browser].exists():
        shutil.rmtree(PROFILES[browser], ignore_errors=True)
    PROFILES[browser].mkdir(parents=True, exist_ok=True)

    port = PORTS[browser]
   
    if browser in PROCESSES:
        kill_process_tree(PROCESSES[browser].pid)
        PROCESSES.pop(browser)

    cmd = [
        exe,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={PROFILES[browser]}",
        "--no-first-run",
        "--no-default-browser-check",
        url
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    PROCESSES[browser] = proc

    ready = wait_for_debug(port)
    return jsonify({"status": f"{browser} started", "url": url, "debug_ready": ready})

@app.route("/geturl")
def geturl():
    browser = request.args.get("browser")
    if browser not in PROCESSES:
        return jsonify({"error": f"{browser} not running"}), 400
    port = PORTS[browser]
    try:
        r = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=1)
        tabs = r.json()
        if tabs and "url" in tabs[0]:
            return jsonify({"url": tabs[0]["url"]})
        return jsonify({"error": "No tab found"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/stop")
def stop():
    browser = request.args.get("browser")
    if browser not in PROCESSES:
        return jsonify({"error": f"{browser} not running"}), 400
    kill_process_tree(PROCESSES[browser].pid)
    PROCESSES.pop(browser, None)
    return jsonify({"status": f"{browser} stopped"})

@app.route("/cleanup")
def cleanup():
    browser = request.args.get("browser")
    if browser not in PROFILES:
        return jsonify({"error": "Unsupported browser"}), 400
    if PROFILES[browser].exists():
        shutil.rmtree(PROFILES[browser], ignore_errors=True)
        return jsonify({"status": f"{browser} profile cleaned"})
    return jsonify({"status": "No profile found"})

if __name__ == "__main__":
    app.run(port=5000, debug=True)
