"""One-request pipeline for cached live collector data plus optional screenshot OCR."""
from __future__ import annotations

from typing import Any

try:
    from pc_agent.binary_signal_engine import generate_binary_signal
    from pc_agent.screenshot_analyzer import analyze_screenshot
except ModuleNotFoundError:  # Supports direct execution from pc_agent/.
    from binary_signal_engine import generate_binary_signal
    from screenshot_analyzer import analyze_screenshot


def analyze_live_with_screenshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyze a screenshot (when supplied) and combine it with fresh collector data.

    Collector candles/ticks remain the primary market evidence. OCR is optional and
    never turns unreadable/ambiguous screenshot text into a direction.
    """
    if not isinstance(payload, dict):
        return {"ok": False, "error": "JSON object required"}

    has_image = bool(payload.get("image_base64") or payload.get("screenshot_base64"))
    screenshot = payload.get("screenshot_analysis")
    if has_image:
        screenshot = analyze_screenshot({
            "image_base64": payload.get("image_base64") or payload.get("screenshot_base64")
        })
        if not screenshot.get("ok"):
            return {"ok": False, "error": "screenshot_analysis_failed",
                    "details": screenshot.get("error", "Unknown screenshot error")}

    signal_payload = {
        "asset": payload.get("asset") or payload.get("symbol") or "",
        "source": "live_collector+screenshot" if screenshot else "live_collector",
    }
    for key in ("candles", "ticks"):
        if key in payload:
            signal_payload[key] = payload[key]
    if isinstance(screenshot, dict):
        signal_payload["screenshot_analysis"] = screenshot

    signal = generate_binary_signal(signal_payload)
    return {
        "ok": bool(signal.get("ok")),
        "pipeline": "collector_plus_optional_screenshot_ocr",
        "screenshot_analysis": screenshot if isinstance(screenshot, dict) else None,
        "signal": signal,
        "execution": "signal_only_no_live_trades",
    }
