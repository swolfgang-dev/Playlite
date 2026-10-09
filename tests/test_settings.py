from plugin_test_support import require_plugin
require_plugin('IGDB')
require_plugin('LutrisIntegration')
require_plugin('GameArchiver')
require_plugin('SteamMetadata')
require_plugin('SteamAutoCrack')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication, QLabel
from playlite.settings import SettingsDialog
from playlite.app import LibraryWindow

APP = QApplication.instance() or QApplication([])


class SettingsTests(unittest.TestCase):
    def test_general_install_folder_is_saved_and_used_by_add_game(self):
        from PyQt6.QtWidgets import QWidget,QPushButton
        from playlite.manual_installation import ManualInstallation
        with tempfile.TemporaryDirectory() as directory:
            data=Path(directory);settings=QSettings(str(data/'ui.ini'),QSettings.Format.IniFormat)
            dialog=SettingsDialog(settings)
            dialog.default_install_folder.setText('/games/default')
            dialog.save()
            self.assertEqual(settings.value('installation/defaultFolder'),'/games/default')
            editor=QWidget();editor.data=data;editor.fields={}
            widget=ManualInstallation().create_editor(editor,{})
            with patch('playlite.manual_installation.choose_directory',return_value='') as choose:
                widget.findChild(QPushButton,'browseInstallDirectory').click()
                self.assertEqual(choose.call_args.args[2],'/games/default')
            override=ManualInstallation().create_editor(editor,{},directory_defaults={'InstallDirectory':'/games/plugin'})
            with patch('playlite.manual_installation.choose_directory',return_value='') as choose:
                override.findChild(QPushButton,'browseInstallDirectory').click()
                self.assertEqual(choose.call_args.args[2],'/games/plugin')

    def test_default_installation_method_is_exclusive_saved_and_used(self):
        from playlite.add_game import AddGameEditor
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            checks = dialog.default_method_checks
            self.assertTrue(checks['Manual'].isChecked())
            checks['LutrisImport'].click()
            self.assertFalse(checks['Manual'].isChecked())
            checks['LutrisAdd'].click()
            self.assertFalse(checks['LutrisImport'].isChecked())
            self.assertEqual(sum(check.isChecked() for check in checks.values()), 1)
            dialog.save()
            self.assertEqual(settings.value('installation/defaultMethod'), 'LutrisAdd')
            editor = AddGameEditor(None, data)
            self.assertEqual(editor.installation_plugin.id, 'LutrisAdd')
            self.assertEqual(editor.installation_header_label.text(), 'Installation Method')
            editor.reject()
            editor = AddGameEditor(None, data, installation_method='Manual')
            self.assertEqual(editor.installation_plugin.id, 'Manual')
            editor.reject()
            reopened = SettingsDialog(settings)
            self.assertTrue(reopened.default_method_checks['LutrisAdd'].isChecked())
            reopened.default_method_checks['Manual'].click()
            reopened.reject()
            settings.sync()
            self.assertEqual(settings.value('installation/defaultMethod'), 'LutrisAdd')
            settings.setValue('installation/defaultMethod', 'Unavailable')
            settings.sync()
            editor = AddGameEditor(None, data)
            self.assertEqual(editor.installation_plugin.id, 'Manual')
            editor.reject()

    def test_image_filter_defaults_save_cancel_and_reset(self):
        from playlite.image_dialog import ImageDownloader
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ui.ini'
            settings = QSettings(str(path), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            filters = dialog.image_filter_defaults['CoverImage']
            for name, value in [('artwork', ['Icon', 'CoverImage']), ('shape', ['portrait', 'square']), ('resolution', [512, 1024, 1920])]:
                filters[name].set_values(value)
            dialog.reject()
            self.assertFalse(settings.contains('images/defaultFilters/CoverImage/shape'))
            dialog = SettingsDialog(settings)
            for name, value in [('artwork', ['Icon', 'CoverImage']), ('shape', ['portrait', 'square']), ('resolution', [512, 1024, 1920])]:
                selector = dialog.image_filter_defaults['CoverImage'][name]
                selector.set_values(value)
            dialog.save()
            picker = ImageDownloader({'Name': 'Example'}, settings_path=path)
            icon_defaults = [widget.values() for widget in picker.filters['Icon']]
            picker.tabs.setCurrentIndex(1)
            self.assertEqual([widget.values() for widget in picker.filters['CoverImage']],
                             [['Icon', 'CoverImage'], ['square', 'portrait'], [512, 1024, 1920]])
            picker.filters['CoverImage'][1].set_values(['wide'])
            picker.tabs.setCurrentIndex(0)
            self.assertEqual([widget.values() for widget in picker.filters['Icon']],
                             icon_defaults)
            picker.tabs.setCurrentIndex(1)
            self.assertEqual(picker.filters['CoverImage'][1].values(), ['square', 'portrait'])
            picker.reset_filters('CoverImage')
            self.assertEqual(picker.filters['CoverImage'][1].values(), ['square', 'portrait'])
            picker.reject()

    def test_legacy_filter_defaults_migrate_to_checkbox_selections(self):
        from playlite.image_filters import defaults, FilterChecks
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            for name, value in [('artwork', 'all'), ('shape', 'landscape'), ('resolution', 512)]:
                settings.setValue('images/defaultFilters/Icon/' + name, value)
            saved = defaults(settings, 'Icon')
            self.assertEqual(saved['artwork'], ['Icon', 'Logo', 'CoverImage', 'HeaderImage', 'BackgroundImage'])
            self.assertEqual(saved['shape'], ['landscape', 'wide'])
            self.assertEqual(saved['resolution'], [512, 1024, 1920])
            checks = FilterChecks('shape', saved['shape'])
            checks.boxes['square'].click()
            self.assertEqual(checks.values(), ['square', 'landscape', 'wide'])
            checks.all.click()
            self.assertEqual(len(checks.values()), 7)
            checks.all.click()
            self.assertEqual(checks.values(), [])
            settings.setValue('images/defaultFilters/Icon/shape/selected', [])
            self.assertEqual(defaults(settings, 'Icon')['shape'], [])

    def test_background_blur_save_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            self.assertEqual(dialog.background_blur.value(), 20)
            dialog.background_blur.setValue(72)
            self.assertEqual(dialog.background_blur_value.text(), '7.2')
            dialog.reject()
            self.assertFalse(settings.contains('appearance/backgroundBlur'))
            dialog = SettingsDialog(settings)
            dialog.background_blur.setValue(0)
            dialog.panel_transparency['sidePanelTransparency'].setValue(60)
            dialog.panel_transparency['gamePanelTransparency'].setValue(35)
            dialog.save()
            reopened = SettingsDialog(settings)
            self.assertEqual(reopened.background_blur.value(), 0)
            self.assertEqual(reopened.panel_transparency['sidePanelTransparency'].value(), 60)
            self.assertEqual(reopened.panel_transparency['gamePanelTransparency'].value(), 35)
            reopened.reject()

    def test_panel_transparency_changes_surfaces_without_fading_artwork(self):
        from playlite.app import card
        from PyQt6.QtWidgets import QLabel
        with tempfile.TemporaryDirectory() as directory:
            window = LibraryWindow(Path(directory))
            panel, layout = card()
            window.details.addWidget(panel)
            artwork = QLabel('Cover', window.content)
            artwork.setObjectName('cover')
            window.settings.setValue('appearance/sidePanelTransparency', 100)
            window.settings.setValue('appearance/gamePanelTransparency', 50)
            window.apply_panel_appearance()
            self.assertTrue(window.game_background.isAncestorOf(window.list))
            self.assertTrue(window.game_background.isAncestorOf(window.game_scroll))
            self.assertIn('rgba(20, 21, 22, 0)', window.list.styleSheet())
            self.assertIn('rgba(29, 30, 32, 204)', panel.styleSheet())
            window.settings.setValue('appearance/readablePanels', False)
            window.apply_panel_appearance()
            self.assertIn('rgba(29, 30, 32, 128)', panel.styleSheet())
            self.assertIsNone(artwork.graphicsEffect())
            self.assertEqual(artwork.styleSheet(), '')
            window.close()

    def test_steam_api_key_save_validation_and_cancel(self):
        from playlite.providers import discover_plugins
        plugin = discover_plugins(include_disabled=True)['SteamAutoCrack']
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / 'steam.ini'
            settings = QSettings(str(filename), QSettings.Format.IniFormat)
            with patch.object(type(plugin), 'settings', return_value=settings):
                widget = plugin.create_settings()
                widget.api_key.setText('invalid')
                with self.assertRaises(ValueError):
                    plugin.save_settings(widget)
                self.assertFalse(settings.contains('apiKey'))
                key = 'a' * 32
                widget.api_key.setText(key)
                plugin.save_settings(widget)
                self.assertEqual(filename.stat().st_mode & 0o777, 0o600)
                reopened = plugin.create_settings()
                self.assertEqual(reopened.api_key.text(), key)
                reopened.api_key.clear()
                self.assertEqual(settings.value('apiKey'), key)
                plugin.save_settings(reopened)
                self.assertEqual(settings.value('apiKey'), '')

    def test_image_provider_defaults_save_cancel_and_initialize_downloader(self):
        import copy
        from playlite.providers import discover_providers
        from playlite.image_dialog import ImageDownloader
        steam = discover_providers()['SteamMetadata']
        other = copy.copy(steam)
        other.id, other.name = 'Other', 'Other artwork'
        other.image_types = {'Icon'}
        plugins = {'SteamMetadata': steam, 'Other': other}
        with tempfile.TemporaryDirectory() as directory, \
             patch('playlite.providers.discover_plugins', return_value=plugins), \
             patch('playlite.image_dialog.discover_providers', return_value=plugins):
            path = Path(directory) / 'ui.ini'
            settings = QSettings(str(path), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            self.assertEqual(dialog.image_sources['CoverImage'].count(), 2)
            dialog.image_sources['Icon'].setCurrentIndex(1)
            dialog.reject()
            self.assertFalse(settings.contains('images/defaultProvider/Icon'))
            dialog = SettingsDialog(settings)
            dialog.image_sources['Icon'].setCurrentIndex(1)
            dialog.save()
            reopened = SettingsDialog(settings)
            self.assertEqual(reopened.image_sources['Icon'].currentData(), 'Other')
            self.assertEqual(reopened.image_sources['CoverImage'].currentData(), 'SteamMetadata')
            # A provider offering icons can also supply artwork for a cover.
            settings.setValue('images/defaultProvider/CoverImage', 'Other')
            settings.sync()
            picker = ImageDownloader({'Name': 'Example'}, settings_path=path)
            self.assertEqual(picker.controls['Icon'][0].currentData(), 'Other')
            self.assertEqual(picker.controls['CoverImage'][0].currentData(), 'Other')
            picker.reject()
            reopened.reject()

    def test_preferences_save_and_cancel(self):
        with tempfile.TemporaryDirectory() as directory, patch('playlite_plugins.igdb.client.load_credentials', return_value=('', '')):
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            dialog.close_to_tray.setChecked(False)
            dialog.default_view.setCurrentIndex(dialog.default_view.findData('compact'))
            dialog.reset_on_launch.setChecked(True)
            dialog.save()
            reopened = SettingsDialog(settings)
            self.assertFalse(reopened.close_to_tray.isChecked())
            self.assertFalse(hasattr(reopened, 'metadata_source'))
            self.assertEqual(reopened.default_view.currentData(), 'compact')
            self.assertTrue(reopened.reset_on_launch.isChecked())
            self.assertEqual(reopened.tabs.tabText(1), 'Appearance')
            self.assertEqual(reopened.tabs.tabText(2), 'Plugins')
            self.assertEqual([reopened.plugin_tabs.tabText(i) for i in range(reopened.plugin_tabs.count())], ['Installed', 'Available', 'General', 'Metadata', 'Installation'])
            self.assertTrue(any(target.id == 'LutrisAdd' and reopened.plugin_tabs.widget(4).isAncestorOf(widget) for owner, target, widget in reopened.plugin_contributions))
            self.assertTrue({'LutrisIntegration', 'IGDB', 'GameArchiver', 'SteamAutoCrack'}.issubset(reopened.plugin_widgets))
            installed = {reopened.installed_plugins.item(row, 4).text():
                         reopened.installed_plugins.item(row, 3).text()
                         for row in range(reopened.installed_plugins.rowCount())}
            from playlite.plugin_manager import installed_plugins
            studio = next(plugin for plugin in installed_plugins() if plugin['id'] == 'ImageStudio')
            self.assertEqual(installed['ImageStudio'], 'Enabled' if studio.get('enabled', True) else 'Disabled')
            self.assertEqual(installed['SteamAutoCrack'], 'Enabled')
            self.assertFalse(any(label.text() == 'No configurable settings.' for label in reopened.findChildren(QLabel)))
            reopened.close_to_tray.setChecked(True)
            reopened.reject()
            self.assertFalse(settings.value('app/closeToTray', type=bool))

    def test_startup_view_and_reset_sorting_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
            settings.setValue('library/view', 'list')
            settings.setValue('library/filters', '{"Genres": "RPG"}')
            settings.setValue('library/sort', 'Playtime')
            settings.setValue('library/descending', True)
            settings.setValue('app/defaultView', 'grid')
            settings.setValue('app/resetSortingFilters', True)
            settings.sync()
            window = LibraryWindow(data)
            self.assertTrue(window.is_grid)
            self.assertEqual(window.sort.currentData(), 'Name')
            self.assertFalse(window.order.isChecked())
            self.assertFalse(window.filter_controls['Genres'].values())
            window.close()

    def test_page_scrollbar_handle_only_appears_with_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            window = LibraryWindow(Path(directory))
            bar = window.game_scroll.verticalScrollBar()
            bar.setRange(0, 0)
            self.assertFalse(bar.isEnabled())
            self.assertIn('background: transparent', bar.styleSheet())
            bar.setRange(0, 100)
            self.assertTrue(bar.isEnabled())
            self.assertEqual(bar.styleSheet(), '')
            bar.setRange(0, 0)
            self.assertFalse(bar.isEnabled())
            self.assertIn('background: transparent', bar.styleSheet())
            window.close()

    def test_window_size_is_not_saved(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            window = LibraryWindow(data)
            default_size = window.size()
            window.settings.setValue('window/normalSizeStable', window.size())
            window.resize(720, 620)
            window.save_window_state()
            reopened = LibraryWindow(data)
            self.assertEqual(reopened.size(), default_size)
            self.assertFalse(reopened.settings.contains('window/normalSizeStable'))
            self.assertTrue(reopened.fit_default_height)
            window.close()
            reopened.close()

    def test_plugin_contributions_have_independent_installation_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            plugin_settings = QSettings(str(Path(directory) / 'steam.ini'), QSettings.Format.IniFormat)
            plugins_method = __import__('playlite.providers', fromlist=['discover_plugins']).discover_plugins
            plugins = plugins_method(include_disabled=True)
            with patch.object(type(plugins['SteamAutoCrack']), 'settings', return_value=plugin_settings), patch('playlite.providers.discover_plugins', return_value=plugins):
                dialog = SettingsDialog(settings)
                contributions = {target.id: widget for owner, target, widget in dialog.plugin_contributions if owner.id == 'SteamAutoCrack'}
                self.assertTrue({'Manual', 'LutrisImport', 'LutrisAdd'} <= set(contributions))
                contributions['Manual'].setChecked(False)
                contributions['LutrisImport'].setChecked(True)
                dialog.save()
                self.assertFalse(plugins['SteamAutoCrack'].default_for('Manual'))
                self.assertTrue(plugins['SteamAutoCrack'].default_for('LutrisImport'))
                from playlite.add_game import AddGameEditor
                editor = AddGameEditor(None, Path(directory))
                self.assertFalse(editor.autocrack.isChecked())
                editor.reject()
                editor = AddGameEditor(None, Path(directory), installation_method='LutrisImport')
                self.assertTrue(editor.autocrack.isChecked())
                editor.reject()
