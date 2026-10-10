# PC Companion — Self-Repair Module

This folder includes a safe self-diagnosis/self-repair helper for the PC companion.

It does not execute arbitrary commands, modify Windows system files, change registry settings, or overwrite source code. Repairs are restricted to the agent's own `runtime/` directory.

Use from Python:

```python
from pc_agent.self_repair import diagnose, repair

print(diagnose())
print(repair())
```

For the mobile app, use the existing LAN endpoint:

```
http://<PC-LAN-IP>:8765
```

The Android app communicates with `/api/mobile/command` using the `X-PC-Agent-Token` header.

The repair layer handles missing runtime directories, missing/corrupt local config, stale temporary files, and basic Python/port diagnostics.

Run directly:

```bash
python pc_agent/self_repair.py
```

The project does not include Gemini integration, cloud AI fallback, or a Gemini API-key setting. Mobile requests are handled locally by built-in allow-listed phone actions or by the PC companion's allow-listed commands; unsupported requests return a message instead of being sent to a cloud model.
