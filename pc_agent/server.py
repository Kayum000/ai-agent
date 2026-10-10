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

try:
    from pc_agent.binary_signal_engine import ingest_collector_payload, generate_binary_signal
    from pc_agent.screenshot_analyzer import analyze_screenshot
    from pc_agent.combined_analysis import analyze_live_with_screenshot
except ModuleNotFoundError:  # Supports running `python pc_agent/server.py` directly.
    from binary_signal_engine import ingest_collector_payload, generate_binary_signal
    from screenshot_analyzer import analyze_screenshot
    from combined_analysis import analyze_live_with_screenshot

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
    """Launch only explicitly allow-listed desktop applications/folders."""
    system = platform.system().lower()
    key = name.lower().strip()
    try:
        if key in {"browser", "web browser", "ব্রাউজার", "ইন্টারনেট"}:
            opened = webbrowser.open("https://www.google.com")
            return bool(opened), "Browser opened." if opened else "No usable browser was found."
        if key in {"file explorer", "explorer", "files", "ফাইল ম্যানেজার"}:
            target = str(Path.home())
            if system == "windows":
                subprocess.Popen(["explorer.exe", target])
            elif system == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
            return True, "File manager opened at your home folder."
        if key in {"downloads", "download folder", "ডাউনলোড", "ডাউনলোড ফোল্ডার"}:
            target = str(Path.home() / "Downloads")
            if not Path(target).is_dir():
                return False, "Downloads folder was not found."
            if system == "windows":
                subprocess.Popen(["explorer.exe", target])
            elif system == "darwin":
                subprocess.Popen(["open", target])
            else:
                subprocess.Popen(["xdg-open", target])
            return True, "Downloads folder opened."
        if key in {"task manager", "টাস্ক ম্যানেজার"}:
            if system == "windows":
                subprocess.Popen(["taskmgr.exe"])
                return True, "Task Manager opened."
            if system == "darwin":
                subprocess.Popen(["open", "-a", "Activity Monitor"])
                return True, "Activity Monitor opened."
            exe = shutil.which("gnome-system-monitor") or shutil.which("xfce4-taskmanager")
            if not exe:
                return False, "No supported system monitor was found."
            subprocess.Popen([exe])
            return True, "System monitor opened."

        if key in {"vscode", "vs code", "visual studio code"}:
            executable = shutil.which("code")
            if not executable:
                return False, "Visual Studio Code was not found on this PC."
            subprocess.Popen([executable])
            return True, "Visual Studio Code opened."

        if key in {"chrome", "google chrome"}:
            if system == "windows":
                candidates = [
                    os.path.expandvars(r"%ProgramFiles%\Google\Chrome\Application\chrome.exe"),
                    os.path.expandvars(r"%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"),
                    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
                ]
                exe = next((p for p in candidates if Path(p).exists()), None)
            elif system == "darwin":
                subprocess.Popen(["open", "-a", "Google Chrome"])
                return True, "Google Chrome opened."
            else:
                exe = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chromium-browser")
            if exe:
                subprocess.Popen([exe])
                return True, "Google Chrome opened."
            return False, "Google Chrome was not found; try 'open browser'."

        if key in {"edge", "microsoft edge"}:
            if system == "windows":
                candidates = [
                    os.path.expandvars(r"%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"),
                    os.path.expandvars(r"%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"),
                ]
                exe = next((p for p in candidates if Path(p).exists()), None)
                if exe:
                    subprocess.Popen([exe])
                    return True, "Microsoft Edge opened."
            elif system == "darwin":
                subprocess.Popen(["open", "-a", "Microsoft Edge"])
                return True, "Microsoft Edge opened."
            else:
                exe = shutil.which("microsoft-edge") or shutil.which("microsoft-edge-stable")
                if exe:
                    subprocess.Popen([exe])
                    return True, "Microsoft Edge opened."
            return False, "Microsoft Edge was not found on this PC."

        if key in {"firefox", "ফায়ারফক্স", "ফায়ারফক্স"}:
            if system == "darwin":
                subprocess.Popen(["open", "-a", "Firefox"])
                return True, "Firefox opened."
            exe = shutil.which("firefox")
            if exe:
                subprocess.Popen([exe])
                return True, "Firefox opened."
            return False, "Firefox was not found on this PC."

        command_map = {
            "notepad": {"windows": ["notepad.exe"], "darwin": ["open", "-a", "TextEdit"], "linux": ["gedit"]},
            "text editor": {"windows": ["notepad.exe"], "darwin": ["open", "-a", "TextEdit"], "linux": ["gedit"]},
            "নোটপ্যাড": {"windows": ["notepad.exe"], "darwin": ["open", "-a", "TextEdit"], "linux": ["gedit"]},
            "calculator": {"windows": ["calc.exe"], "darwin": ["open", "-a", "Calculator"], "linux": ["gnome-calculator"]},
            "calc": {"windows": ["calc.exe"], "darwin": ["open", "-a", "Calculator"], "linux": ["gnome-calculator"]},
            "ক্যালকুলেটর": {"windows": ["calc.exe"], "darwin": ["open", "-a", "Calculator"], "linux": ["gnome-calculator"]},
        }
        cmd = command_map.get(key, {}).get(system)
        if not cmd:
            return False, f"{name} is not supported on {platform.system()}."
        subprocess.Popen(cmd)
        return True, f"{name} opened."
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"Could not open {name}: {exc}"


