import base64
import unittest

from pc_agent.screenshot_analyzer import analyze_screenshot


class ScreenshotAnalyzerTests(unittest.TestCase):
    def test_requires_image(self):
        result = analyze_screenshot({})
        self.assertFalse(result["ok"])
        self.assertIn("image_base64", result["error"])

    def test_rejects_invalid_base64(self):
        result = analyze_screenshot({"image_base64": "not an image!!!"})
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "Invalid base64 image")

    def test_rejects_oversized_encoded_input(self):
        result = analyze_screenshot({"image_base64": "A" * 10_000_001})
        self.assertFalse(result["ok"])
        self.assertIn("too large", result["error"])


if __name__ == "__main__":
    unittest.main()
