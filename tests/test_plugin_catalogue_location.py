import base64
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from playlite.plugin_manager import plugin_catalogue


class CatalogueLocationTests(unittest.TestCase):
    def test_catalogue_downloads_from_core_and_points_to_source_repositories(self):
        catalogue = json.loads((Path(__file__).resolve().parents[1] / 'catalogue.json').read_text())
        document = {'content': base64.b64encode(json.dumps(catalogue).encode()).decode()}
        with patch('playlite.plugin_manager.github_request', return_value=document) as request:
            entries = plugin_catalogue()
        request.assert_called_once_with('repos/swolfgang-dev/Playlite/contents/catalogue.json')
        self.assertEqual(len(entries), 7)
        self.assertEqual(len({repository for _, repository in entries}), 7)
        self.assertTrue(all(not repository.endswith('-releases') for _, repository in entries))
