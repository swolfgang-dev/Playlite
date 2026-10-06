import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import re
import unittest
import json
from unittest.mock import patch
from pathlib import Path
from tempfile import TemporaryDirectory
from PyQt6.QtCore import QSettings
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QApplication, QLabel
from playlite import theme
from playlite.settings import SettingsDialog

APP = QApplication.instance() or QApplication([])


class ThemeTests(unittest.TestCase):
    def test_saved_colours_update_styles_paint_and_svg_without_losing_alpha(self):
        with TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            label = QLabel()
            theme.set_style(label, 'color: #e9e9e9; background: rgba(29, 30, 32, 128);')
            settings.setValue('appearance/colours/e9e9e9', '#abcdef')
            settings.setValue('appearance/colours/1d1e20', '#123456')
            theme.apply(settings)
            self.assertEqual(theme.colour('#e9e9e9'), '#abcdef')
            self.assertIn('color: #abcdef', label.styleSheet())
            self.assertIn('rgba(18, 52, 86, 128)', label.styleSheet())
            asset = Path(theme.themed_asset(Path(__file__).parents[1] / 'playlite/assets/chevron-down.svg'))
            self.assertIn('#abcdef', asset.read_text())
            settings.setValue('appearance/colours/e9e9e9', '#654321')
            theme.apply(settings)
            self.assertIn('color: #654321', label.styleSheet())
            settings.clear()
            theme.apply(settings)
            label.close()

    def test_colour_picker_save_cancel_and_reset(self):
        with TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            self.assertEqual(set(dialog.colour_buttons), set(theme.ROLES))
            dialog.set_colour_button(dialog.colour_buttons['text'], '#123456')
            dialog.reject()
            self.assertFalse(settings.contains('appearance/colours/e9e9e9'))
            dialog = SettingsDialog(settings)
            dialog.set_colour_button(dialog.colour_buttons['text'], '#123456')
            dialog.save()
            reopened = SettingsDialog(settings)
            self.assertEqual(reopened.colour_buttons['text'].property('selected_colour'), '#123456')
            reset = next(button for button in reopened.findChildren(type(reopened.colour_buttons['text']))
                         if button.text() == 'Reset colours to defaults')
            reset.click()
            reopened.save()
            self.assertEqual(theme.colour('#e9e9e9'), '#e9e9e9')

    def test_role_aliases_and_legacy_custom_colour_migration(self):
        with TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            settings.setValue('appearance/colours/879bb7', '#123456')
            settings.setValue('appearance/colours/343638', '#654321')
            dialog = SettingsDialog(settings)
            self.assertEqual(dialog.colour_buttons['accent'].property('selected_colour'), '#123456')
            dialog.save()
            self.assertEqual(settings.value('appearance/palette/accent'), '#123456')
            self.assertFalse(settings.contains('appearance/colours/879bb7'))
            self.assertEqual(theme.colour('#2196f3'), theme.colour('#879bb7'))
            self.assertEqual(theme.colour('#292a2c'), theme.colour('#343638'))
            self.assertEqual(theme.colour('#2c2d2f'), theme.colour('#363638'))
            settings.clear()
            theme.apply(settings)

    def test_theme_plugin_discovery_selection_and_user_override(self):
        from playlite.providers import discover_plugins, ThemePlugin
        with TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / 'example-theme'
            folder.mkdir()
            (folder / 'manifest.json').write_text(json.dumps({
                'id': 'ExampleTheme', 'name': 'Example theme', 'version': '1.0.0',
                'api_version': 1, 'type': 'theme'}))
            (folder / 'plugin.py').write_text(
                "from playlite.providers import ThemePlugin\n"
                "class Plugin(ThemePlugin):\n"
                "    def palette(self):\n"
                "        return {'accent': '#abcdef', 'window': '#123456', 'text': 'invalid'}\n")
            plugins = discover_plugins(root)
            self.assertIsInstance(plugins['ExampleTheme'], ThemePlugin)
            settings = QSettings(str(root / 'ui.ini'), QSettings.Format.IniFormat)
            with patch('playlite.providers.discover_plugins', return_value=plugins):
                dialog = SettingsDialog(settings)
                dialog.theme_source.setCurrentIndex(dialog.theme_source.findData('ExampleTheme'))
                self.assertEqual(dialog.colour_buttons['accent'].property('selected_colour'), '#abcdef')
                dialog.set_colour_button(dialog.colour_buttons['text'], '#fedcba')
                dialog.save()
                self.assertEqual(theme.colour('accent'), '#abcdef')
                self.assertEqual(theme.colour('text'), '#fedcba')
                self.assertEqual(theme.base_palette(settings)['text'], '#e9e9e9')
                self.assertEqual(theme.colour('panel'), theme.ROLES['panel'][1])
                reopened = SettingsDialog(settings)
                self.assertEqual(reopened.theme_source.currentData(), 'ExampleTheme')
                reopened.reject()
                settings.clear()
                theme.apply(settings)

    def test_colour_catalog_covers_source_and_ui_assets(self):
        root = Path(__file__).parents[1] / 'playlite'
        used = set()
        for path in [*root.rglob('*.py'), *root.joinpath('assets').glob('*.svg')]:
            used.update(value.lower() for value in re.findall(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b', path.read_text()))
        self.assertTrue(used <= set(theme.COLOURS), used - set(theme.COLOURS))

    def test_native_palette_tracks_enabled_disabled_and_accent_colours(self):
        from PyQt6.QtGui import QPalette
        with TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            theme.apply(settings)
            self.assertEqual(APP.palette().color(QPalette.ColorRole.ButtonText), QColor(theme.colour('text')))
            self.assertEqual(APP.palette().color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText), QColor(theme.colour('disabled_text')))
            self.assertEqual(APP.palette().color(QPalette.ColorRole.Highlight), QColor(theme.colour('accent')))

    def test_standard_dialog_symbols_use_app_colours_in_both_states(self):
        from PyQt6.QtWidgets import QStyle
        from PyQt6.QtGui import QIcon
        from playlite.native_style import ApplicationStyle
        style = ApplicationStyle()
        self.assertTrue(style.styleHint(QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons))
        with TemporaryDirectory() as directory:
            theme.load(QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat))
            for symbol in (QStyle.StandardPixmap.SP_DialogSaveButton, QStyle.StandardPixmap.SP_DialogCancelButton):
                icon = style.standardIcon(symbol)
                for mode, role in ((QIcon.Mode.Normal, 'text'), (QIcon.Mode.Disabled, 'disabled_text')):
                    image = icon.pixmap(24, 24, mode).toImage()
                    pixels = [image.pixelColor(x, y) for x in range(image.width()) for y in range(image.height())]
                    opaque = max(pixels, key=lambda pixel: pixel.alpha())
                    self.assertGreater(opaque.alpha(), 200)
                    self.assertEqual(opaque.name(), QColor(theme.colour(role)).name())
