import unittest
from unittest.mock import patch

from pc_agent.combined_analysis import analyze_live_with_screenshot


class CombinedAnalysisTests(unittest.TestCase):
    @patch("pc_agent.combined_analysis.generate_binary_signal")
    @patch("pc_agent.combined_analysis.analyze_screenshot")
    def test_image_ocr_and_signal_share_one_request(self, ocr, signal):
        ocr.return_value = {"ok": True, "asset": "EURUSD", "direction": None,
                            "confidence": 0.0, "observed_at": 123.0}
        signal.return_value = {"ok": True, "action": "NO TRADE", "expiry_seconds": None}
        result = analyze_live_with_screenshot({
            "asset": "EURUSD", "image_base64": "ZmFrZQ==",
            "candles": [{"timestamp": 1, "open": 1, "high": 1, "low": 1, "close": 1}],
        })
        self.assertTrue(result["ok"])
        self.assertEqual(result["pipeline"], "collector_plus_optional_screenshot_ocr")
        self.assertIsNone(result["screenshot_analysis"]["direction"])
        signal.assert_called_once()
        self.assertEqual(signal.call_args.args[0]["asset"], "EURUSD")
        self.assertIn("screenshot_analysis", signal.call_args.args[0])

    @patch("pc_agent.combined_analysis.analyze_screenshot")
    def test_bad_screenshot_stops_pipeline(self, ocr):
        ocr.return_value = {"ok": False, "error": "Invalid base64 image"}
        result = analyze_live_with_screenshot({"image_base64": "bad"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "screenshot_analysis_failed")

    @patch("pc_agent.combined_analysis.generate_binary_signal")
    def test_collector_only_is_supported(self, signal):
        signal.return_value = {"ok": True, "action": "NO TRADE"}
        result = analyze_live_with_screenshot({"asset": "EURUSD"})
        self.assertTrue(result["ok"])
        self.assertIsNone(result["screenshot_analysis"])
        signal.assert_called_once_with({"asset": "EURUSD", "source": "live_collector"})


if __name__ == "__main__":
    unittest.main()
