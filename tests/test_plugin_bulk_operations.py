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
    def test_available_hides_installed_plugins_by_current_repositories_and_ids(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            root = Path(directory)
            for identity, repository in (
                    ('LutrisIntegration', 'swolfgang-dev/playlite-plugin-lutris-integration'),
                    ('SteamDepotDownloader', 'swolfgang-dev/playlite-plugin-steam-depot-downloader'),
                    ('ImageStudio', 'swolfgang-dev/playlite-plugin-image-studio')):
                folder = root / 'playlite/plugins' / identity.lower()
                folder.mkdir(parents=True)
                (folder / 'manifest.json').write_text(json.dumps(dict(
                    id=identity, name=identity, version='1', repository=repository, enabled=False)))
            cache = catalogue_cache()
            old = cache.plugins, cache.loaded, cache.loading, cache.error
            cache.complete([
                dict(name='Lutris Integration', version='1', description='',
                     repository='SWOLFGANG-DEV/playlite-plugin-lutris-integration'),
                dict(name='Steam Depot Downloader', version='1', description='',
                     repository='swolfgang-dev/playlite-plugin-steam-depot-downloader'),
                dict(id='ImageStudio', name='Image Studio', version='1', description='',
                     repository='owner/image-studio'),
                dict(name='Other', version='1', description='', repository='owner/other')])
            window = SettingsDialog(QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat))
            try:
                self.assertEqual(window.installed_plugins.rowCount(), 3)
                self.assertEqual(window.available_plugins.rowCount(), 1)
                self.assertEqual(window.available_plugins.item(0, 0).text(), 'Other')
            finally:
                window.reject()
                cache.plugins, cache.loaded, cache.loading, cache.error = old

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
                with patch('PyQt6.QtCore.QThreadPool.globalInstance', return_value=Mock()), patch('playlite.lifecycle.run_dialog', return_value=1):
                    window.delete_plugin_button.click()
                    window.batch_delete_task.run()
                self.assertEqual(window.installed_plugins.rowCount(),0)
                for row in range(2):
                    window.available_plugins.selectionModel().select(window.available_plugins.model().index(row,0),QItemSelectionModel.SelectionFlag.Select|QItemSelectionModel.SelectionFlag.Rows)
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

    def test_installed_button_updates_selected_plugins_directly(self):
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            root = Path(directory)
            for identity in ('First', 'Second'):
                plugin = root / 'playlite/plugins' / identity.lower()
                plugin.mkdir(parents=True)
                manifest = dict(id=identity, name=identity, version='1', type='generic',
                                enabled=False, repository='owner/' + identity.lower() + '-source')
                if identity == 'First':
                    manifest['distribution_repository'] = 'owner/first-releases'
                (plugin / 'manifest.json').write_text(json.dumps(manifest))
            cache = catalogue_cache()
            old = (cache.plugins, cache.loaded, cache.loading, cache.error)
            cache.complete([dict(name='Second', version='2', description='', repository='owner/second-releases')])
            window = SettingsDialog(QSettings(str(root / 'ui.ini'), QSettings.Format.IniFormat))
            try:
                window.installed_plugins.selectAll()
                with patch('playlite.settings.run_dialog') as dialog, \
                        patch('PyQt6.QtCore.QThreadPool.globalInstance', return_value=Mock()), \
                        patch('playlite.plugin_manager.install_github', side_effect=[
                            ValueError('denied'), {'name': 'Second', 'version': '2'}]) as install:
                    window.update_selected_button.click()
                    self.assertFalse(window.update_selected_button.isEnabled())
                    self.assertFalse(window.delete_plugin_button.isEnabled())
                    window.batch_install_task.run()
                    self.assertEqual([call.args[0] for call in install.call_args_list],
                                     ['owner/first-releases', 'owner/second-releases'])
                    dialog.assert_not_called()
                    log = window.plugin_operation_status.toPlainText()
                    self.assertIn('denied', log)
                    self.assertIn('Installed Second 2', log)
                    self.assertIn('Restart Playlite', log)
                window.installed_plugins.clearSelection()
                self.assertFalse(window.update_selected_button.isEnabled())
            finally:
                window.reject()
                cache.plugins, cache.loaded, cache.loading, cache.error = old

    def test_context_menu_toggles_mixed_selection_and_preserves_it(self):
        from PyQt6.QtWidgets import QMenu
        from playlite.plugin_manager import installed_plugins
        with TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_DATA_HOME': directory}):
            root = Path(directory)
            for identity, enabled in [('First', True), ('Second', False), ('Third', True)]:
                folder = root / 'playlite/plugins' / identity.lower()
                folder.mkdir(parents=True)
                (folder / 'manifest.json').write_text(json.dumps(dict(id=identity, name=identity, version='1', enabled=enabled)))
            with patch('playlite.providers.discover_plugins', return_value={}):
                window = SettingsDialog(QSettings(str(root / 'settings.ini'), QSettings.Format.IniFormat))
            table = window.installed_plugins
            table.setFixedSize(700, 300)
            for row in (0, 1):
                table.selectionModel().select(table.model().index(row, 0), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            try:
                with patch.object(QMenu, 'popup'):
                    window.installed_plugin_context_menu(table.visualItemRect(table.item(0, 0)).center())
                menu = table.findChildren(QMenu)[-1]
                self.assertEqual([action.text() for action in menu.actions()], ['Enable selected', 'Disable selected'])
                menu.actions()[1].trigger()
                state = {plugin['id']: plugin['enabled'] for plugin in installed_plugins()}
                self.assertEqual(state, {'First': False, 'Second': False, 'Third': True})
                self.assertEqual(len(table.selectionModel().selectedRows()), 2)
                window.set_selected_plugins_enabled(['First', 'Second'], True)
                self.assertTrue(all(plugin['enabled'] for plugin in installed_plugins()))
                self.assertIn('Restart Playlite', window.plugin_operation_status.toPlainText())
                with patch.object(QMenu, 'popup'):
                    window.installed_plugin_context_menu(table.visualItemRect(table.item(2, 0)).center())
                menu = table.findChildren(QMenu)[-1]
                self.assertEqual([action.text() for action in menu.actions()], ['Disable'])
                self.assertEqual([index.row() for index in table.selectionModel().selectedRows()], [2])
            finally:
                window.reject()

    def test_plugin_removal_settings_choice_is_scoped(self):
        with TemporaryDirectory() as folder:
            root = Path(folder)
            plugins = root / 'plugins'
            target = plugins / 'lutris'
            target.mkdir(parents=True)
            manifest = dict(id='LutrisIntegration', name='Lutris', version='1', settings_groups=['Lutris'])
            (target / 'manifest.json').write_text(json.dumps(manifest))
            settings = QSettings(str(root / 'preferences.ini'), QSettings.Format.IniFormat)
            settings.setValue('LibraryDirectory', '/external/lutris')
            with patch('PyQt6.QtCore.QSettings', return_value=settings):
                delete_plugin('LutrisIntegration', plugins)
                self.assertEqual(settings.value('LibraryDirectory'), '/external/lutris')
                target.mkdir()
                (target / 'manifest.json').write_text(json.dumps(manifest))
                delete_plugin('LutrisIntegration', plugins, keep_settings=False)
                self.assertFalse(settings.contains('LibraryDirectory'))
