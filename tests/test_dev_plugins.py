import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from playlite.dev_plugins import sync_plugins


class DevelopmentPluginTests(unittest.TestCase):
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
