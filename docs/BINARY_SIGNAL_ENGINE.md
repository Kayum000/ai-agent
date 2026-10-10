# Binary Signal Engine + Quotex Collector bridge

This repository contains a signal-only binary-options analysis endpoint. It does
not submit orders, access balances, or calculate stop-loss/take-profit.

## Authenticated endpoints

Every POST uses the existing PC Agent token in `X-PC-Agent-Token`. Keep the
server on a trusted LAN; do not port-forward it.

- `POST /api/collector/quotex`: receives `asset`, `candles` (OHLC +
  timestamp), and optional `ticks` / `quotes`. Recent data is held in a
  bounded in-memory cache for up to 180 seconds.
- `POST /api/binary/signal`: receives candle/tick data and optional
  `screenshot_analysis`; returns `CALL`, `PUT`, or `NO TRADE` and, when
  justified, a heuristic 60/120/180/300-second expiry. If candles are omitted,
  it uses a fresh cached collector snapshot.

Collector payload shape:
```json
{"asset":"EURUSD_otc","candles":[{"timestamp":1790000000,"open":1.1,"high":1.101,"low":1.099,"close":1.1005}],"ticks":[{"timestamp":1790000000,"price":1.1005}]}
```

Screenshot observation shape:
```json
{"asset":"EURUSD_otc","screenshot_analysis":{"asset":"EURUSD_otc","direction":"CALL","confidence":0.7,"observed_at":1790000000}}
```

The Android app includes a **Chart** button: it lets the user select a chart
screenshot, asks the configured Gemini vision model for a structured observation,
then sends that observation to the PC Agent. The engine compares it with the
fresh Collector stream; an asset mismatch or conflicting direction returns
`NO TRADE`. Screenshot analysis requires a configured Gemini API key and a
connected PC Agent. A screenshot by itself cannot replace the minimum closed-candle
history required by the live signal engine.

## Research safeguards

Uses trend, momentum, range breakout, RSI/wick rejection, candle structure, and
optional fresh tick pressure as independent evidence. Stale data, malformed
candles, weak confluence, and conflicting observations are rejected. The
`confidence_score` is a confluence score, **not** a calibrated win probability.
Expiry is a heuristic and must be walk-forward tested on the intended asset and
payout conditions. No signal is guaranteed. No trade-execution code is present.

## Test
```bash
python -m unittest discover -s tests
```
