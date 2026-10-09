import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtWidgets import QApplication, QMainWindow, QPlainTextEdit
from playlite.automation import Automation, execute_command, settings_for
from playlite.background_tasks import BackgroundTasks
from playlite.editor import MetadataEditor

APP = QApplication.instance() or QApplication([])


def wait(predicate):
    deadline = time.monotonic() + 5
    while not predicate() and time.monotonic() < deadline:
        APP.processEvents(); time.sleep(.01)
    assert predicate(), 'Automation did not finish'
    APP.processEvents()


class AutomationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'Folder with spaces'; self.root.mkdir()
        self.game = {'Id': 'one', 'Name': 'Name $(not-a-command)', 'InstallDirectory': str(self.root),
                     'Automation': {'enabled': True, 'timeout': 2, 'before_launch': '', 'after_launch': '', 'after_exit': ''}}
        self.action = {'Name': 'Chosen action', 'Prefix': str(self.root / 'prefix')}
        self.window = QMainWindow(); self.window.background_tasks = BackgroundTasks(self.window)
        self.window.game_detection = Mock(); self.window.game_detection.status.return_value = 'Stopped'
        self.window.game_status_changed = Mock()
        self.controller = Automation(self.window)
        self.addCleanup(self.window.close)

    def test_environment_and_working_directory_are_literal_and_output_is_logged(self):
        result = execute_command('printf "%s\\n" "$PLAYLITE_GAME_NAME" "$PLAYLITE_PREFIX" "$PLAYLITE_ACTION_NAME"; pwd', self.game, self.action, 2, threading.Event())
        self.assertEqual(result['state'], 'Complete')
        self.assertIn(self.game['Name'], result['details'])
        self.assertIn(str(self.root), result['details'])
        self.assertIn('Chosen action', result['details'])
        self.assertIn(str(self.root / 'prefix'), result['details'])

    def test_before_launch_waits_and_failure_prevents_continuation(self):
        self.game['Automation']['before_launch'] = 'sleep .1; echo useful-error; exit 7'
        launch = Mock(); self.controller.run(self.game, self.action, 'before_launch', completed=launch)
        self.assertEqual(self.controller.busy('one'), 'before_launch'); launch.assert_not_called()
        wait(lambda: not self.controller.tasks)
        launch.assert_not_called(); self.assertIsNone(self.controller.busy('one'))
        self.window.game_detection.launch_failed.assert_called_once_with('one')
        row = next(iter(self.window.background_tasks.records.values()))
        self.assertEqual(row['state'], 'Failed'); self.assertIn('useful-error', row['details'])

    def test_successful_preparation_runs_continuation_once(self):
        self.game['Automation']['before_launch'] = 'printf ready'
        launch = Mock(); self.controller.run(self.game, self.action, 'before_launch', completed=launch)
        wait(lambda: not self.controller.tasks); launch.assert_called_once()
        self.assertIn('ready', next(iter(self.window.background_tasks.records.values()))['details'])

    def test_companion_can_start_without_waiting_for_its_exit(self):
        start = time.monotonic()
        result = execute_command('sleep 2 &', self.game, self.action, 3, threading.Event())
        self.assertEqual(result['state'], 'Complete')
        self.assertLess(time.monotonic() - start, 1)

    def test_missing_folder_does_not_fall_back_to_an_unrelated_directory(self):
        self.game['InstallDirectory'] = str(self.root / 'missing')
        with self.assertRaisesRegex(ValueError, 'folder does not exist'):
            execute_command('touch unexpected', self.game, self.action, 1, threading.Event())
        self.assertFalse((self.root / 'unexpected').exists())

    def test_timeout_stops_command_and_cancelled_command_does_not_start(self):
        result = execute_command('sleep 10', self.game, self.action, 1, threading.Event())
        self.assertEqual(result['state'], 'Failed'); self.assertIn('timed out', result['details'])
        cancelled = threading.Event(); cancelled.set()
        result = execute_command('touch unexpected', self.game, self.action, 1, cancelled)
        self.assertEqual(result['state'], 'Cancelled'); self.assertFalse((self.root / 'unexpected').exists())

    def test_cancel_preparation_prevents_launch(self):
        self.game['Automation']['before_launch'] = 'sleep 10'
        launch = Mock(); self.controller.run(self.game, self.action, 'before_launch', completed=launch)
        row = next(iter(self.window.background_tasks.records.values()))
        self.window.background_tasks.callbacks[row['id']]['cancel']()
        wait(lambda: not self.controller.tasks); launch.assert_not_called()
        self.assertEqual(row['state'], 'Cancelled')

    def test_exit_uses_launch_snapshot_waits_for_after_launch_and_notifies_once(self):
        self.game['Automation'].update(after_launch='sleep .1; printf launch >> order', after_exit='printf exit >> order')
        self.controller.launched(self.game, self.action)
        self.game['Automation']['after_exit'] = 'printf wrong >> order'
        self.game['InstallDirectory'] = '/missing-location'
        completed = Mock(); self.controller.exited('one', completed)
        completed.assert_not_called()
        wait(lambda: completed.called and not self.controller.tasks)
        completed.assert_called_once(); self.assertEqual((self.root / 'order').read_text(), 'launchexit')
        self.assertNotIn('one', self.controller.sessions)

    def test_external_exit_skips_commands_and_cleanup_failure_still_notifies(self):
        completed = Mock(); self.controller.exited('external', completed)
        completed.assert_called_once(); self.assertFalse(self.window.background_tasks.records)
        self.game['Automation']['after_exit'] = 'exit 2'; self.controller.launched(self.game, self.action)
        completed.reset_mock(); self.controller.exited('one', completed)
        wait(lambda: not self.controller.tasks); completed.assert_called_once()

    def test_editor_save_preserves_scripts_without_executing_and_cancel_leaves_game_untouched(self):
        with patch('playlite.automation.subprocess.Popen') as launch:
            editor = MetadataEditor(self.game, self.root)
            editor.automation_commands['before_launch'].setPlainText('printf changed')
            editor.reject(); self.assertEqual(self.game['Automation']['before_launch'], '')
            result = editor.collect(); self.assertEqual(result['Automation']['before_launch'], 'printf changed')
            launch.assert_not_called(); editor.close()

    def test_invalid_timeout_and_null_commands_are_rejected(self):
        with self.assertRaises(ValueError): settings_for({'Automation': {'timeout': 0}})
        with self.assertRaises(ValueError): settings_for({'Automation': {'before_launch': '\0'}})
        with self.assertRaises(ValueError): settings_for({'Automation': {'enabled': 'false'}})
