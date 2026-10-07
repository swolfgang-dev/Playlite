import io
import json
from zipfile import ZipFile
import hashlib
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from playlite import plugin_manager as manager

class PublicDownloadTests(unittest.TestCase):
    def test_public_assets_do_not_use_api_and_keep_checksum_verification(self):
        stream=io.BytesIO()
        with ZipFile(stream,'w') as bundle:bundle.writestr('manifest.json',json.dumps(dict(id='Example',name='Example',version='1')))
        archive=stream.getvalue()
        hashes = (hashlib.sha256(archive).hexdigest()+'  plugin.zip\n').encode()
        response = MagicMock()
        response.__enter__.return_value.read.side_effect=[archive,hashes]
        with patch.object(manager,'github_token',return_value=''), patch.object(manager,'github_request') as api, patch('urllib.request.urlopen',return_value=response) as download, patch.object(manager,'install_archive',return_value={'id':'Example'}):
            self.assertEqual(manager.install_github('owner/example'),{'id':'Example'})
            api.assert_not_called()
            self.assertIn('/releases/latest/download/plugin.zip',download.call_args_list[0].args[0].full_url)

    def test_bad_public_checksum_blocks_installation(self):
        response=MagicMock();response.__enter__.return_value.read.side_effect=[b'archive',b'wrong  plugin.zip\n']
        with patch.object(manager,'github_token',return_value=''), patch('urllib.request.urlopen',return_value=response), patch.object(manager,'install_archive') as install:
            with self.assertRaisesRegex(ValueError,'checksum'):manager.install_github('owner/example')
            install.assert_not_called()

    def test_rate_limited_list_falls_back_to_public_release(self):
        response=MagicMock();response.__enter__.return_value.geturl.return_value='https://github.com/owner/example/releases/tag/v1'
        with patch.object(manager,'plugin_catalogue',return_value=[('Example','owner/example')]), patch.object(manager,'github_request',side_effect=HTTPError('url',403,'rate limit',{},None)), patch('urllib.request.urlopen',return_value=response):
            self.assertEqual(manager.available_plugins()[0]['version'],'v1')
