import json
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest.mock import patch
from playlite.dev_plugins import sync_plugins, prepare_dependencies


class DevelopmentPluginTests(unittest.TestCase):
    def test_sync_includes_new_runtime_files_but_excludes_ignored_private_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            checkout=root/'source/playlite-plugin-example';checkout.mkdir(parents=True)
            subprocess.run(['git','init','-q',str(checkout)],check=True)
            (checkout/'manifest.json').write_text(json.dumps({'id':'Example'}))
            (checkout/'.gitignore').write_text('private.json\n')
            subprocess.run(['git','-C',str(checkout),'add','manifest.json','.gitignore'],check=True)
            (checkout/'vm_backend.py').write_text('new runtime')
            assets=checkout/'tools/vm';assets.mkdir(parents=True)
            (assets/'rpc.py').write_text('new guest client')
            (assets/'README.md').write_text('bundled installer documentation')
            (checkout/'private.json').write_text('private data')
            target=root/'plugins'/checkout.name;target.mkdir(parents=True)
            (target/'manifest.json').write_text(json.dumps({'id':'Example','enabled':False}))
            sync_plugins(root/'source',root/'plugins')
            self.assertEqual((target/'vm_backend.py').read_text(),'new runtime')
            self.assertEqual((target/'tools/vm/rpc.py').read_text(),'new guest client')
            self.assertTrue((target/'tools/vm/README.md').is_file())
            self.assertFalse((target/'private.json').exists())
            self.assertFalse(json.loads((target/'manifest.json').read_text())['enabled'])

    def test_prepare_installs_missing_and_outdated_requirements_once(self):
        from importlib.metadata import PackageNotFoundError
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            for name,manifest in [('one',dict(requirements=['vdf>=3.4','PyYAML>=6'])),
                                  ('two',dict(requirements=['vdf>=3.4'])),
                                  ('disabled',dict(enabled=False,requirements=['unused']))]:
                folder=root/name;folder.mkdir();(folder/'manifest.json').write_text(json.dumps(manifest))
            def version(name):
                if name=='PyQt6':return '6.6.1'
                if name=='Pillow':return '12.0.0'
                if name=='vdf':raise PackageNotFoundError(name)
                return '5.4'
            with patch('importlib.metadata.version',side_effect=version),patch('sys.prefix','/private-venv'),patch('importlib.util.find_spec',return_value=object()),patch('playlite.dev_plugins.subprocess.run') as run:
                prepare_dependencies(root)
                self.assertEqual(run.call_args.args[0][-2:],['PyYAML>=6','vdf>=3.4'])
                run.assert_called_once()

    def test_prepare_skips_satisfied_requirements(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/'plugin';folder.mkdir()
            (folder/'manifest.json').write_text(json.dumps(dict(requirements=['vdf>=3.4'])))
            with patch('importlib.metadata.version',side_effect=lambda name: {'PyQt6':'6.6.1','Pillow':'12.0.0','vdf':'3.4'}[name]),patch('playlite.dev_plugins.subprocess.run') as run:
                prepare_dependencies(root);run.assert_not_called()

    def test_sync_updates_installed_code_preserving_enabled_and_settings(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);source=root/'source';destination=root/'plugins'
            checkout=source/'playlite-plugin-example';checkout.mkdir(parents=True)
            (checkout/'.git').mkdir()
            (checkout/'manifest.json').write_text(json.dumps({'id':'Example','version':'2'}))
            (checkout/'plugin.py').write_text('new code')
            target=destination/checkout.name;target.mkdir(parents=True)
            (target/'manifest.json').write_text(json.dumps({'id':'Example','enabled':False,'version':'1'}))
            (target/'settings.json').write_text('retained')
            with patch('playlite.dev_plugins.subprocess.check_output',return_value=b'manifest.json\0plugin.py\0'):
                sync_plugins(source,destination)
                self.assertEqual((target/'plugin.py').read_text(),'new code')
                (checkout/'plugin.py').write_text('changed again')
                sync_plugins(source,destination)
            self.assertEqual((target/'plugin.py').read_text(),'changed again')
            self.assertFalse(json.loads((target/'manifest.json').read_text())['enabled'])
            self.assertEqual((target/'settings.json').read_text(),'retained')
