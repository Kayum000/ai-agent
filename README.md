# Siri — My PC AI Agent

Native Android + Windows/macOS/Linux companion. The Android app provides Bengali/English voice input, text-to-speech replies, safe phone actions, and an optional authenticated local PC companion.

**This project does not use Gemini or any cloud AI API.** There is no Gemini API-key setting or Gemini fallback. Requests are handled by the app's built-in allow-listed phone actions and the PC companion's allow-listed actions. Unsupported requests receive a message explaining that the command is not supported.

## Android features

- Bengali/English voice input through Android's system speech-recognition activity.
- Text-to-speech replies; Siri prioritizes an installed female-sounding Bengali voice, then an English female-sounding voice when available. Actual voices depend on the phone's TTS engine and installed language data.
- Open supported phone apps and explicit HTTP(S) websites.
- Optional PC connection with a configurable URL and secret token.
- PC Test button to verify connectivity.
- GitHub Actions builds and uploads a debug APK.

## PC companion setup

Requirements: Python 3.10 or newer; no third-party Python packages are needed for the basic PC companion.

1. On the PC, download/clone this repository.
2. Open a terminal in the repository folder and run: `python pc_agent/server.py`
3. On first run, the server creates a random authentication token and prints it in the terminal. Keep it private. It is also saved in the user's config folder.
4. Find the PC's private LAN IPv4 address (Windows: `ipconfig`; macOS/Linux: `ip addr` or network settings).
5. Connect the phone and PC to the same trusted Wi-Fi network. In Siri Settings, enter `http://PC-LAN-IP:8765` and the token printed by the PC.
6. Tap **PC Test**.

The companion supports allow-listed actions only: open normal HTTP(S) websites, open YouTube/Google/Gmail/Facebook/GitHub/ChatGPT, open Chrome/Edge/Firefox/Notepad/Calculator/Downloads/Task Manager/file manager/VS Code when available, search the web, and report basic system/disk information. You can prefix commands with `PC:` to explicitly target the computer, or `PHONE:` to target the Android phone. Bengali and English command variants are supported for common actions. Unsupported requests are not sent to a cloud model. The server deliberately does **not** execute arbitrary shell commands, scripts, or destructive operations.

## Network and privacy safety

- The PC server listens on the network so the phone can reach it. Use it only on a trusted private LAN.
- Do not expose port 8765 to the public internet, do not configure router port-forwarding, and do not share the token.
- HTTP on a local LAN is not encrypted; use only a trusted network. For remote access, use a properly configured VPN/tunnel rather than public port forwarding.
- The app has no Gemini integration and does not send prompts to Google's Gemini API.

## Binary signal, live collector, and screenshot OCR

The PC companion exposes authenticated, signal-only endpoints:

- `POST /api/collector/quotex` — accepts normalized candles/ticks from the local collector.
- `POST /api/binary/signal` — returns `CALL`, `PUT`, or `NO TRADE`; expiry is selected automatically by the existing rule-based market-regime heuristic (60–300 seconds).
- `POST /api/screenshot/analyze` — accepts JSON `{"image_base64":"..."}` (raw base64 or a data URL) and extracts visible text using optional OCR dependencies.
- `POST /api/binary/analyze` — one-request pipeline: optionally OCRs a screenshot, then combines it with fresh cached collector candles/ticks to produce a signal and expiry. Send `{"asset":"EURUSD","image_base64":"..."}`; current collector data must already have been posted to `/api/collector/quotex`. You may also include `candles`/`ticks` directly.

### Enable screenshot OCR

Install Python packages `Pillow` and `pytesseract`, and install the Tesseract OCR executable for your operating system. OCR is intentionally conservative and does **not** interpret candle shapes or claim to be a vision AI. If the screenshot contains no single unambiguous visible direction label, the result has no direction and should not be used as a trade signal.

All endpoints require the existing `X-PC-Agent-Token` header. This remains signal-only and never places orders. The signal engine checks screenshot age and asset mismatch. Use fresh live data; stale data produces `NO TRADE`.

Example screenshot request body:

```json
{"image_base64":"<base64-encoded PNG or JPEG>"}
```

The endpoint accepts up to 7.5 MB of decoded image data. Do not send account credentials, cookies, session tokens, or personal information in screenshots.
