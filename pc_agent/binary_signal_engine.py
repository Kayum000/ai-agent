"""Signal-only adaptive binary-options engine; no order execution or SL/TP."""
from __future__ import annotations
from datetime import datetime
import math
import threading
import time
from typing import Any

_LOCK = threading.Lock()
_LATEST: dict[str, dict[str, Any]] = {}
_LATEST_AT: dict[str, float] = {}
MAX_AGE = 180
MAX_CANDLES = 500


def _num(value):
    try:
        n = float(value)
        return n if math.isfinite(n) else None
    except (TypeError, ValueError):
        return None


def _ts(value):
    n = _num(value)
    if n is not None:
        return n / 1000 if n > 10_000_000_000 else n
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _candles(rows):
    out = []
    if not isinstance(rows, list):
        return out
    for r in rows[-MAX_CANDLES:]:
        if not isinstance(r, dict):
            continue
        ts = _ts(r.get("timestamp", r.get("time")))
        vals = [_num(r.get(k)) for k in ("open", "high", "low", "close")]
        if ts is None or any(v is None or v <= 0 for v in vals):
            continue
        o, h, l, c = vals
        if h < max(o, c, l) or l > min(o, c, h):
            continue
        out.append({"timestamp": ts, "open": o, "high": h, "low": l, "close": c})
    unique = {r["timestamp"]: r for r in out}
    return [unique[k] for k in sorted(unique)]


def _ema(values, span):
    a = 2.0 / (span + 1.0)
    result = values[0]
    for v in values[1:]:
        result = a * v + (1 - a) * result
    return result


def _rsi(values, period=14):
    changes = [values[i] - values[i-1] for i in range(max(1, len(values)-period), len(values))]
    gain = sum(max(v, 0) for v in changes) / max(1, len(changes))
    loss = sum(max(-v, 0) for v in changes) / max(1, len(changes))
    if loss == 0:
        return 100.0 if gain > 0 else 50.0
    return 100 - 100 / (1 + gain / loss)


def _asset_key(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalnum())


def _direction(value):
    s = str(value or "").strip().upper()
    if s in {"CALL", "UP", "BUY", "BULLISH", "RISE"}: return "CALL"
    if s in {"PUT", "DOWN", "SELL", "BEARISH", "FALL"}: return "PUT"
    return None


def ingest_collector_payload(payload):
    """Validate and cache recent candle/tick snapshots separately for each asset."""
    global _LATEST, _LATEST_AT
    if not isinstance(payload, dict):
        return {"ok": False, "error": "JSON object required"}
    fallback_asset = str(payload.get("asset") or payload.get("symbol") or payload.get("active_asset") or "").strip()[:80]
    raw_candles = payload.get("candles") or []
    raw_ticks = payload.get("ticks") or payload.get("quotes") or []
    candle_groups = {}
    tick_groups = {}
    if isinstance(raw_candles, list):
        for row in raw_candles[-MAX_CANDLES * 20:]:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset") or row.get("symbol") or fallback_asset or "UNKNOWN").strip()[:80]
            candle_groups.setdefault(asset, []).append(row)
    if isinstance(raw_ticks, list):
        for row in raw_ticks[-2000:]:
            if not isinstance(row, dict):
                continue
            asset = str(row.get("asset") or row.get("symbol") or fallback_asset or "UNKNOWN").strip()[:80]
            ts = _ts(row.get("timestamp", row.get("time")))
            price = _num(row.get("price", row.get("close")))
            if ts is not None and price is not None and price > 0:
                tick_groups.setdefault(asset, []).append({"timestamp": ts, "price": price})
    assets = set(candle_groups) | set(tick_groups)
    if not assets:
        return {"ok": False, "error": "No valid candles or ticks"}
    accepted_candles = accepted_ticks = 0
    now = time.time()
    with _LOCK:
        for asset in assets:
            candles = _candles(candle_groups.get(asset, []))
            ticks = tick_groups.get(asset, [])
            previous = _LATEST.get(asset)
            # Tick-only updates must not erase candle history for that asset.
            if previous:
                if not candles:
                    candles = previous.get("candles", [])
                if not ticks:
                    ticks = previous.get("ticks", [])
                elif previous.get("ticks"):
                    ticks = (previous["ticks"] + ticks)[-2000:]
            _LATEST[asset] = {"asset": asset, "candles": candles, "ticks": ticks, "received_at": now}
            _LATEST_AT[asset] = now
            accepted_candles += len(candle_groups.get(asset, []))
            accepted_ticks += len(tick_groups.get(asset, []))
    return {"ok": True, "assets": sorted(assets), "accepted_candles": accepted_candles, "accepted_ticks": accepted_ticks}


