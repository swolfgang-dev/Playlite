import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from playlite.providers import discover_plugins


class PluginModuleTests(unittest.TestCase):
    identity = 'ReviewFixture'

    def tearDown(self):
        for name in list(sys.modules):
            if name == 'playlite_plugins.reviewfixture' or name.startswith('playlite_plugins.reviewfixture.'):
                del sys.modules[name]

    def fixture(self, root, value):
        directory = root / 'example';directory.mkdir(parents=True)
        (directory / 'manifest.json').write_text(json.dumps(dict(id=self.identity, name='Example',
            version='1', api_version=1, type='generic')))
        (directory / 'helper.py').write_text(f'VALUE = {value!r}\n')
        (directory / 'plugin.py').write_text('from playlite.providers import GenericPlugin\n'
            'from .helper import VALUE\nclass Plugin(GenericPlugin):\n    value = VALUE\n')
        return directory

    def test_repeated_discovery_does_not_reexecute_package_code(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);self.fixture(root, 'first')
            first=discover_plugins(root)[self.identity]
            second=discover_plugins(root)[self.identity]
            self.assertIs(type(first), type(second))

    def test_switching_profile_roots_does_not_reuse_another_roots_helpers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            self.fixture(root/'one', 'one');self.fixture(root/'two', 'two')
            first=discover_plugins(root/'one')[self.identity]
            second=discover_plugins(root/'two')[self.identity]
            self.assertEqual(first.value, 'one');self.assertEqual(second.value, 'two')

    def test_failed_import_does_not_leave_a_half_loaded_package(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);directory=self.fixture(root, 'first')
            with (directory/'plugin.py').open('a') as stream:stream.write('raise ValueError("failed import")\n')
            with self.assertLogs(level='ERROR'):
                self.assertNotIn(self.identity, discover_plugins(root))
            self.assertFalse(any(name.startswith('playlite_plugins.reviewfixture') for name in sys.modules))

    def test_lifecycle_receives_validated_manifest_metadata(self):
        from playlite.plugin_lifecycle import load_plugin
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.fixture(root, 'setup')
            entry = dict(id=self.identity, installation_hooks=True,
                         manifest_path=str(directory / 'manifest.json'))
            with patch('playlite.plugin_lifecycle.installed_plugins', return_value=[entry]), \
                 patch('playlite.plugin_lifecycle.plugin_directory', return_value=root):
                plugin = load_plugin(self.identity)
            self.assertEqual(plugin.id, self.identity)
            self.assertEqual(plugin.name, 'Example')
            self.assertEqual(plugin.manifest_path, directory / 'manifest.json')
            for name in list(sys.modules):
                if name.startswith('playlite_install_hooks.plugin_'):
                    del sys.modules[name]

    def test_failed_lifecycle_factory_removes_partial_namespace(self):
        from playlite.plugin_lifecycle import load_plugin
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            directory = self.fixture(root, 'setup')
            (directory / 'plugin.py').write_text('class Plugin: pass\n')
            entry = dict(id=self.identity, installation_hooks=True,
                         manifest_path=str(directory / 'manifest.json'))
            before = set(sys.modules)
            with patch('playlite.plugin_lifecycle.installed_plugins', return_value=[entry]), \
                 patch('playlite.plugin_lifecycle.plugin_directory', return_value=root):
                with self.assertRaisesRegex(ValueError, 'must inherit GenericPlugin'):
                    load_plugin(self.identity)
            self.assertFalse(any(name.startswith('playlite_install_hooks.plugin_')
                                 for name in set(sys.modules) - before))
