import io
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from PIL import Image
from playlite.metadata import MetadataError, download_artwork


class ArtworkHostTests(unittest.TestCase):
    def test_steamgriddb_cdns_download_readable_artwork(self):
        buffer = io.BytesIO()
        Image.new('RGB', (16, 16)).save(buffer, format='PNG')
        with TemporaryDirectory() as root:
            for host in ('cdn.steamgriddb.com', 'cdn2.steamgriddb.com'):
                with self.subTest(host=host), patch('playlite.metadata.request', return_value=buffer.getvalue()) as request:
                    result = download_artwork(f'https://{host}/grid/example.png', Path(root) / 'image.png')
                    self.assertTrue(Path(result).is_file())
                    request.assert_called_once()

    def test_untrusted_hosts_and_http_are_rejected_before_request(self):
        with patch('playlite.metadata.request') as request:
            for url in ('http://cdn2.steamgriddb.com/image.png',
                        'https://cdn2.steamgriddb.com.example.com/image.png',
                        'https://other.steamgriddb.com/image.png'):
                with self.subTest(url=url), self.assertRaises(MetadataError):
                    download_artwork(url, '/tmp/unused-artwork.png')
            request.assert_not_called()
