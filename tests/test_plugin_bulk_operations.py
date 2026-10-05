import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch
from PyQt6.QtCore import QSettings, QItemSelectionModel
from PyQt6.QtWidgets import QApplication, QAbstractItemView
from playlite.plugin_manager import delete_plugin, install_plugins
from playlite.settings import SettingsDialog
from playlite.plugin_catalogue_cache import catalogue_cache

APP = QApplication.instance() or QApplication([])

class BulkPluginTests(unittest.TestCase):
    def test_install_continues_after_individual_failure(self):
        with patch('playlite.plugin_manager.install_github', side_effect=[ValueError('denied'), {'name':'Second','version':'1'}]) as install:
            messages = []
            results = install_plugins(['owner/first','owner/second','owner/first'], messages.append)
            self.assertEqual(messages, ['Installing owner/first…', 'owner/first: denied', 'Installing owner/second…', 'Installed Second 1'])
            self.assertEqual(install.call_count, 2)
            self.assertEqual(results[0][2], 'denied')
            self.assertEqual(results[1][1]['name'], 'Second')

    def test_delete_removes_only_plugin_and_rejects_external_symlink(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            plugins=root/'plugins'; plugins.mkdir()
            plugin=plugins/'example'; plugin.mkdir()
            (plugin/'manifest.json').write_text(json.dumps({'id':'Example'}))
            (root/'library.json').write_text('[]')
            delete_plugin('Example', plugins)
            self.assertFalse(plugin.exists())
            self.assertTrue((root/'library.json').exists())
            external=root/'external';external.mkdir()
            (external/'manifest.json').write_text(json.dumps({'id':'External'}))
            (plugins/'external').symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError): delete_plugin('External', plugins)
            self.assertTrue(external.exists())

    def test_tables_support_bulk_delete_and_install(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME':directory}):
            root=Path(directory)
            for identity in ('First','Second'):
                path=root/'playlite/plugins'/identity.lower(); path.mkdir(parents=True)
                (path/'manifest.json').write_text(json.dumps(dict(id=identity,name=identity,version='1',type='generic',enabled=False)))
            cache=catalogue_cache()
            old=(cache.plugins,cache.loaded,cache.loading,cache.error)
            cache.complete([dict(name=identity,version='1',description='',repository='owner/'+identity.lower()) for identity in ('First','Second')])
            window=SettingsDialog(QSettings(str(root/'settings.ini'),QSettings.Format.IniFormat))
            try:
                for table in (window.installed_plugins,window.available_plugins):
                    self.assertEqual(table.selectionMode(),QAbstractItemView.SelectionMode.ExtendedSelection)
                    for row in range(2):
                        table.selectionModel().select(table.model().index(row,0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
                    self.assertEqual(len(table.selectionModel().selectedRows()),2)
                with patch('PyQt6.QtCore.QThreadPool.globalInstance', return_value=Mock()):
                    window.delete_plugin_button.click()
                    window.batch_delete_task.run()
                self.assertEqual(window.installed_plugins.rowCount(),0)
                pool=Mock()
                def install_batch(repositories, progress):
                    progress('Installed First 1')
                    self.assertIn('Installed First',window.available_operation_log.toPlainText())
                    progress('owner/second: denied')
                    return [('owner/first',{'name':'First','version':'1'},''),('owner/second',None,'denied')]
                with patch('PyQt6.QtCore.QThreadPool.globalInstance',return_value=pool),patch('playlite.plugin_manager.install_plugins',side_effect=install_batch) as install:
                    window.install_selected_button.click()
                    self.assertFalse(window.install_selected_button.isEnabled())
                    window.batch_install_task.run()
                    self.assertEqual(install.call_args.args[0], ['owner/first','owner/second'])
                    self.assertIn('Installed First',window.available_operation_log.toPlainText())
                    self.assertIn('denied',window.available_operation_log.toPlainText())
            finally:
                window.reject()
                cache.plugins,cache.loaded,cache.loading,cache.error=old

    def test_installed_button_opens_a_populated_working_download_dialog(self):
        from PyQt6.QtWidgets import QComboBox, QPushButton
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME':directory}):
            root=Path(directory)
            plugin=root/'playlite/plugins/example';plugin.mkdir(parents=True)
            (plugin/'manifest.json').write_text(json.dumps(dict(id='Example',name='Example',version='1',type='generic',enabled=False,repository='owner/private-source')))
            cache=catalogue_cache()
            old=(cache.plugins,cache.loaded,cache.loading,cache.error)
            cache.complete([dict(name='Example',version='v1',description='',repository='owner/example-releases')])
            def run(dialog):
                combo=dialog.findChild(QComboBox)
                self.assertEqual(combo.currentText(),'owner/example-releases')
                button=next(button for button in dialog.findChildren(QPushButton) if button.text()=='Install / update')
                self.assertTrue(button.isEnabled())
                button.click()
                dialog.install_task.run()
                dialog.reject()
            try:
                window=SettingsDialog(QSettings(str(root/'ui.ini'),QSettings.Format.IniFormat))
                with patch('playlite.settings.run_dialog',side_effect=run) as opened, patch('PyQt6.QtCore.QThreadPool.globalInstance',return_value=Mock()), patch('playlite.plugin_manager.install_github',return_value={'name':'Example','version':'1'}) as install:
                    button=next(button for button in window.findChildren(QPushButton) if button.text()=='Install / update from GitHub…')
                    button.click()
                    opened.assert_called_once()
                    install.assert_called_once_with('owner/example-releases')
                window.reject()
            finally:
                cache.plugins,cache.loaded,cache.loading,cache.error=old
