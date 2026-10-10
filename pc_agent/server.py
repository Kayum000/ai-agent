#!/usr/bin/env python3
"""My PC AI Agent companion server.

Only performs explicit, allow-listed local actions. It never executes arbitrary
shell commands or code supplied by a phone.
"""
from __future__ import annotations

import hmac
import json
import os
import platform
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
import re

APP_NAME = "My PC AI Agent"
HOST = os.environ.get("PC_AGENT_HOST", "0.0.0.0")
PORT = int(os.environ.get("PC_AGENT_PORT", "8765"))
MAX_BODY = 8192


def config_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home())))
        path = base / "MyPCAgent"
    else:
        path = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "my-pc-ai-agent"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_token() -> str:
    override = os.environ.get("PC_AGENT_TOKEN", "").strip()
    if override:
        if len(override) < 24:
            raise RuntimeError("PC_AGENT_TOKEN must be at least 24 characters.")
        return override
    path = config_dir() / "token.txt"
    if path.exists():
        token = path.read_text(encoding="utf-8").strip()
        if len(token) >= 24:
            return token
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    print(f"\n{APP_NAME} first-run token (keep private):\n{token}\n")
    print(f"Token saved to: {path}")
    return token


TOKEN = load_token()


def open_app(name: str) -> tuple[bool, str]:
    system = platform.system().lower()
    key = name.lower().strip()
    if key in {"browser", "web browser", "ব্রাউজার", "ইন্টারনেট"}:
        return (webbrowser.open("https://www.google.com"), "Browser opened.")
    if key in {"notepad", "text editor", "নোটপ্যাড"}:
        commands = {
            "windows": ["notepad.exe"],
            "darwin": ["open", "-a", "TextEdit"],
            "linux": ["gedit"],
        }
        cmd = commands.get(system)
    elif key in {"calculator", "calc", "ক্যালকুলেটর"}:
        commands = {
            "windows": ["calc.exe"],
            "darwin": ["open", "-a", "Calculator"],
            "linux": ["gnome-calculator"],
        }
        cmd = commands.get(system)
    elif key in {"file explorer", "explorer", "files", "ফাইল ম্যানেজার"}:
        home = str(Path.home())
        if system == "windows":
            subprocess.Popen(["explorer.exe", home])
        elif system == "darwin":
            subprocess.Popen(["open", home])
        else:
            subprocess.Popen(["xdg-open", home])
        return True, "File manager opened at your home folder."
    elif key in {"vscode", "vs code", "visual studio code"}:
        executable = shutil.which("code")
        if not executable:
            return False, "Visual Studio Code was not found on this PC."
        subprocess.Popen([executable])
        return True, "Visual Studio Code opened."
    elif key in {"chrome", "google chrome"}:
        if system == "windows":
            candidates = [
                os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
            ]
            exe = next((p for p in candidates if Path(p).exists()), None)
            if exe:
                subprocess.Popen([exe])
                return True, "Google Chrome opened."
        elif system == "darwin":
            subprocess.Popen(["open", "-a", "Google Chrome"])
            return True, "Google Chrome opened."
        else:
            exe = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
            if exe:
                subprocess.Popen([exe])
                return True, "Google Chrome/Chromium opened."
        return False, "Google Chrome was not found; try 'open browser'."
    else:
        return False, "This app is not in the safe allow-list."
    if not cmd:
        return False, f"{name} is not supported on {platform.system()}."
    try:
        subprocess.Popen(cmd)
        return True, f"{name} opened."
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not open {name}: {exc}"


def handle_command(command: str) -> dict:
    raw = command.strip()
    if not raw:
        return {"ok": False, "handled": False, "response": "Empty command."}
    low = raw.lower()

    # Only explicit HTTP(S) URLs are opened. No javascript:, file:, or shell URLs.
    match = re.search(r"https?://[^\s<>\"']+", raw, flags=re.IGNORECASE)
    if match and any(w in low for w in ("open", "visit", "go to", "website", "খুলো", "খুলে", "ওয়েবসাইট", "ওয়েবসাইট")):
        target = match.group(0).rstrip(".,)")
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return {"ok": False, "handled": True, "response": "For safety, only a normal http/https website URL can be opened."}
        webbrowser.open(target)
        return {"ok": True, "handled": True, "action": "open_url", "response": f"Website opened: {target}"}

    app_patterns = [
        (("calculator", "calc", "ক্যালকুলেটর"), "calculator"),
        (("notepad", "নোটপ্যাড", "text editor"), "notepad"),
        (("file explorer", "explorer", "file manager", "ফাইল ম্যানেজার"), "file explorer"),
        (("vscode", "vs code", "visual studio code"), "vscode"),
        (("chrome", "google chrome"), "chrome"),
        (("browser", "ব্রাউজার"), "browser"),
    ]
    open_intent = any(w in low for w in ("open", "launch", "start", "খোলো", "খুলে দাও", "চালু", "ওপেন"))
    if open_intent:
        for words, app in app_patterns:
            if any(w in low for w in words):
                ok, response = open_app(app)
                return {"ok": ok, "handled": True, "action": "open_app", "response": response}

    if any(w in low for w in ("pc status", "system status", "computer info", "system info", "কম্পিউটারের অবস্থা", "পিসির অবস্থা", "সিস্টেম তথ্য")):
        home = Path.home()
        usage = shutil.disk_usage(home)
        total_gb = round(usage.total / (1024 ** 3), 1)
        free_gb = round(usage.free / (1024 ** 3), 1)
        return {
            "ok": True, "handled": True, "action": "system_info",
            "response": f"PC online. OS: {platform.platform()}; device: {socket.gethostname()}; Python: {platform.python_version()}; disk free at home volume: {free_gb} GB / {total_gb} GB."
        }

    return {
        "ok": True, "handled": False,
        "response": "This PC agent only performs safe allow-listed actions (open a website, browser, Chrome, Notepad, Calculator, file manager, VS Code, or report basic system info). No command was executed."
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "MyPCAgent/1.0"

    def _send(self, code: int, data: dict) -> None:
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/health":
            self._send(200, {"ok": True, "name": APP_NAME, "capabilities": ["open_url", "open_allowlisted_app", "system_info"]})
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/api/mobile/command":
            self._send(404, {"ok": False, "error": "not_found"})
            return
        supplied = self.headers.get("X-PC-Agent-Token", "")
        if not hmac.compare_digest(supplied, TOKEN):
            self._send(401, {"ok": False, "handled": False, "error": "unauthorized", "response": "PC Agent token is incorrect."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 1 or length > MAX_BODY:
            self._send(413, {"ok": False, "error": "invalid_body_size"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            command = body.get("command", "") if isinstance(body, dict) else ""
            if not isinstance(command, str) or len(command) > 2000:
                raise ValueError("command must be text up to 2000 characters")
            result = handle_command(command)
            self._send(200, result)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send(400, {"ok": False, "handled": False, "error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        # Avoid logging command contents or authentication headers.
        print(f"[PC Agent] {self.address[0]} - {fmt % args}")


def main() -> None:
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"{APP_NAME} listening on http://{HOST}:{PORT}")
    print("Use the PC's LAN IP in the Android app. Keep this on a trusted private network; do not port-forward it.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping PC Agent...")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
