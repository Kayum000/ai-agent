import unittest
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


if __name__ == "__main__":
    unittest.main()
