import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile
from PyQt6.QtCore import QSettings
from playlite.plugin_manager import install_archive, installed_plugins
from playlite.ownership import record_tree


class PluginFolderTests(unittest.TestCase):
    def test_install_uses_current_id_and_folder_preserving_disabled_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugins = root / 'plugins'
            old = plugins / 'playlite-plugin-image-studio'
            old.mkdir(parents=True)
            (old / 'manifest.json').write_text(json.dumps({'id': 'ImageStudio', 'enabled': False}))
            record_tree(old)
            archive = root / 'plugin.zip'
            with ZipFile(archive, 'w') as bundle:
                bundle.writestr('manifest.json', json.dumps({'id': 'ImageStudio', 'name': 'Image Studio',
                                   'version': '2.2.1', 'api_version': 1, 'type': 'generic'}))
                bundle.writestr('plugin.py', 'pass')
            manifest = install_archive(archive, plugins)
            self.assertFalse(manifest['enabled'])
            self.assertTrue(old.exists())
            self.assertTrue((plugins / 'playlite-plugin-image-studio/manifest.json').exists())
            self.assertEqual(len(installed_plugins(plugins)), 1)

    def test_failed_folder_move_restores_previous_installation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plugins = root / 'plugins'
            old = plugins / 'playlite-plugin-image-studio'
            old.mkdir(parents=True)
            (old / 'manifest.json').write_text(json.dumps({'id': 'ImageStudio', 'enabled': True}))
            record_tree(old)
            archive = root / 'plugin.zip'
            with ZipFile(archive, 'w') as bundle:
                bundle.writestr('manifest.json', json.dumps({'id': 'ImageStudio', 'name': 'Image Studio',
                                   'version': '2.2.1', 'api_version': 1, 'type': 'generic'}))
                bundle.writestr('plugin.py', 'pass')
            rename = Path.rename
            def fail_stage(path, destination):
                if path.name == 'plugin':
                    raise OSError('cannot publish stage')
                return rename(path, destination)
            with patch.object(Path, 'rename', fail_stage), self.assertRaises(OSError):
                install_archive(archive, plugins)
            self.assertTrue((old / 'manifest.json').exists())
            self.assertEqual(installed_plugins(plugins)[0]['id'], 'ImageStudio')

    def test_reinstall_recovers_cache_only_folder_but_protects_user_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);plugins=root/'plugins'
            destination=plugins/'playlite-plugin-example';destination.mkdir(parents=True)
            cache=destination/'__pycache__';cache.mkdir();(cache/'plugin.cpython-314.pyc').write_bytes(b'cache')
            archive=root/'plugin.zip'
            with ZipFile(archive,'w') as bundle:
                bundle.writestr('manifest.json',json.dumps(dict(id='Example',name='Example',version='1.0',api_version=1,type='generic',repository='owner/playlite-plugin-example')))
                bundle.writestr('plugin.py','pass')
            note=destination/'notes.txt';note.write_text('keep')
            with self.assertRaisesRegex(ValueError,'already occupied'):install_archive(archive,plugins)
            self.assertEqual(note.read_text(),'keep');note.unlink()
            install_archive(archive,plugins)
            self.assertEqual(installed_plugins(plugins)[0]['id'],'Example')
            self.assertTrue((destination/'plugin.py').exists())
