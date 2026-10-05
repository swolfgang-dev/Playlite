import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from playlite.providers import MetadataProvider
from playlite.image_dialog import ImageDownloader


class PagedProvider(MetadataProvider):
    id = 'Paged'
    name = 'Paged artwork'
    image_types = frozenset(('Icon',))

    def image_page(self, game_id, image_type, page=0):
        return ([{'url': f'https://example.com/{page}.png', 'label': str(page)}], page == 0)

    def is_exact_query(self, query, result_id=None):
        return query.isdigit()

    def search(self, query):
        return [{'id': int(query), 'name': 'Example'}]


class ImagePagingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_load_more_appends_and_hides_after_last_page(self):
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': PagedProvider()}):
            dialog = ImageDownloader({'Name': 'Example'})
        dialog.run = lambda function, complete: (complete(function()), dialog.update_load_more())
        def download(url, path):
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        with patch('playlite.image_dialog.download_artwork', side_effect=download):
            dialog.selected_game = {'id': 1, 'name': 'Example'}
            dialog.load_images()
            self.assertEqual(dialog.images.count(), 1)
            self.assertFalse(dialog.load_more_button.isHidden())
            original = dialog.images.item(0).data(256)
            dialog.load_images(more=True)
            self.assertEqual(dialog.images.count(), 2)
            self.assertEqual(dialog.images.item(0).data(256), original)
            self.assertTrue(dialog.load_more_button.isHidden())
        dialog.finish(0)

    def test_legacy_provider_does_not_offer_more(self):
        provider = MetadataProvider()
        provider.images = lambda game, kind: [{'url': 'legacy'}]
        self.assertEqual(provider.image_page(1, 'Icon'), ([{'url': 'legacy'}], False))
        self.assertEqual(provider.image_page(1, 'Icon', 1), ([], False))

    def test_open_preloads_distinct_selected_providers_and_search_refreshes(self):
        first, second = PagedProvider(), PagedProvider()
        second.id, second.name = 'Other', 'Other artwork'
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': first, 'Other': second}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1, 'Other': 2}})
        dialog.controls['CoverImage'][0].setCurrentIndex(1)
        dialog.run = lambda function, complete: (complete(function()), dialog.update_load_more())
        def download(url, path):
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        with patch.object(first, 'search', wraps=first.search) as first_search, patch.object(second, 'search', wraps=second.search) as second_search, patch('playlite.image_dialog.download_artwork', side_effect=download) as artwork:
            dialog.preload_images()
            dialog.process_pending_searches()
            self.assertEqual(first_search.call_count, 1)
            self.assertEqual(second_search.call_count, 1)
            self.assertEqual(len(dialog.catalogues), 2)
            self.assertEqual(dialog.image_lists['CoverImage'].count(), 1)
            before = artwork.call_count
            dialog.tabs.setCurrentIndex(1)
            self.assertEqual(artwork.call_count, before)
            dialog.search()
            self.assertEqual(second_search.call_count, 2)
            self.assertEqual(artwork.call_count, before + 1)
            self.assertEqual(len(dialog.image_pixmaps), 3)
        dialog.finish(0)

    def test_new_provider_with_id_searches_when_selected(self):
        first, second = PagedProvider(), PagedProvider()
        second.id, second.name = 'Other', 'Other artwork'
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': first, 'Other': second}):
            dialog = ImageDownloader({'MetadataIds': {'Other': 2}})
        dialog.initial_search_scheduled = True
        with patch.object(dialog, 'search') as search:
            dialog.source.setCurrentIndex(1)
            search.assert_called_once_with(key='Icon', refresh=False)
        dialog.finish(0)

    def test_provider_switch_restores_other_tab_artwork_without_requests(self):
        other = PagedProvider()
        other.id, other.name = 'Other', 'Other artwork'
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': PagedProvider(), 'Other': other}):
            dialog = ImageDownloader({'Name': 'Example'})
        dialog.run = lambda function, complete: (complete(function()), dialog.update_load_more())
        def download(url, path):
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        with patch('playlite.image_dialog.download_artwork', side_effect=download):
            dialog.selected_game = {'id': 1, 'name': 'Example'}
            dialog.load_images()
        with patch.object(dialog, 'run') as request:
            dialog.tabs.setCurrentIndex(1)
            dialog.filters['CoverImage'][1].set_values(['wide'])
            dialog.source.setCurrentIndex(dialog.source.findData('Other'))
            self.assertEqual(dialog.images.count(), 0)
            dialog.source.setCurrentIndex(dialog.source.findData('Paged'))
            self.assertEqual(dialog.images.count(), 1)
            self.assertEqual(dialog.selected_game['id'], 1)
            self.assertEqual(dialog.filters['CoverImage'][1].values(), ['wide'])
            self.assertFalse(dialog.load_more_button.isHidden())
            request.assert_not_called()
        dialog.finish(0)

    def test_cached_catalogue_retains_more_state_on_tab_switch(self):
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': PagedProvider()}):
            dialog = ImageDownloader({'Name': 'Example'})
        key = ('Paged', '1')
        dialog.catalogues[key] = ([], [])
        dialog.catalogue_pages[key] = {'Icon': (1, True)}
        dialog.selected_game = {'id': 1, 'name': 'Example'}
        dialog.load_images()
        self.assertFalse(dialog.load_more_button.isHidden())
        dialog.update_source('Icon')
        self.assertTrue(dialog.load_more_button.isHidden())
        dialog.finish(0)
