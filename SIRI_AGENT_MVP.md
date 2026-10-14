# Siri Agent — Safe MVP

Siri Agent is a local-first Bengali/English assistant for Windows PC with a browser dashboard.

## MVP features
- Browser chat using a local Ollama model.
- Browser speech recognition when supported and speech synthesis for replies.
- Confirm-before-action buttons for fixed Windows apps: Notepad and Calculator.
- Web research opens a DuckDuckGo search after confirmation.
- Server binds to 127.0.0.1 only, bounds request sizes, and never executes arbitrary shell commands or model-generated code.
- No file deletion, messaging, purchases, credential access, public hosting, or real-money trading.

## Requirements
- Windows 10/11 and Python 3.10+
- Ollama installed and running
- Local model: ollama pull qwen2.5:3b

## Run
From the repository folder, run:

    ollama pull qwen2.5:3b
    python siri_agent_mvp.py

Open http://127.0.0.1:8787. To use another locally installed Ollama model, set OLLAMA_MODEL before starting the server. The dashboard is not exposed to the LAN.

## Initial test checklist
1. Verify the health status reports Ollama online.
2. Ask a question in Bengali and another in English.
3. Try Speak if browser speech recognition is supported and grant microphone permission.
4. Confirm Notepad/Calculator opens only after the confirmation prompt.
5. Cancel confirmation and verify no app opens.
6. Search a harmless topic and verify confirmation appears before the browser opens.
7. Send an unknown action to /api/action; it should return HTTP 403.
8. Stop Ollama and verify chat shows a controlled unavailable error.
9. Verify the server binds only to 127.0.0.1.

## Safety notes
- Local model inference is not a guarantee of accuracy.
- Browser speech recognition may use a browser/OS provider and may not be fully offline; text chat and Ollama inference are local.
- Never expose port 8787 publicly or configure router port forwarding.
- This is a restricted MVP, not a fully autonomous agent.