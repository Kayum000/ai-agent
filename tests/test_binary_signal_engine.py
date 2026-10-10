import time
import unittest
from pc_agent.binary_signal_engine import _candles, generate_binary_signal, ingest_collector_payload, latest_collector_payload


def candles(count=100, trend=1.0):
    now = int(time.time() // 60) * 60
    rows, price = [], 1.1
    for i in range(count):
        close = price + trend * (i+1) * 0.0001
        rows.append({"timestamp": now-(count-i)*60, "open": price,
                     "high": max(price,close)+0.00002, "low": min(price,close)-0.00002, "close": close})
        price = close
    return rows


class SignalTests(unittest.TestCase):
    def test_validate_candles(self):
        self.assertEqual(len(_candles(candles())), 100)
        self.assertEqual(_candles([{"timestamp":"bad"}]), [])

    def test_signal_is_signal_only(self):
        r = generate_binary_signal({"asset":"EURUSD", "candles":candles()})
        self.assertTrue(r["ok"])
        self.assertIn(r["action"], {"CALL","PUT","NO TRADE"})
        self.assertEqual(r["execution"], "signal_only_no_live_trades")
        self.assertNotIn("stop_loss", r)
        self.assertNotIn("take_profit", r)

    def test_stale_data_no_trade(self):
        rows = candles()
        for row in rows: row["timestamp"] -= 600
        self.assertEqual(generate_binary_signal({"candles":rows})["action"], "NO TRADE")

    def test_collector_cache(self):
        r = ingest_collector_payload({"asset":"EURUSD", "candles":candles()})
        self.assertTrue(r["ok"])
        self.assertIsNotNone(latest_collector_payload())


if __name__ == "__main__":
    unittest.main()
