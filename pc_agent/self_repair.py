"""Safe self-diagnostics and self-repair helpers for the PC AI Agent."""
from __future__ import annotations

import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

AGENT_DIR = Path(__file__).resolve().parent
RUNTIME_DIR = AGENT_DIR / "runtime"
LOG_DIR = RUNTIME_DIR / "logs"
TMP_DIR = RUNTIME_DIR / "tmp"
CONFIG_FILE = RUNTIME_DIR / "agent_config.json"

DEFAULT_CONFIG = {
    "host": "0.0.0.0",
    "port": 8765,
    "token_env": "PC_AGENT_TOKEN",
    "version": 1,
}

def _port_state(host: str, port: int) -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.4)
    try:
        return "open" if s.connect_ex((host, port)) == 0 else "free"
    finally:
        s.close()

def diagnose() -> dict[str, Any]:
    port = int(os.getenv("PC_AGENT_PORT", DEFAULT_CONFIG["port"]))
    return {
        "ok": True,
        "python": sys.version.split()[0],
        "agent_dir": str(AGENT_DIR),
        "runtime_dir": str(RUNTIME_DIR),
        "config_exists": CONFIG_FILE.exists(),
        "log_dir_exists": LOG_DIR.exists(),
        "tmp_dir_exists": TMP_DIR.exists(),
        "port": port,
        "port_state": _port_state("127.0.0.1", port),
        "timestamp": time.time(),
    }

def repair() -> dict[str, Any]:
    actions: list[str] = []
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    if not CONFIG_FILE.exists():
        CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
        actions.append("created missing agent_config.json")
    else:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                raise ValueError("config is not an object")
        except Exception:
            backup = CONFIG_FILE.with_suffix(".broken.json")
            CONFIG_FILE.replace(backup)
            CONFIG_FILE.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
            actions.append(f"replaced invalid config; backup={backup.name}")

    for p in TMP_DIR.iterdir():
        try:
            if p.is_file() and (time.time() - p.stat().st_mtime) > 86400:
                p.unlink()
                actions.append(f"removed stale temp file {p.name}")
        except OSError:
            pass

    result = diagnose()
    result["repaired"] = True
    result["actions"] = actions
    return result

if __name__ == "__main__":
    print(json.dumps(repair(), indent=2, ensure_ascii=False))
