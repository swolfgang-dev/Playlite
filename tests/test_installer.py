import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock,patch
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import QApplication
from playlite.installer import InstallerDialog
from playlite.plugin_lifecycle import installed_setup,prepare_removal

APP=QApplication.instance() or QApplication([])


class InstallerTests(unittest.TestCase):
    def test_finish_saves_preferences_and_completion_only_to_selected_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = QSettings(str(Path(directory) / 'repo.ini'), QSettings.Format.IniFormat)
            release = QSettings(str(Path(directory) / 'release.ini'), QSettings.Format.IniFormat)
            dialog = InstallerDialog(settings=repo)
            self.assertFalse(repo.value('onboarding/completed', False, type=bool))
            dialog.default_view.setCurrentIndex(dialog.default_view.findData('grid'))
            dialog.close_to_tray.setChecked(False)
            dialog.reset_filters.setChecked(True)
            dialog.finish_setup()
            self.assertTrue(repo.value('onboarding/completed', False, type=bool))
            self.assertEqual(repo.value('app/defaultView'), 'grid')
            self.assertFalse(repo.value('app/closeToTray', type=bool))
            self.assertTrue(repo.value('app/resetSortingFilters', type=bool))
            self.assertFalse(release.contains('onboarding/completed'))

    def test_dismissal_leaves_setup_pending_and_preferences_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            settings.setValue('app/defaultView', 'list')
            dialog = InstallerDialog(settings=settings)
            self.assertEqual(dialog.default_view.currentData(), 'list')
            dialog.reject()
            self.assertFalse(settings.contains('onboarding/completed'))
            self.assertEqual(settings.value('app/defaultView'), 'list')

    def dialog(self):
        with patch('playlite.installer.QTimer.singleShot'):
            return InstallerDialog()

    def test_selected_plugins_only_and_post_install_setup(self):
        dialog=self.dialog()
        pool=Mock();pool.start.side_effect=lambda task:task.run()
        entries=[{'name':'Steam Downloader','repository':'owner/steam'}, {'name':'Other','repository':'owner/other'}]
        with patch('playlite.installer.QThreadPool.globalInstance',return_value=pool),patch('playlite.installer.available_plugins',return_value=entries),patch('playlite.installer.installed_plugins',return_value=[]):
            dialog.load_catalogue()
        dialog.plugins.item(0).setCheckState(Qt.CheckState.Checked)
        result=[('owner/steam',{'id':'SteamDepotDownloader','name':'Steam Downloader'},'')]
        with patch('playlite.installer.QThreadPool.globalInstance',return_value=pool),patch('playlite.installer.install_plugins',return_value=result) as install,patch('playlite.installer.installed_setup') as setup:
            dialog.install_selected()
            self.assertEqual(install.call_args.args[0],['owner/steam'])
            self.assertEqual(setup.call_args.args[0],[result[0][1]])
        self.assertFalse(dialog.busy)
        dialog.accept()

    def test_busy_installer_cannot_be_closed(self):
        dialog=self.dialog();dialog.show();dialog.busy=True
        dialog.reject();self.assertTrue(dialog.isVisible())
        dialog.busy=False;dialog.reject()

    def test_optional_setup_hook_and_cancelled_removal(self):
        plugin=Mock()
        with patch('playlite.plugin_lifecycle.load_plugin',return_value=plugin):
            installed_setup([{'id':'SteamDepotDownloader'}],None,Mock())
            plugin.post_install.assert_called_once_with(None)
            plugin.prepare_uninstall.return_value=False
            self.assertFalse(prepare_removal(['SteamDepotDownloader'],None,Mock()))
