import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pc_agent.server import handle_command


class PcCommandTests(unittest.TestCase):
    @patch("pc_agent.server.webbrowser.open", return_value=True)
    def test_bengali_youtube_opens_pc_browser(self, opened):
        result = handle_command("ইউটিউব খোলো")
        self.assertTrue(result["handled"])
        self.assertTrue(result["ok"])
        opened.assert_called_once_with("https://www.youtube.com")

    @patch("pc_agent.server.webbrowser.open", return_value=True)
    def test_go_to_youtube_is_recognized(self, opened):
        result = handle_command("please go to YouTube")
        self.assertTrue(result["handled"])
        opened.assert_called_once_with("https://www.youtube.com")

    @patch("pc_agent.server.webbrowser.open", return_value=True)
    def test_search_command_opens_encoded_search(self, opened):
        result = handle_command("search for cute cats")
        self.assertTrue(result["handled"])
        self.assertEqual(result["action"], "web_search")
        self.assertIn("q=cute+cats", opened.call_args.args[0])

    @patch("pc_agent.server.open_app", return_value=(True, "Downloads folder opened."))
    def test_downloads_folder_command(self, launch):
        result = handle_command("Siri, open Downloads")
        self.assertTrue(result["handled"])
        launch.assert_called_once_with("downloads")

    @patch("pc_agent.server.open_app", return_value=(True, "Task Manager opened."))
    def test_task_manager_command(self, launch):
        result = handle_command("open task manager")
        self.assertTrue(result["handled"])
        launch.assert_called_once_with("task manager")

    def test_unsupported_command_is_not_claimed_as_completed(self):
        result = handle_command("do my homework")
        self.assertFalse(result["handled"])
        self.assertIn("সমর্থিত", result["response"])

    def test_empty_command_has_helpful_error(self):
        result = handle_command("   ")
        self.assertFalse(result["handled"])
        self.assertIn("খালি", result["response"])

    @patch("pc_agent.server.urllib.request.urlopen")
    def test_local_ai_fallback_returns_general_answer(self, mocked_urlopen):
        response = mocked_urlopen.return_value.__enter__.return_value
        response.read.return_value = json.dumps({
            "message": {"content": json.dumps({"mode": "answer", "answer": "Local answer"})}
        }).encode("utf-8")
        from pc_agent.server import local_ai_fallback
        result = local_ai_fallback("Explain something")
        self.assertTrue(result["handled"])
        self.assertEqual(result["response"], "Local answer")

    def test_create_desktop_file_without_overwriting(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "Desktop").mkdir()
            with patch("pc_agent.server.Path.home", return_value=home):
                result = handle_command("create file SiriTest.txt with content: Hello Siri")
                self.assertTrue(result["ok"])
                self.assertEqual((home / "Desktop" / "SiriTest.txt").read_text(encoding="utf-8"), "Hello Siri")
                again = handle_command("create file SiriTest.txt with content: overwrite")
                self.assertFalse(again["ok"])
                self.assertEqual((home / "Desktop" / "SiriTest.txt").read_text(encoding="utf-8"), "Hello Siri")

    def test_create_desktop_folder(self):
        with TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "Desktop").mkdir()
            with patch("pc_agent.server.Path.home", return_value=home):
                result = handle_command("create folder Reports")
                self.assertTrue(result["ok"])
                self.assertTrue((home / "Desktop" / "Reports").is_dir())


if __name__ == "__main__":
    unittest.main()