def latest_collector_payload(asset=None):
    with _LOCK:
        if asset:
            key = str(asset).strip()
            exact = _LATEST.get(key)
            if exact and time.time() - _LATEST_AT.get(key, 0.0) <= MAX_AGE:
                return dict(exact)
            normalized = _asset_key(key)
            match = next((name for name in _LATEST if _asset_key(name) == normalized), None)
            snap = _LATEST.get(match) if match else None
            stamp = _LATEST_AT.get(match, 0.0) if match else 0.0
            return dict(snap) if snap and time.time() - stamp <= MAX_AGE else None
        fresh = [(stamp, _LATEST[key]) for key, stamp in _LATEST_AT.items() if time.time() - stamp <= MAX_AGE]
        return dict(max(fresh, key=lambda item: item[0])[1]) if fresh else None


def generate_binary_signal(payload):
    """Return CALL/PUT/NO TRADE and a heuristic 1–5 minute expiry."""
    if not isinstance(payload, dict):
        return {"ok": False, "action": "NO TRADE", "reason": "JSON object required"}
    asset = str(payload.get("asset") or payload.get("symbol") or "").strip()[:80]
    rows = payload.get("candles")
    ticks = payload.get("ticks")
    source = str(payload.get("source") or "live_collector")
    if not isinstance(rows, list) or not rows:
        cached = latest_collector_payload(asset or None)
        if cached:
            rows, ticks, asset, source = cached["candles"], ticks or cached["ticks"], asset or cached["asset"], "live_collector"
    x = _candles(rows)
    if len(x) < 60:
        return {"ok": True, "action": "NO TRADE", "asset": asset or "UNKNOWN",
                "reason": "কমপক্ষে ৬০টি বৈধ closed candle দরকার", "data_candles": len(x), "source": source}
    now = time.time()
    last, prev = x[-1], x[-2]
    age = now - last["timestamp"]
    if age < -30 or age > MAX_AGE:
        return {"ok": True, "action": "NO TRADE", "asset": asset or "UNKNOWN",
                "reason": "Collector data stale or timestamp invalid", "data_age_seconds": round(age, 1), "source": source}
    closes = [r["close"] for r in x]
    highs, lows = [r["high"] for r in x], [r["low"] for r in x]
    e8, e21, e50 = _ema(closes[-80:], 8), _ema(closes[-100:], 21), _ema(closes[-150:], 50)
    recent_range = sum(r["high"]-r["low"] for r in x[-14:]) / 14
    if recent_range <= 0:
        return {"ok": True, "action": "NO TRADE", "asset": asset or "UNKNOWN", "reason": "Price range too flat", "source": source}
    rsi = _rsi(closes)
    move = closes[-1] - closes[-4]
    body = last["close"] - last["open"]
    candle_range = max(last["high"]-last["low"], 1e-12)
    upper = last["high"] - max(last["open"], last["close"])
    lower = min(last["open"], last["close"]) - last["low"]
    votes = []
    if e8 > e21 > e50 and last["close"] > e8: votes.append(("CALL", 2.0, "EMA trend alignment"))
    elif e8 < e21 < e50 and last["close"] < e8: votes.append(("PUT", 2.0, "EMA trend alignment"))
    if move > recent_range*.35: votes.append(("CALL", 1.4, "positive short momentum"))
    elif move < -recent_range*.35: votes.append(("PUT", 1.4, "negative short momentum"))
    hi20, lo20 = max(highs[-21:-1]), min(lows[-21:-1])
    if last["close"] > hi20: votes.append(("CALL", 2.0, "20-candle breakout"))
    elif last["close"] < lo20: votes.append(("PUT", 2.0, "20-candle breakdown"))
    if rsi <= 28 and lower > abs(body)*.8: votes.append(("CALL", 1.0, "oversold RSI plus rejection wick"))
    elif rsi >= 72 and upper > abs(body)*.8: votes.append(("PUT", 1.0, "overbought RSI plus rejection wick"))
    if body > candle_range*.65 and last["close"] > prev["close"]: votes.append(("CALL", .7, "strong bullish candle"))
    elif body < -candle_range*.65 and last["close"] < prev["close"]: votes.append(("PUT", .7, "strong bearish candle"))
    if isinstance(ticks, list):
        prices = []
        for t in ticks[-100:]:
            if not isinstance(t, dict): continue
            ts, p = _ts(t.get("timestamp", t.get("time"))), _num(t.get("price", t.get("close")))
            if ts is not None and p is not None and p > 0 and now-ts <= 45: prices.append(p)
        if len(prices) >= 8:
            delta = prices[-1]-prices[0]
            if delta > recent_range*.08: votes.append(("CALL", 1.0, "fresh tick pressure up"))
            elif delta < -recent_range*.08: votes.append(("PUT", 1.0, "fresh tick pressure down"))
    screenshot = payload.get("screenshot_analysis")
    screenshot_note = None
    if isinstance(screenshot, dict):
        sa = str(screenshot.get("asset") or "").strip()
        if sa and asset and _asset_key(sa) != _asset_key(asset):
            return {"ok": True, "action": "NO TRADE", "asset": asset, "reason": "Screenshot/live asset mismatch", "source": "live_collector+screenshot"}
        st = _ts(screenshot.get("observed_at"))
        if st is not None and abs(now-st) > MAX_AGE:
            screenshot_note = "stale screenshot observation ignored"
        else:
            sd, sc = _direction(screenshot.get("direction") or screenshot.get("bias")), _num(screenshot.get("confidence")) or 0
            if sd and sc >= .65:
                existing = {d: sum(w for a,w,_ in votes if a == d) for d in ("CALL","PUT")}
                screenshot_note = "screenshot/live conflict" if votes and existing["CALL" if sd=="PUT" else "PUT"] >= existing[sd] else "screenshot observation added"
                votes.append((sd, min(1.0, max(0.0, sc)), "screenshot chart observation"))
    cw, pw = sum(w for a,w,_ in votes if a=="CALL"), sum(w for a,w,_ in votes if a=="PUT")
    total = cw + pw
    if total <= 0:
        return {"ok": True, "action": "NO TRADE", "asset": asset or "UNKNOWN", "reason": "No clear confluence", "regime": "unclear", "rsi14": round(rsi,1), "source": source}
    action = "CALL" if cw > pw else "PUT" if pw > cw else "NO TRADE"
    agreement = abs(cw-pw)/total
    aligned = sum(1 for a,_,_ in votes if a==action) if action!="NO TRADE" else 0
    if (screenshot_note and "conflict" in screenshot_note) or action=="NO TRADE" or agreement < .55 or aligned < 3:
        action = "NO TRADE"
    trend_strength = abs(e8-e21)/max(last["close"], 1e-12)
    volatility = recent_range/max(last["close"], 1e-12)
    if action == "NO TRADE":
        expiry, regime = None, "unclear"
        reason = "Insufficient agreement or conflicting evidence"
    elif trend_strength >= .00035 and agreement >= .72 and not (43 <= rsi <= 58):
        expiry, regime, reason = 300, "trend", "Confluent evidence; expiry is a heuristic, not a win guarantee"
    elif volatility >= .0015:
        expiry, regime, reason = 60, "high_volatility", "High volatility: shorter expiry heuristic"
    elif rsi <= 32 or rsi >= 68:
        expiry, regime, reason = 120, "reversal_or_range", "Range/reversal conditions"
    elif trend_strength >= .00015:
        expiry, regime, reason = 180, "moderate_trend", "Moderate trend conditions"
    else:
        expiry, regime, reason = 120, "mixed", "Mixed market conditions"
    evidence = [why for a,_,why in votes if action!="NO TRADE" and a==action]
    return {"ok": True, "action": action, "binary_direction": {"CALL":"UP","PUT":"DOWN"}.get(action),
            "asset": asset or "UNKNOWN", "expiry_seconds": expiry,
            "confidence_score": round(agreement*100,1), "confidence_is_calibrated_probability": False,
            "regime": regime, "rsi14": round(rsi,1), "data_candles": len(x),
            "data_age_seconds": round(age,1), "evidence": evidence, "screenshot_note": screenshot_note,
            "source": source + ("+screenshot" if isinstance(screenshot,dict) else ""),
            "execution": "signal_only_no_live_trades", "reason": reason}
