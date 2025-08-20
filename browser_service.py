import os
import psutil
import subprocess
import tempfile
import shutil
import time
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

CHROME_PATH = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
MICROSOFT_EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

processes = {}

PORTS = {"chrome": 9222, "edge": 9223}
PROFILE_PATHS = {
    "chrome": os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default"),
    "edge": os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default")
}

def kill_existing_instances(browser):
    exe_name = "chrome.exe" if browser == "chrome" else "msedge.exe"
    for proc in psutil.process_iter(['name']):
        if proc.info['name'] == exe_name:
            proc.kill()

def start_browser_process(browser, url):
    path = CHROME_PATH if browser == "chrome" else MICROSOFT_EDGE
    port = PORTS[browser]
    kill_existing_instances(browser)
    user_data_dir = tempfile.mkdtemp()
    proc = subprocess.Popen([
        path,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={user_data_dir}",
        url
    ])
    time.sleep(2)
    return proc.pid, user_data_dir, port

@app.route("/start")
def start_browser():
    browser = request.args.get("browser", "").lower()
    url = request.args.get("url")
    if not browser or not url:
        return "Missing url parameters", 400
    try:
        pid, user_data_dir, port = start_browser_process(browser, url)
        processes[browser] = {"pid": pid, "user_data_dir": user_data_dir, "port": port}
        return f"{browser} started with PID {pid}", 200
    except Exception as e:
        return f"Error starting {browser}: {str(e)}", 500

@app.route("/stop")
def stop_browser():
    browser = request.args.get("browser", "").lower()
    if browser not in processes:
        return "Browser not running", 400
    info = processes[browser]
    pid = info["pid"]
    if psutil.pid_exists(pid):
        try:
            proc = psutil.Process(pid)
            for child in proc.children(recursive=True):
                child.terminate()
            proc.terminate()
        except Exception as e:
            return f"Error stopping {browser}: {str(e)}", 500
    processes.pop(browser)
    return f"{browser} stopped", 200

@app.route("/cleanup")
def cleanup_browser():
    browser = request.args.get("browser", "").lower()
    if browser not in PROFILE_PATHS:
        return "Unsupported browser", 400
    if browser in processes:
        stop_browser()
    info = processes.get(browser)
    if info and os.path.exists(info.get("user_data_dir", "")):
        shutil.rmtree(info["user_data_dir"], ignore_errors=True)
    cache_path = PROFILE_PATHS[browser]
    try:
        shutil.rmtree(cache_path, ignore_errors=True)
        return f"{browser} data cleaned", 200
    except Exception as e:
        return f"Error cleaning {browser}: {str(e)}", 500

@app.route("/geturl")
def get_url():
    browser = request.args.get("browser", "").lower()
    if browser not in processes:
        return jsonify({"error": f"{browser} not running", "url": None}), 400
    port = processes[browser]["port"]
    for _ in range(5):
        try:
            response = requests.get(f"http://localhost:{port}/json", timeout=1).json()
            for tab in response:
                if tab.get("type") == "page":
                    return jsonify({"url": tab.get("url")})
        except requests.exceptions.RequestException:
            time.sleep(0.5)
    return jsonify({"error": "DevTools not available yet", "url": None})

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080)
