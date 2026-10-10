# My PC AI Agent

Native Android + Windows/macOS/Linux companion agent. The Android app provides Bengali/English AI chat, system speech recognition, Bengali/English speech output, Gemini cloud fallback, and a token-authenticated local PC companion.

## Android features

- Bengali/English Gemini chat; API key is entered by the user and saved only in local Android preferences.
- Voice input uses Android's system speech-recognition activity. This build does not request the app-level microphone permission or use Accessibility Service.
- Text-to-speech replies.
- Open supported phone apps and explicit HTTP(S) websites.
- Optional PC connection with a configurable URL and secret token.
- PC Test button to verify connectivity.
- GitHub Actions builds and uploads the debug APK.

## PC companion setup

Requirements: Python 3.10 or newer; no third-party Python packages are needed.

1. On the PC, download/clone this repository.
2. Open a terminal in the repository folder and run:
   `python pc_agent/server.py`
3. On first run, the server creates a random authentication token and prints it in the terminal. Keep it private. It is also saved in the user's config folder.
4. Find the PC's private LAN IPv4 address (Windows: `ipconfig`; macOS/Linux: `ip addr` or network settings).
5. Connect the phone and PC to the same trusted Wi-Fi network. In Android app Settings, enter `http://PC-LAN-IP:8765` and the token printed by the PC.
6. Tap **PC Test**.

The companion server currently supports allow-listed actions only: open a normal HTTP(S) website, open a browser/Chrome/Notepad/Calculator/file manager/VS Code when available, and report basic system/disk information. Unsupported requests fall back to Gemini chat. It deliberately does **not** execute arbitrary shell commands, scripts, or destructive operations.

## Network and privacy safety

- The PC server listens on the network so the phone can reach it. Use it only on a trusted private LAN.
- Do not expose port 8765 to the public internet, do not configure router port-forwarding, and do not share the token.
- HTTP on a local LAN is not encrypted; use only a trusted network. For remote access, use a properly configured VPN/tunnel rather than public port forwarding.
- Gemini requests are sent to Google's API using the API key you supply. Never commit an API key or PC token to this repository.

## Cloud AI

The app tries `gemini-2.5-flash-lite` and then `gemini-2.5-flash`. Model availability and API quotas are controlled by Google and may change.

## Binary signal, live collector, and screenshot OCR

The PC companion exposes authenticated, signal-only endpoints:

- `POST /api/collector/quotex` — accepts normalized candles/ticks from the local collector.
- `POST /api/binary/signal` — returns `CALL`, `PUT`, or `NO TRADE`; expiry is selected automatically by the existing rule-based market-regime heuristic (60–300 seconds).
- `POST /api/screenshot/analyze` — accepts JSON `{"image_base64":"..."}` (raw base64 or a data URL) and extracts visible text using optional OCR dependencies.
- `POST /api/binary/analyze` — one-request pipeline: optionally OCRs a screenshot, then combines it with fresh cached collector candles/ticks to produce a signal and expiry. Send `{"asset":"EURUSD","image_base64":"..."}`; current collector data must already have been posted to `/api/collector/quotex`. You may also include `candles`/ `ticks` directly.

### Enable screenshot OCR

Install Python packages `Pillow` and `pytesseract`, and install the Tesseract OCR executable for your operating system. OCR is intentionally conservative and does **not** interpret candle shapes or claim to be a vision AI. If the screenshot contains no single unambiguous visible direction label, the result has no direction and should not be used as a trade signal.

For the combined workflow, first POST collector data to `/api/collector/quotex`, then send the screenshot and asset to `POST /api/binary/analyze`. The response includes both `screenshot_analysis` and the signal result. Alternatively, send the OCR response's object as `screenshot_analysis` to `POST /api/binary/signal`, alongside current closed candles. The signal engine checks screenshot age and asset mismatch. Use fresh live data; stale data produces `NO TRADE`. All endpoints require the existing `X-PC-Agent-Token` header. This remains signal-only and never places orders.

Example screenshot request body:

```json
{"image_base64":"<base64-encoded PNG or JPEG>"}
```

The endpoint accepts up to 7.5 MB of decoded image data. Do not send account credentials, cookies, session tokens, or personal information in screenshots.
