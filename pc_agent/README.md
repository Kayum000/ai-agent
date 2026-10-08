# PC AI Agent — Self-Repair Module

This folder adds a safe self-diagnosis/self-repair layer for the PC agent.

It does not execute arbitrary commands, modify Windows system files, change registry settings, or overwrite source code. Repairs are restricted to the agent's own runtime/ directory.

Use from the existing PC server:

~~~python
from pc_agent.self_repair import diagnose, repair

# GET /health
return {"status": "ok", "self_repair": diagnose()}

# POST /api/mobile/command
if command.strip().lower() in {"self repair", "self-repair", "fix yourself", "নিজেকে ঠিক করো"}:
    return {"response": "Self-repair complete", "diagnostics": repair()}
~~~

For the mobile app, keep the existing LAN endpoint:

http://<PC-LAN-IP>:8765

and the existing /api/mobile/command + X-PC-Agent-Token contract.

The repair layer handles missing runtime directories, missing/corrupt local config, stale temporary files, and basic Python/port diagnostics.

Run directly:

~~~bash
python pc_agent/self_repair.py
~~~

The Android app also tries multiple supported Gemini models automatically when one model returns an access/404 error.
