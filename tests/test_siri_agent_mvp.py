import unittest
from unittest.mock import patch
import siri_agent_mvp

class SafeActionTests(unittest.TestCase):
    @patch('siri_agent_mvp.platform.system', return_value='Windows')
    def test_only_fixed_apps_are_allowed(self, _system):
        self.assertEqual(siri_agent_mvp.safe_app_command('notepad'), ['notepad.exe'])
        self.assertEqual(siri_agent_mvp.safe_app_command('calculator'), ['calc.exe'])
        self.assertIsNone(siri_agent_mvp.safe_app_command('powershell'))
        self.assertIsNone(siri_agent_mvp.safe_app_command('delete_files'))
        self.assertIsNone(siri_agent_mvp.safe_app_command('notepad.exe & whoami'))

    @patch('siri_agent_mvp.platform.system', return_value='Linux')
    def test_actions_disabled_off_windows(self, _system):
        self.assertIsNone(siri_agent_mvp.safe_app_command('notepad'))
        self.assertIsNone(siri_agent_mvp.safe_app_command('calculator'))

if __name__ == '__main__':
    unittest.main()
