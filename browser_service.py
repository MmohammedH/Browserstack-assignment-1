import os
import psutil
import subprocess
import tempfile
from flask import Flask, request, jsonify
import requests
import shutil

app= Flask(__name__)

processes={}

CHROME_PATH=r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

MICROSOFT_EDGE=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

@app.route("/start")
def start_browser():
   browser = request.args.get("browser")
   url = request.args.get("url")
   if not browser or not url:
      return "Missing url parameters",400

   if browser=="chrome":
     path = CHROME_PATH
     port = 9222
   elif browser=="edge":
     path = MICROSOFT_EDGE
     port = 9223
   else:
     return "Unsupported browser",400
   
   try:
     proc = subprocess.Popen([
        CHROME_PATH,
        "--remote-debugging-port=9222",
        url
     ])
     processes[browser]=proc.pid
     return f"{browser} started with PID {proc.pid}",200

   except Exception as e:
     return f"Error with {browser}",500


@app.route("/stop")
def stop_browser():
   browser = request.args.get("browser")
   if not browser or browser not in processes:
      return "Browser not running",400
   
   try:
    pid = processes[browser]
    proc = psutil.Process(pid)
    for child in proc.children(recursive=True):
      child.terminate()
    proc.terminate()
    return f"{browser} stopped",200
   except Exception as e:
    return f"Error stopping {browser}: {str(e)}",500


@app.route("/cleanup")
def cleanup_browser():
   browser= request.args.get("browser")
   if browser == "chrome":
     cache_path=os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\User Data\Default")
   elif browser == "edge":
     cache_path=os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default")
   else:
     return "Unsupported browser",400
    

   try:
     shutil.rmtree(cache_path, ignore_errors=True)
     return f"{browser} data cleaned",200
   except Exception as e:
     return f"Error cleaning {browser}: {str(e)}",500


@app.route("/geturl")
def get_url():
   try:
      data=requests.get("http://localhost:9222/json").json()
      if data and "url" in data[0]:
         return jsonify({"url":data[0]["url"]})
   except Exception:
      pass
   
   return jsonify({"url":"https://example.com"})


if __name__=="__main__":
   app.run(host="127.0.0.1", port=8080)