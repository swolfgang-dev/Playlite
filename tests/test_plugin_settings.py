import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from playlite.plugin_settings import clear_plugin_settings


class PluginSettingsResetTests(unittest.TestCase):
    def test_invalid_later_file_does_not_remove_earlier_file_or_group(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory)
            (config / 'playlite').mkdir()
            credentials = config / 'playlite/provider.json'
            credentials.write_text('credentials')
            with patch.dict(os.environ, XDG_CONFIG_HOME=directory), patch('PyQt6.QtCore.QSettings') as settings:
                with self.assertRaises(ValueError):
                    clear_plugin_settings({'settings_groups': ['Provider'],
                                           'settings_files': ['playlite/provider.json', '../elsewhere.json']})
                settings.assert_not_called()
            self.assertEqual(credentials.read_text(), 'credentials')

    def test_malformed_declarations_are_rejected_before_reset(self):
        for declaration in ({'settings_groups': 'Provider'}, {'settings_files': [None]},
                            {'settings_groups': ['Provider', 'bad/group']}):
            with self.subTest(declaration=declaration), patch('PyQt6.QtCore.QSettings') as settings:
                with self.assertRaises(ValueError):
                    clear_plugin_settings(declaration)
                settings.assert_not_called()

    def test_symlinked_parent_cannot_remove_external_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / 'config'; config.mkdir()
            external = root / 'external'; external.mkdir()
            (config / 'playlite').symlink_to(external, target_is_directory=True)
            path = external / 'provider.json'; path.write_text('keep')
            with patch.dict(os.environ, XDG_CONFIG_HOME=str(config)):
                with self.assertRaises(ValueError):
                    clear_plugin_settings({'settings_files': ['playlite/provider.json']})
            self.assertEqual(path.read_text(), 'keep')
