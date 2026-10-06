import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from playlite import updater


class UpdateRestartTests(unittest.TestCase):
    def test_update_bypasses_tray_but_respects_close_veto(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from PyQt6.QtWidgets import QApplication, QDialog, QMainWindow
        from playlite.lifecycle import TrayLifecycle
        from playlite.settings import SettingsDialog
        app = QApplication.instance() or QApplication([])

        class Window(QMainWindow):
            allow_close = True
            def closeEvent(self, event):
                event.setAccepted(self.allow_close)

        for allow_close in (True, False):
            with self.subTest(allow_close=allow_close), tempfile.TemporaryDirectory() as root:
                window = Window()
                window.allow_close = allow_close
                window.lifecycle = TrayLifecycle(window, app)
                window.lifecycle.quit = Mock()
                window.show()
                directory = Path(root) / 'staged'
                directory.mkdir()
                dialog = SimpleNamespace(
                    application_release={'tag_name': 'v1'},
                    update_status=Mock(), check_update_button=Mock(),
                    parentWidget=lambda: window, save=lambda: None,
                    result=lambda: QDialog.DialogCode.Accepted,
                    update_task=lambda function, complete: complete(function()))
                with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE': ''}), \
                        patch.object(updater, 'prepare_update', return_value=directory), \
                        patch.object(updater, 'launch_update') as launch, \
                        patch('playlite.lifecycle.QSystemTrayIcon.isSystemTrayAvailable', return_value=True):
                    SettingsDialog.install_application_update(dialog)
                self.assertFalse(window.lifecycle.quitting)
                if allow_close:
                    launch.assert_called_once_with(directory, 'v1')
                    window.lifecycle.quit.assert_called_once()
                    self.assertFalse(window.isVisible())
                else:
                    launch.assert_not_called()
                    window.lifecycle.quit.assert_not_called()
                    self.assertTrue(window.isVisible())
                    self.assertFalse(directory.exists())
                window.lifecycle.quitting = True
                window.allow_close = True
                window.close()
                window.deleteLater()

class UpdaterTests(unittest.TestCase):
    def test_rate_limit_falls_back_to_public_release_and_checksums(self):
        from urllib.error import HTTPError
        from unittest.mock import Mock
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.geturl.return_value='https://github.com/swolfgang-dev/Playlite/releases/tag/v0.2.53'
        limited=HTTPError('api',403,'rate limit',{},None)
        with patch.object(updater,'fetch',side_effect=[limited,b'hash  install.sh\nhash  playlite-0.2.53-py3-none-any.whl\n']),patch.object(updater.urllib.request,'urlopen',return_value=response):
            release=updater.latest_release()
        self.assertEqual(release['tag_name'],'v0.2.53')
        assets={item['name']:item['browser_download_url'] for item in release['assets']}
        self.assertEqual(assets['install.sh'],'https://github.com/swolfgang-dev/Playlite/releases/download/v0.2.53/install.sh')
        self.assertIn('SHA256SUMS',assets)

    def test_other_release_errors_are_not_hidden(self):
        from urllib.error import HTTPError
        with patch.object(updater,'fetch',side_effect=HTTPError('api',404,'missing',{},None)):
            with self.assertRaises(HTTPError):updater.latest_release()

    def test_repo_cannot_install_updates(self):
        with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE':'repo'}):
            with self.assertRaises(ValueError): updater.prepare_update({})

    def test_verified_installer_is_staged_with_standalone_helper(self):
        import shutil
        script = b'#!/bin/bash\nexit 0\n'
        release = {'assets':[{'name':'SHA256SUMS','browser_download_url':'hashes'}, {'name':'install.sh','browser_download_url':'script'}]}
        with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE':''}), patch.object(updater,'fetch',side_effect=[(hashlib.sha256(script).hexdigest()+'  install.sh\n').encode(),script]):
            directory = updater.prepare_update(release)
        try:
            self.assertEqual((directory/'install.sh').read_bytes(),script)
            self.assertTrue((directory/'updater.py').is_file())
        finally: shutil.rmtree(directory)

    def test_bad_checksum_prevents_staging(self):
        release = {'assets':[{'name':'SHA256SUMS','browser_download_url':'hashes'}, {'name':'install.sh','browser_download_url':'script'}]}
        with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE':''}), patch.object(updater,'fetch',side_effect=[b'wrong  install.sh\n',b'installer']):
            with self.assertRaisesRegex(ValueError,'checksum'):updater.prepare_update(release)

    def test_failed_install_does_not_restart_and_cleans_staging(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)/'staged';directory.mkdir()
            with patch.object(updater,'__file__',str(directory/'updater.py')), patch.object(updater.subprocess,'run',return_value=SimpleNamespace(returncode=1)), patch.object(updater.subprocess,'Popen') as launch:
                with self.assertRaises(RuntimeError):updater.run_update(999999999,'v1')
                launch.assert_not_called()
            self.assertFalse(directory.exists())
