import os
import unittest
from unittest.mock import patch
from tempfile import TemporaryDirectory
from playlite import plugin_manager as manager

class GitHubAccessTests(unittest.TestCase):
    def test_credentials_are_isolated_from_shell_and_global_cli(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {
            'XDG_DATA_HOME': directory, 'GH_TOKEN': 'secret', 'GITHUB_TOKEN': 'secret',
            'GH_CONFIG_DIR': '/global/config', 'GH_ENTERPRISE_TOKEN': 'secret',
            'GITHUB_ENTERPRISE_TOKEN': 'secret'}):
            env = manager.github_environment()
            self.assertEqual(env['GH_CONFIG_DIR'], directory + '/playlite/github')
            for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN'):
                self.assertNotIn(key, env)

    def test_release_build_never_reads_credentials(self):
        with patch.object(manager, 'development_checkout', return_value=False), patch.object(manager.subprocess, 'run') as run:
            self.assertEqual(manager.github_token(), '')
            with self.assertRaises(ValueError):
                manager.authenticate_github('secret')
            run.assert_not_called()

    def test_unavailable_private_repositories_are_not_listed(self):
        from urllib.error import HTTPError
        with patch.object(manager, 'plugin_catalogue', return_value=[('Example', 'owner/example')]), patch.object(manager, 'github_request', side_effect=HTTPError('url', 404, 'Not Found', {}, None)):
            self.assertEqual(manager.available_plugins(), [])

    def test_visible_repository_requires_a_release(self):
        with patch.object(manager, 'plugin_catalogue', return_value=[('Example', 'owner/example')]), patch.object(manager, 'github_request', side_effect=[
            {'description': 'Example plugin', 'private': True}, {'tag_name': 'v1.0.0'}]):
            self.assertEqual(manager.available_plugins()[0]['repository'], 'owner/example')

    def test_browser_command_is_limited_to_repository_build(self):
        with patch.object(manager, 'development_checkout', return_value=False):
            with self.assertRaises(ValueError):
                manager.github_browser_command()
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}), patch.object(manager, 'development_checkout', return_value=True), patch.object(manager.shutil, 'which', return_value='/usr/bin/gh'):
            command = manager.github_browser_command()
            self.assertIn('--web', command)
            self.assertIn('--insecure-storage', command)

    def test_browser_dialog_displays_code_and_finishes_without_ui_blocking(self):
        import sys
        from pathlib import Path
        from PyQt6.QtCore import QSettings, QEventLoop, QTimer
        from PyQt6.QtWidgets import QApplication, QPushButton, QLabel, QDialog
        from playlite.settings import SettingsDialog
        app = QApplication.instance() or QApplication([])
        command = [sys.executable, '-u', '-c', "print('! First copy your one-time code: ABCD-1234', flush=True); input()"]
        observed = []
        def run(dialog):
            loop = QEventLoop()
            dialog.finished.connect(loop.quit)
            for button in dialog.findChildren(QPushButton):
                if button.text() == 'Sign in with GitHub in browser':
                    button.click()
                    break
            QTimer.singleShot(5000, loop.quit)
            loop.exec()
            observed.extend(label.text() for label in dialog.findChildren(QLabel))
            self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}), patch.object(manager, 'github_browser_command', return_value=command), patch('playlite.settings.run_dialog', side_effect=run), patch('playlite.settings.QDesktopServices.openUrl', return_value=True) as open_url:
            window = SettingsDialog(QSettings(str(Path(directory)/'test.ini'), QSettings.Format.IniFormat))
            with patch.object(window, 'refresh_available_plugins') as refresh:
                window.authenticate_plugin_github()
                refresh.assert_called_once()
            self.assertTrue(any('ABCD-1234' in text for text in observed))
            open_url.assert_called_once()
            self.assertEqual(open_url.call_args.args[0].toString(), 'https://github.com/login/device')
            window.reject()

    def test_cancelling_browser_login_stops_process(self):
        import sys
        from pathlib import Path
        from PyQt6.QtCore import QSettings, QProcess
        from PyQt6.QtWidgets import QApplication, QPushButton
        from playlite.settings import SettingsDialog
        app = QApplication.instance() or QApplication([])
        command = [sys.executable, '-u', '-c', 'import time; time.sleep(60)']
        def run(dialog):
            for button in dialog.findChildren(QPushButton):
                if button.text() == 'Sign in with GitHub in browser':
                    button.click()
                    break
            process = dialog.findChild(QProcess)
            self.assertTrue(process.waitForStarted(1000))
            dialog.reject()
            self.assertEqual(process.state(), QProcess.ProcessState.NotRunning)
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}), patch.object(manager, 'github_browser_command', return_value=command), patch('playlite.settings.run_dialog', side_effect=run):
            window = SettingsDialog(QSettings(str(Path(directory)/'test.ini'), QSettings.Format.IniFormat))
            with patch.object(window, 'refresh_available_plugins') as refresh:
                window.authenticate_plugin_github()
                refresh.assert_not_called()
            window.reject()
