"""Optional OCR bridge for chart screenshots.

OCR is deliberately conservative: text extraction is not chart-vision and must not
invent a trade direction from pixels. The signal engine should use NO TRADE when
there is no explicit, unambiguous direction label.
"""
from __future__ import annotations

import base64
import binascii
import re
import time
from typing import Any


def analyze_screenshot(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": "JSON object required"}
    encoded = payload.get("image_base64") or payload.get("screenshot_base64")
    if not isinstance(encoded, str) or not encoded.strip():
        return {"ok": False, "error": "image_base64 is required"}
    encoded = encoded.strip()
    if encoded.startswith("data:") and "," in encoded:
        encoded = encoded.split(",", 1)[1]
    if len(encoded) > 10_000_000:
        return {"ok": False, "error": "Screenshot is too large (max encoded size 10 MB)"}
    try:
        image_bytes = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        return {"ok": False, "error": "Invalid base64 image"}
    if not image_bytes or len(image_bytes) > 7_500_000:
        return {"ok": False, "error": "Screenshot is empty or exceeds 7.5 MB"}
    try:
        from PIL import Image
        import pytesseract
        from io import BytesIO
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        if image.width < 100 or image.height < 100:
            return {"ok": False, "error": "Screenshot must be at least 100x100 pixels"}
        text = pytesseract.image_to_string(image, config="--psm 11")[:12000]
    except ImportError:
        return {
            "ok": False,
            "error": "Screenshot OCR dependencies are missing. Install Pillow and pytesseract, plus the Tesseract OCR executable.",
        }
    except Exception as exc:
        return {"ok": False, "error": f"Could not read screenshot: {type(exc).__name__}"}

    # Asset labels are only accepted when clearly present as text.
    match = re.search(r"\b([A-Z]{3}\s*[/_-]?\s*[A-Z]{3}(?:\s*OTC)?)\b", text.upper())
    asset = re.sub(r"\s+", "", match.group(1)).replace("/", "").replace("-", "").replace("_", "") if match else None
    upper = text.upper()
    # Never infer CALL/PUT merely from candle colors or chart shape.
    directions = set()
    if re.search(r"\b(CALL|BUY|UP|BULLISH)\b", upper):
        directions.add("CALL")
    if re.search(r"\b(PUT|SELL|DOWN|BEARISH)\b", upper):
        directions.add("PUT")
    direction = next(iter(directions)) if len(directions) == 1 else None
    result = {
        "ok": True,
        "asset": asset,
        "direction": direction,
        "confidence": 0.65 if direction else 0.0,
        "observed_at": time.time(),
        "ocr_text": text.strip()[:4000],
        "analysis_mode": "ocr_only_not_visual_chart_ai",
        "note": "OCR can read visible labels only; it does not understand candle patterns. No explicit unambiguous direction label means NO TRADE.",
    }
    return result
