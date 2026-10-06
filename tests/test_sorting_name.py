from plugin_test_support import require_plugin
require_plugin('IGDB')
require_plugin('SteamMetadata')
import unittest
from playlite.sorting_name import sorting_name
from playlite_plugins.steammetadata.metadata import normalize
from playlite_plugins.igdb.client import normalize as normalize_igdb


class SortingNameTests(unittest.TestCase):
    def test_playnite_conversion_rules(self):
        cases = {
            'The Witcher 3': 'Witcher 03',
            'A Plague Tale: Innocence': 'Plague Tale: Innocence',
            'Final Fantasy VII Remastered': 'Final Fantasy 07 Remastered',
            'Portal Two': 'Portal 02',
            'Chapter One: Arrival': 'Chapter 01: Arrival',
            'Army of Two: The 40th Day': 'Army of Two: The 40th Day',
            'X-COM': 'X-COM',
            'Mega Man X-Treme': 'Mega Man X-Treme',
            'S.T.A.L.K.E.R.': 'S.T.A.L.K.E.R.',
            'Game IIX': 'Game IIX',
            'Game Ⅳ': 'Game 04',
        }
        for title, expected in cases.items():
            with self.subTest(title=title):
                self.assertEqual(sorting_name(title), expected)

    def test_both_metadata_sources_provide_sorting_name(self):
        self.assertEqual(normalize(1, {'name': 'The Witcher 3'})['fields']['SortingName'], 'Witcher 03')
        self.assertEqual(normalize_igdb({'id': 1, 'name': 'The Witcher 3'})['fields']['SortingName'], 'Witcher 03')