def handle_command(command: str) -> dict:
    """Parse a deliberately small, safe set of natural-language PC commands."""
    raw = command.strip()
    if not raw:
        return {"ok": False, "handled": False, "response": "কমান্ড খালি। কী করতে হবে লিখুন বা বলুন।"}

    # Normalize common voice-command wrappers without ever treating input as shell code.
    low = re.sub(r"[!?।]+$", "", raw.lower()).strip()
    low = re.sub(r"^(?:siri[,: ]+|please\s+|দয়া করে\s+|দয়া করে\s+)", "", low).strip()
    low = re.sub(r"^(?:pc\s*:\s*|পিসি\s*:\s*)", "", low).strip()
    # Users often append the target device, e.g. "Open YouTube My PC".
    low = re.sub(r"\s+(?:on\s+)?(?:my\s+)?(?:pc|computer|desktop)\s*$", "", low).strip()
    low = re.sub(r"\s+(?:আমার\s+)?(?:পিসি|কম্পিউটারে|কম্পিউটার)\s*$", "", low).strip()

    # Open a user-supplied ordinary website URL only.
    match = re.search(r"""https?://[^\s<>"']+""", raw, flags=re.IGNORECASE)
    open_words = ("open", "launch", "start", "go to", "visit", "browse", "খোলো", "খুলো", "খুলে দাও", "খুলুন", "চালু", "ওপেন", "যাও", "দেখাও", "ওয়েবসাইট", "ওয়েবসাইট")
    has_open_intent = any(w in low for w in open_words)
    if match and has_open_intent:
        target = match.group(0).rstrip(".,)")
        parsed = urlparse(target)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
            return {"ok": False, "handled": True, "response": "নিরাপত্তার জন্য শুধু সাধারণ http/https ওয়েবসাইট খোলা যাবে।"}
        try:
            opened = webbrowser.open(target)
            return {"ok": bool(opened), "handled": True, "action": "open_url",
                    "response": f"Website open request sent: {target}" if opened else f"ব্রাউজার URL খুলতে পারেনি: {target}"}
        except Exception as exc:
            return {"ok": False, "handled": True, "response": f"ওয়েবসাইট খোলা যায়নি: {exc}"}

    site_aliases = {
        "youtube": "https://www.youtube.com",
        "ইউটিউব": "https://www.youtube.com",
        "google": "https://www.google.com",
        "গুগল": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "facebook": "https://www.facebook.com",
        "ফেসবুক": "https://www.facebook.com",
        "github": "https://github.com",
        "chatgpt": "https://chatgpt.com",
        "গুগল ম্যাপ": "https://maps.google.com",
        "google maps": "https://maps.google.com",
    }
    if has_open_intent:
        for alias, target in site_aliases.items():
            if alias in low:
                try:
                    opened = webbrowser.open(target)
                    return {"ok": bool(opened), "handled": True, "action": "open_url",
                            "response": f"{alias.title()} open request sent." if opened else f"{alias.title()} খোলার জন্য PC browser পাওয়া যায়নি।"}
                except Exception as exc:
                    return {"ok": False, "handled": True, "response": f"{alias.title()} খোলা যায়নি: {exc}"}

    # Search requests are limited to a normal browser search URL.
    search_match = re.search(r"(?:search(?:\s+for)?|google|খুঁজো|সার্চ করো|সার্চ)\s+(.+)$", low)
    if search_match:
        from urllib.parse import quote_plus
        query = search_match.group(1).strip()
        if query:
            target = "https://www.google.com/search?q=" + quote_plus(query)
            try:
                opened = webbrowser.open(target)
                return {"ok": bool(opened), "handled": True, "action": "web_search",
                        "response": f"Browser search opened for: {query}" if opened else "PC browser পাওয়া যায়নি; search খোলা যায়নি।"}
            except Exception as exc:
                return {"ok": False, "handled": True, "response": f"Search খোলা যায়নি: {exc}"}

    # System status is read-only.
    if any(w in low for w in ("pc status", "system status", "computer info", "system info", "কম্পিউটারের অবস্থা", "পিসির অবস্থা", "সিস্টেম তথ্য", "পিসির তথ্য")):
        home = Path.home()
        usage = shutil.disk_usage(home)
        total_gb = round(usage.total / (1024 ** 3), 1)
        free_gb = round(usage.free / (1024 ** 3), 1)
        return {
            "ok": True, "handled": True, "action": "system_info",
            "response": f"PC online. OS: {platform.platform()}; device: {socket.gethostname()}; Python: {platform.python_version()}; disk free at home volume: {free_gb} GB / {total_gb} GB."
        }

    # App actions are allow-listed; user input is never passed to a shell.
    app_patterns = [
        (("calculator", "calc", "ক্যালকুলেটর"), "calculator"),
        (("notepad", "নোটপ্যাড", "text editor", "টেক্সট এডিটর"), "notepad"),
        (("file explorer", "explorer", "file manager", "ফাইল ম্যানেজার", "my computer", "this pc", "আমার কম্পিউটার"), "file explorer"),
        (("downloads", "download folder", "ডাউনলোড", "ডাউনলোড ফোল্ডার"), "downloads"),
        (("task manager", "টাস্ক ম্যানেজার"), "task manager"),
        (("vscode", "vs code", "visual studio code"), "vscode"),
        (("chrome", "google chrome", "ক্রোম"), "chrome"),
        (("edge", "microsoft edge"), "edge"),
        (("firefox", "ফায়ারফক্স", "ফায়ারফক্স"), "firefox"),
        (("browser", "web browser", "ব্রাউজার", "ইন্টারনেট"), "browser"),
    ]
    if has_open_intent:
        for words, app in app_patterns:
            if any(w in low for w in words):
                ok, response = open_app(app)
                return {"ok": ok, "handled": True, "action": "open_app", "response": response}

    return {
        "ok": True, "handled": False,
        "response": "এই কমান্ডটি এখনো সমর্থিত নয়। সমর্থিত উদাহরণ: open YouTube/Google/Gmail, open Chrome/Edge/Firefox, open Notepad/Calculator/Downloads/Task Manager/VS Code, search for cats, PC status। নিরাপত্তার জন্য arbitrary terminal command চালানো হয় না।"
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
        if urlparse(self.path).path.rstrip("/") == "/health":
            supplied = self.headers.get("X-PC-Agent-Token", "")
            if not hmac.compare_digest(supplied, TOKEN):
                self._send(401, {"ok": False, "error": "unauthorized", "response": "PC Agent token is incorrect."})
                return
            self._send(200, {"ok": True, "name": APP_NAME, "capabilities": ["open_url", "web_search", "open_allowlisted_app", "open_downloads", "open_task_manager", "system_info", "quotex_collector_ingest", "binary_signal_analysis", "screenshot_ocr_analysis", "combined_live_screenshot_analysis"]})
        else:
            self._send(404, {"ok": False, "error": "not_found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path.rstrip("/")
        if path not in {"/api/mobile/command", "/api/collector/quotex", "/api/binary/signal", "/api/screenshot/analyze", "/api/binary/analyze"}:
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
        max_body = 14 * 1024 * 1024 if path in {"/api/screenshot/analyze", "/api/binary/analyze"} else (512 * 1024 if path != "/api/mobile/command" else MAX_BODY)
        if length < 1 or length > max_body:
            self._send(413, {"ok": False, "error": "invalid_body_size"})
            return
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(body, dict):
                raise ValueError("JSON object required")
            if path == "/api/collector/quotex":
                result = ingest_collector_payload(body)
                self._send(200 if result.get("ok") else 400, result)
                return
            if path == "/api/binary/signal":
                result = generate_binary_signal(body)
                self._send(200 if result.get("ok") else 400, result)
                return
            if path == "/api/screenshot/analyze":
                result = analyze_screenshot(body)
                self._send(200 if result.get("ok") else 400, result)
                return
            if path == "/api/binary/analyze":
                result = analyze_live_with_screenshot(body)
                self._send(200 if result.get("ok") else 400, result)
                return
            command = body.get("command", "")
            if not isinstance(command, str) or len(command) > 2000:
                raise ValueError("command must be text up to 2000 characters")
            result = handle_command(command)
            self._send(200, result)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._send(400, {"ok": False, "handled": False, "error": str(exc)})

    def log_message(self, fmt: str, *args) -> None:
        # Avoid logging command contents or authentication headers.
        print(f"[PC Agent] {self.client_address[0]} - {fmt % args}")


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
