import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap
from playlite.providers import MetadataProvider
from playlite.image_dialog import ImageDownloader


class PagedProvider(MetadataProvider):
    id = 'Paged'
    name = 'Paged artwork'
    image_types = frozenset(('Icon', 'CoverImage'))

    def image_page(self, game_id, image_type, page=0):
        return ([{'url': f'https://example.com/{self.id}/{page}.png', 'label': str(page)}], page == 0)

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

    def test_download_keeps_controls_usable_and_queues_search(self):
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': PagedProvider()}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1}})
        with patch('playlite.image_dialog.QThreadPool') as pool:
            dialog.run(lambda: None, lambda result: None)
            self.assertTrue(dialog.busy)
            self.assertTrue(dialog.tabs.isEnabled())
            self.assertTrue(dialog.source.isEnabled())
            self.assertTrue(dialog.query.isEnabled())
            dialog.tabs.setCurrentIndex(1)
            dialog.search()
            self.assertIn(('CoverImage', ('Paged', '1'), True), dialog.pending_searches)
            pool.globalInstance.return_value.start.assert_called_once()
        dialog.busy = False
        dialog.finish(0)

    def test_preload_prioritizes_selected_tab(self):
        provider = PagedProvider()
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': provider}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1}})
        dialog.tabs.setCurrentIndex(1)
        dialog.run = lambda function, complete: complete(function())
        def download(url, path):
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        def page(game_id, image_type, page=0):
            return ([{'url': f'https://example.com/{image_type}.png'}], False)
        with patch.object(provider, 'image_page', side_effect=page), patch('playlite.image_dialog.download_artwork', side_effect=download) as artwork:
            dialog.preload_images()
            self.assertIn('CoverImage', artwork.call_args_list[0].args[0])
        dialog.finish(0)

    def test_images_are_revealed_before_batch_finishes(self):
        provider = PagedProvider()
        provider.image_types = frozenset(('Icon',))
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': provider}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1}})
        dialog.run = lambda function, complete: complete(function())
        counts = []
        def download(url, path):
            counts.append(dialog.images.count())
            self.assertIn('downloading image', dialog.download_status.text())
            pixmap = QPixmap(16, 16)
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        candidates = [{'url': 'https://example.com/one.png'}, {'url': 'https://example.com/two.png'}]
        with patch.object(provider, 'image_page', return_value=(candidates, False)), patch('playlite.image_dialog.download_artwork', side_effect=download):
            dialog.search()
        self.assertEqual(counts, [0, 1])
        self.assertEqual(dialog.images.count(), 2)
        self.assertIn('2 of 2 images shown', dialog.status.text())
        dialog.finish(0)

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
            self.assertEqual(artwork.call_count, before)
            self.assertEqual(len(dialog.image_pixmaps), 2)
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

    def test_opening_tab_waits_for_all_tab_filters_before_preloading(self):
        provider = PagedProvider()
        provider.image_types = frozenset(('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage'))
        sizes = {'Icon': (256, 256), 'CoverImage': (600, 900),
                 'HeaderImage': (1920, 620), 'BackgroundImage': (1920, 1080)}
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': provider}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1}})
        with patch.object(dialog, 'search') as search:
            dialog.tabs.setCurrentIndex(1)
            search.assert_not_called()
        for key, shape in zip(dialog.image_keys, ('square', '2:3', '96:31', '16:9')):
            artwork, shapes, resolution = dialog.filters[key]
            artwork.set_values([key])
            shapes.set_values([shape])
            resolution.set_values([0, 256, 512, 1024, 1920])
        dialog.run = lambda function, complete: (complete(function()), dialog.update_load_more())
        def page(game_id, image_type, page=0):
            width, height = sizes[image_type]
            return ([{'url': f'https://example.com/{image_type}.png',
                      'width': width, 'height': height}], False)
        def download(url, path):
            image_type = url.rsplit('/', 1)[1].split('.')[0]
            pixmap = QPixmap(*sizes[image_type])
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        with patch.object(provider, 'image_page', side_effect=page), patch('playlite.image_dialog.download_artwork', side_effect=download) as artwork:
            dialog.preload_images()
            self.assertEqual(artwork.call_count, 4)
            for key in dialog.image_keys:
                visible = [dialog.image_lists[key].item(i) for i in range(dialog.image_lists[key].count())
                           if not dialog.image_lists[key].item(i).isHidden()]
                self.assertEqual(len(visible), 1, key)
        dialog.finish(0)

    def test_search_downloads_only_new_filter_matches(self):
        provider = PagedProvider()
        provider.image_types = frozenset(('CoverImage',))
        candidates = [{'url': 'https://example.com/portrait.png', 'width': 600, 'height': 900},
                      {'url': 'https://example.com/wide.png', 'width': 1920, 'height': 620},
                      {'url': 'https://example.com/small.png', 'width': 300, 'height': 450}]
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': provider}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1}})
        dialog.tabs.blockSignals(True)
        dialog.tabs.setCurrentIndex(1)
        dialog.tabs.blockSignals(False)
        dialog.run = lambda function, complete: (complete(function()), dialog.update_load_more())
        shape, resolution = dialog.filters['CoverImage'][1:]
        for key in dialog.image_keys:
            if key != 'CoverImage':
                dialog.filters[key][0].set_values([key])
        shape.set_values(['2:3'])
        resolution.set_values([512])
        def download(url, path):
            size = (1920, 620) if 'wide' in url else (600, 900)
            pixmap = QPixmap(*size)
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        with patch.object(provider, 'image_page', return_value=(candidates, False)), patch('playlite.image_dialog.download_artwork', side_effect=download) as artwork:
            dialog.search()
            self.assertEqual(artwork.call_count, 1)
            self.assertIn('portrait', artwork.call_args.args[0])
            shape.set_values(['wide'])
            resolution.set_values([1920])
            dialog.search()
            self.assertEqual(artwork.call_count, 2)
            self.assertIn('wide', artwork.call_args.args[0])
            self.assertEqual(dialog.images.count(), 2)
            dialog.search()
            self.assertEqual(artwork.call_count, 2)
        dialog.finish(0)

    def test_search_uses_filters_from_other_tabs(self):
        provider = PagedProvider()
        provider.image_types = frozenset(('Icon', 'CoverImage'))
        with patch('playlite.image_dialog.discover_providers', return_value={'Paged': provider}):
            dialog = ImageDownloader({'MetadataIds': {'Paged': 1}})
        dialog.run = lambda function, complete: complete(function())
        for key in dialog.image_keys:
            dialog.filters[key][0].set_values([key])
        dialog.filters['Icon'][1].set_values(['square'])
        dialog.filters['CoverImage'][1].set_values(['2:3'])
        def page(game_id, image_type, page=0):
            width, height = (256, 256) if image_type == 'Icon' else (600, 900)
            return ([{'url': f'https://example.com/{image_type}.png',
                      'width': width, 'height': height}], False)
        def download(url, path):
            pixmap = QPixmap(*( (256, 256) if 'Icon' in url else (600, 900)))
            pixmap.fill()
            pixmap.save(str(path), 'PNG')
            return str(path)
        with patch.object(provider, 'image_page', side_effect=page), patch('playlite.image_dialog.download_artwork', side_effect=download) as artwork:
            dialog.search()
            self.assertEqual(artwork.call_count, 2)
            self.assertEqual(dialog.image_lists['CoverImage'].count(), 2)
            dialog.search()
            self.assertEqual(artwork.call_count, 2)
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
