import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
from PyQt6.QtCore import QSettings
from playlite.image_filters import apply_install_defaults, defaults, declared_defaults


class ImageDefaultTests(unittest.TestCase):
    def test_install_seeds_declared_defaults_and_preserves_user_choices(self):
        with TemporaryDirectory() as temporary:
            data = Path(temporary)
            manifest = {'id': 'Example', 'image_defaults': {'BackgroundImage':
                {'artwork': ['BackgroundImage'], 'shape': ['16:9'], 'resolution': [1024, 1920]}}}
            apply_install_defaults(manifest, data)
            settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
            self.assertEqual(settings.value('images/defaultProvider/BackgroundImage'), 'Example')
            with patch('playlite.providers.discover_plugins', return_value={}):
                self.assertEqual(defaults(settings, 'BackgroundImage')['resolution'], [1024, 1920])
            settings.setValue('images/defaultProvider/BackgroundImage', 'Chosen')
            settings.setValue('images/defaultFilters/BackgroundImage/resolution/selected', [256])
            settings.sync()
            apply_install_defaults(manifest, data)
            self.assertEqual(settings.value('images/defaultProvider/BackgroundImage'), 'Chosen')
            with patch('playlite.providers.discover_plugins', return_value={}):
                self.assertEqual(defaults(settings, 'BackgroundImage')['resolution'], [256])

    def test_installed_plugin_declarations_supply_unsaved_defaults(self):
        plugin = SimpleNamespace(id='Example', image_types={'Icon'}, image_defaults={
            'Icon': {'artwork': ['Icon'], 'shape': ['square'], 'resolution': [256]}})
        plugins = {'Example': plugin}
        self.assertEqual(declared_defaults('Icon', plugins)[0], 'Example')
        self.assertEqual(declared_defaults('BackgroundImage', plugins), ('', {}))
        with patch('playlite.providers.discover_plugins', return_value=plugins):
            self.assertEqual(defaults(None, 'Icon'), {'artwork': ['Icon'], 'shape': ['square'], 'resolution': [256]})
