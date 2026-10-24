import io
import json
import unittest
from unittest.mock import patch
from playlite.steam_catalogue import search_games


class SteamCatalogueTests(unittest.TestCase):
    def test_direct_ids_and_store_urls_require_no_network(self):
        with patch('playlite.steam_catalogue.urllib.request.urlopen') as request:
            self.assertEqual(search_games('42')[0]['id'],'42')
            self.assertEqual(search_games('https://store.steampowered.com/app/84/Example/')[0]['id'],'84')
        request.assert_not_called()

    def test_search_filters_bundles_invalid_ids_and_duplicates(self):
        data={'items':[{'id':42,'name':'Example &amp; More','type':'app'}, {'id':42,'name':'Duplicate','type':'app'}, {'id':84,'name':'Bundle','type':'sub'}, {'id':'bad','name':'Invalid','type':'app'}]}
        with patch('playlite.steam_catalogue.urllib.request.urlopen',return_value=io.BytesIO(json.dumps(data).encode())):
            self.assertEqual(search_games('Example'),[{'id':'42','name':'Example & More'}])

    def test_network_and_malformed_responses_have_actionable_errors(self):
        with patch('playlite.steam_catalogue.urllib.request.urlopen',side_effect=OSError('offline')):
            with self.assertRaisesRegex(ValueError,'Could not search Steam'):search_games('Example')
        for data in (b'invalid',b'[]',b'{}'):
            with patch('playlite.steam_catalogue.urllib.request.urlopen',return_value=io.BytesIO(data)):
                with self.assertRaises(ValueError):search_games('Example')
