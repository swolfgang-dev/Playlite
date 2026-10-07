import unittest
from unittest.mock import Mock,patch
from PyQt6.QtWidgets import QApplication,QWidget,QMessageBox,QDialog
from playlite.settings import SettingsDialog
from playlite.lifecycle import restart_application


class RestartTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_cancel_leaves_settings_and_application_open(self):
        parent=QWidget();dialog=QDialog(parent);dialog.save=Mock()
        with patch('playlite.settings.run_dialog',return_value=QMessageBox.StandardButton.Cancel),patch('playlite.lifecycle.restart_application') as restart:
            SettingsDialog.prompt_plugin_restart(dialog)
            restart.assert_not_called();dialog.save.assert_not_called()

    def test_restart_saves_settings_before_restarting(self):
        parent=QWidget();dialog=QDialog(parent);dialog.save=Mock(side_effect=dialog.accept)
        with patch('playlite.settings.run_dialog',return_value=QMessageBox.StandardButton.Ok),patch('playlite.lifecycle.restart_application') as restart:
            SettingsDialog.prompt_plugin_restart(dialog)
            dialog.save.assert_called_once();restart.assert_called_once_with(parent)

    def test_cancelled_download_shutdown_does_not_relaunch(self):
        window=Mock();window.close.return_value=False
        with patch('subprocess.Popen') as launch:
            self.assertFalse(restart_application(window));launch.assert_not_called()
        self.assertFalse(window.lifecycle.quitting)

    def test_restart_waits_for_process_exit_and_quits_through_lifecycle(self):
        window=Mock();window.close.return_value=True
        with patch('subprocess.Popen') as launch:
            self.assertTrue(restart_application(window))
            self.assertIn('os.kill(pid,0)',launch.call_args.args[0][2])
            window.lifecycle.quit.assert_called_once()
