from .theme import colour
"""Choose provider artwork without changing the library until the editor saves."""
from pathlib import Path
from tempfile import TemporaryDirectory
from math import gcd

from PyQt6.QtCore import Qt, QThreadPool, QSize, QSettings, QTimer
from PyQt6.QtGui import QPixmap, QColor, QPen
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                            QComboBox, QListWidget, QListWidgetItem, QLabel, QDialogButtonBox, QTabWidget,
                            QStyledItemDelegate, QStyle, QWidget)
from .image_filters import OPTIONS, defaults, FilterChecks, matches_resolution, matches_shape
from .metadata import download_artwork
from .metadata_dialog import Task
from .providers import discover_providers
from .lifecycle import run_dialog


class ArtworkDelegate(QStyledItemDelegate):
    """Draw actual pixmaps so styles cannot stretch icon thumbnails."""
    def paint(self, painter, option, index):
        painter.save()
        tile = option.rect.adjusted(5, 5, -5, -5)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(colour('#343638')))
            painter.drawRoundedRect(tile, 8, 8)
        pixmap = index.data(Qt.ItemDataRole.DecorationRole)
        if isinstance(pixmap, QPixmap) and not pixmap.isNull():
            area = tile.adjusted(10, 10, -10, -38)
            scaled = pixmap.scaled(area.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            painter.drawPixmap(area.x() + (area.width() - scaled.width()) // 2,
                               area.y() + (area.height() - scaled.height()) // 2, scaled)
        painter.setPen(option.palette.text().color())
        painter.drawText(tile.adjusted(6, tile.height() - 32, -6, -6),
                         Qt.AlignmentFlag.AlignCenter, str(index.data() or ''))
        if index.data(Qt.ItemDataRole.UserRole + 1):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(colour('#2196f3')), 5))
            painter.drawRoundedRect(tile.adjusted(3, 3, -3, -3), 8, 8)
        painter.restore()


class GameSearchResults(QDialog):
    def __init__(self, results, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Select game')
        self.resize(650, 500)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose the game to search for images.'))
        self.games = QListWidget()
        for result in results:
            item = QListWidgetItem(f"{result['name']} ({result['id']})")
            item.setData(Qt.ItemDataRole.UserRole, result)
            self.games.addItem(item)
        layout.addWidget(self.games)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText('Select')
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.games.itemDoubleClicked.connect(lambda *_: self.accept())
        layout.addWidget(buttons)
        self.games.setCurrentRow(0)

    @property
    def selected_game(self):
        item = self.games.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None


class ImageDownloader(QDialog):
    def __init__(self, game, parent=None, settings_path=None):
        super().__init__(parent)
        self.setWindowTitle('Download images')
        available = self.screen().availableGeometry()
        self.resize(min(1200, available.width() - 40), min(850, available.height() - 60))
        self.cache = TemporaryDirectory(prefix='playlite-images-')
        self.applied = {}
        self.closed = False
        self.initial_search_scheduled = False
        self.busy = False
        self.serial = 0
        self.selected_games = {}
        self.loaded_searches = {}
        self.catalogues = {}
        self.catalogue_games = {}
        self.pending_searches = []
        self.automatic_searches = set()
        self.image_pixmaps = {}
        self.downloaded_urls = {}
        self.catalogue_pages = {}
        self.catalogue_urls = {}
        self.filters = {}
        self.providers = {key: plugin for key, plugin in discover_providers().items()
                          if plugin.image_types}
        settings = QSettings(str(settings_path), QSettings.Format.IniFormat) if settings_path else None
        layout = QVBoxLayout(self)
        self.provider_queries = {key: provider.query(game) for key, provider in self.providers.items()}
        self.controls = {}
        self.tabs = QTabWidget()
        self.image_keys = ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage')
        self.filter_defaults = {key: defaults(settings, key) for key in self.image_keys}
        self.image_lists = {}
        for key, label in zip(self.image_keys, ('Icon', 'Cover', 'Header', 'Background')):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            row = QHBoxLayout()
            source = QComboBox()
            for provider_id, provider in self.providers.items():
                source.addItem(provider.name, provider_id)
            preferred = settings.value(f'images/defaultProvider/{key}', 'Steam') if settings else 'Steam'
            source.setCurrentIndex(max(0, source.findData(preferred)))
            query = QLineEdit()
            search = QPushButton('Search')
            for widget in (source, query, search):
                row.addWidget(widget)
            page_layout.addLayout(row)
            game_label = QLabel('Search for a game to load images.')
            page_layout.addWidget(game_label)
            self.controls[key] = (source, query, search, game_label)
            filter_row = QHBoxLayout()
            filter_row.setSpacing(24)
            controls = []
            for name, title in [('artwork', 'Artwork'), ('shape', 'Shape'), ('resolution', 'Resolution')]:
                group = QHBoxLayout()
                group.setSpacing(8)
                heading = QLabel(title)
                group.addWidget(heading)
                checks = FilterChecks(name, self.filter_defaults[key][name])
                if name == 'resolution':
                    checks.setToolTip('Resolution ranges use the longest edge.')
                group.addWidget(checks)
                filter_row.addLayout(group)
                controls.append(checks)
            reset = QPushButton('Reset filters')
            filter_row.addStretch(1)
            filter_row.addWidget(reset)
            page_layout.addLayout(filter_row)
            self.filters[key] = tuple(controls)
            for widget in self.filters[key]:
                widget.changed.connect(lambda key=key: self.filter_images(key))
            reset.clicked.connect(lambda *_, key=key: self.reset_filters(key))
            images = QListWidget()
            images.setViewMode(QListWidget.ViewMode.IconMode)
            images.setResizeMode(QListWidget.ResizeMode.Adjust)
            images.setMovement(QListWidget.Movement.Static)
            images.setWrapping(True)
            tile_size = QSize(240, 360) if key == 'CoverImage' else QSize(300, 230)
            images.setGridSize(tile_size)
            images.setItemDelegate(ArtworkDelegate(images))
            images.setSpacing(10)
            images.setWordWrap(True)
            images.setUniformItemSizes(True)
            images.itemDoubleClicked.connect(lambda item, key=key: self.select_image(item, key))
            self.image_lists[key] = images
            page_layout.addWidget(images, 1)
            self.tabs.addTab(page, label)
        layout.addWidget(self.tabs, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.load_more_button = buttons.addButton('Load more', QDialogButtonBox.ButtonRole.ActionRole)
        self.load_more_button.hide()
        self.load_more_button.clicked.connect(lambda: self.load_images(more=True))
        self.apply_button = buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        for key, (source, query, search, _) in self.controls.items():
            source.currentIndexChanged.connect(lambda *_, key=key: self.update_source(key))
            query.textChanged.connect(lambda text, key=key: self.share_query(key, text))
            search.clicked.connect(self.search)
            query.returnPressed.connect(self.search)
        self.tabs.currentChanged.connect(self.activate_tab)
        self.finished.connect(self.finish)
        for key in self.image_keys:
            self.update_source(key)

    def showEvent(self, event):
        super().showEvent(event)
        if not self.initial_search_scheduled:
            self.initial_search_scheduled = True
            QTimer.singleShot(0, self.preload_images)

    @property
    def active_key(self):
        return self.image_keys[self.tabs.currentIndex()]

    def activate_tab(self, *_):
        self.update_load_more()
        self.filter_images(self.active_key)
        if not self.restore_catalogue(self.active_key):
            self.queue_search(self.active_key)

    def preload_images(self):
        for key in self.image_keys:
            self.queue_search(key, start=False)
        self.process_pending_searches()

    def queue_search(self, key, *, start=True):
        source, query, _, _ = self.controls[key]
        identity = (source.currentData(), query.text().strip())
        provider = self.providers.get(identity[0])
        if (provider and identity[1] and provider.is_exact_query(identity[1])
                and identity not in self.automatic_searches
                and identity not in self.catalogue_games):
            self.automatic_searches.add(identity)
            self.pending_searches.append((key, identity))
        if start:
            self.process_pending_searches()

    def process_pending_searches(self):
        if self.busy or self.closed:
            return
        while self.pending_searches:
            key, identity = self.pending_searches.pop(0)
            source, query, _, _ = self.controls[key]
            if identity != (source.currentData(), query.text().strip()):
                self.automatic_searches.discard(identity)
                continue
            if self.restore_catalogue(key):
                continue
            self.search(key=key, refresh=False)
            return

    @property
    def source(self):
        return self.controls[self.active_key][0]

    @property
    def query(self):
        return self.controls[self.active_key][1]

    @property
    def search_button(self):
        return self.controls[self.active_key][2]

    @property
    def game_label(self):
        return self.controls[self.active_key][3]

    @property
    def selected_game(self):
        return self.selected_games.get(self.active_key)

    @selected_game.setter
    def selected_game(self, value):
        self.selected_games[self.active_key] = value

    def update_source(self, key):
        source, query, search, label = self.controls[key]
        self.selected_games.pop(key, None)
        self.loaded_searches.pop(key, None)
        label.setText('Search for a game to load images.')
        self.image_lists[key].clear()
        self.update_load_more()
        provider = self.providers.get(source.currentData())
        query.blockSignals(True)
        query.setText(self.provider_queries.get(source.currentData(), ''))
        query.blockSignals(False)
        if provider:
            query.setPlaceholderText(provider.query_hint)
        search.setEnabled(provider is not None)
        if not self.restore_catalogue(key) and self.initial_search_scheduled:
            self.queue_search(key)

    def restore_catalogue(self, key):
        source, query, _, label = self.controls[key]
        identity = (source.currentData(), query.text().strip())
        selected = self.catalogue_games.get(identity)
        catalogue_key = (identity[0], str(selected['id'])) if selected else None
        if self.busy or catalogue_key not in self.catalogues:
            return False
        self.selected_games[key] = selected
        self.loaded_searches[key] = identity
        label.setText(f"{source.currentText()} — {selected['name']}")
        self.show_images({key: self.catalogues[catalogue_key]})
        self.update_load_more()
        return True

    def share_query(self, key, text):
        provider_id = self.controls[key][0].currentData()
        if provider_id is None:
            return
        self.provider_queries[provider_id] = text
        for source, query, _, _ in self.controls.values():
            if source.currentData() == provider_id and query.text() != text:
                query.blockSignals(True)
                query.setText(text)
                query.blockSignals(False)

    @property
    def images(self):
        return self.image_lists[self.image_keys[self.tabs.currentIndex()]]

    def run(self, function, complete):
        if self.busy or self.closed:
            return
        self.busy = True
        self.load_more_button.setEnabled(False)
        self.tabs.setEnabled(False)
        self.apply_button.setEnabled(False)
        for widget in (self.source, self.query, self.search_button):
            widget.setEnabled(False)
        self.status.setText(f'Downloading from {self.source.currentText()}…')
        self.task = Task(function)
        def done(value, error=False):
            self.busy = False
            self.tabs.setEnabled(True)
            if self.closed:
                if self.result() != QDialog.DialogCode.Accepted:
                    self.cache.cleanup()
                return
            self.apply_button.setEnabled(bool(self.applied))
            for widget in (self.source, self.query, self.search_button):
                widget.setEnabled(True)
            self.status.setText(str(value) if error else '')
            if not error:
                complete(value)
            self.update_load_more()
            QTimer.singleShot(0, self.process_pending_searches)
        self.task.signals.succeeded.connect(lambda value: done(value))
        self.task.signals.failed.connect(lambda error: done(error, True))
        QThreadPool.globalInstance().start(self.task)

    def search(self, *_, key=None, refresh=True):
        key = key or self.active_key
        source, query, _, _ = self.controls[key]
        provider = self.providers.get(source.currentData())
        if not provider or self.busy:
            return
        text = query.text()
        self.run(lambda: provider.search(text),
                 lambda results: self.show_games(results, key=key, refresh=refresh))
        if self.busy:
            self.status.setText(f'Downloading from {source.currentText()}…')

    def show_games(self, results, *, key=None, refresh=False):
        key = key or self.active_key
        if not results:
            self.status.setText('No games found. Try a game ID or another title.')
            return
        if len(results) == 1:
            selected = results[0]
        else:
            picker = GameSearchResults(results, self)
            if run_dialog(picker) != QDialog.DialogCode.Accepted:
                return
            selected = picker.selected_game
        if selected:
            self.selected_games[key] = selected
            source, _, _, label = self.controls[key]
            label.setText(f"{source.currentText()} — {selected['name']}")
            self.load_images(key=key, refresh=refresh)

    def update_load_more(self):
        game = self.selected_game
        key = (self.source.currentData(), str(game['id'])) if game else None
        artwork = self.filters[self.active_key][0].values()
        self.load_more_button.setVisible(any(more for image_type, (_, more) in self.catalogue_pages.get(key, {}).items()
                                              if image_type in artwork))
        self.load_more_button.setEnabled(not self.busy)

    def load_images(self, *_, more=False, key=None, refresh=False):
        kind = key or self.active_key
        selected = self.selected_games.get(kind)
        if not selected or self.busy or self.closed:
            return
        if not more:
            self.image_lists[kind].clear()
        source, query, _, _ = self.controls[kind]
        provider = self.providers[source.currentData()]
        game_id = selected['id']
        identity = (source.currentData(), query.text().strip())
        catalogue_key = (source.currentData(), str(game_id))
        if catalogue_key in self.catalogues and not more and not refresh:
            self.loaded_searches[kind] = identity
            self.show_images({kind: self.catalogues[catalogue_key]})
            self.update_load_more()
            return
        self.serial += 1
        destination = Path(self.cache.name) / str(self.serial)
        destination.mkdir()
        previous_pages = {} if refresh else self.catalogue_pages.get(catalogue_key, {})
        previous_urls = self.catalogue_urls.get(catalogue_key, set())
        filter_tabs = [kind] if refresh or more else [tab for tab, (tab_source, tab_query, _, _) in self.controls.items()
                                                    if (tab_source.currentData(), tab_query.text().strip()) == identity]
        filter_sets = [tuple(widget.values() for widget in self.filters[tab]) for tab in filter_tabs]
        artwork_types = {image_type for artwork, _, _ in filter_sets for image_type in artwork}
        scroll = self.images.verticalScrollBar().value()
        def fetch():
            result, errors, candidates = [], [], {}
            pages = dict(previous_pages)
            for image_type in self.image_keys:
                if image_type not in provider.image_types or image_type not in artwork_types:
                    continue
                page, remaining = previous_pages.get(image_type, (0, True))
                if more and not remaining:
                    continue
                try:
                    images, remaining = provider.image_page(game_id, image_type, page)
                    pages[image_type] = (page + 1, remaining)
                    for candidate in images:
                        url = candidate['url']
                        if url not in candidates:
                            candidates[url] = (candidate, set())
                        candidates[url][1].add(image_type)
                except Exception as error:
                    errors.append(str(error))
            downloaded = set()
            for index, (candidate, types) in enumerate(candidates.values()):
                if self.closed:
                    break
                width, height = candidate.get('width', 0), candidate.get('height', 0)
                known_size = isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0
                if not any(set(artwork).intersection(types) and
                           (not known_size or (matches_shape(width, height, shape) and
                                               matches_resolution(max(width, height), resolution)))
                           for artwork, shape, resolution in filter_sets):
                    continue
                try:
                    path = self.downloaded_urls.get(candidate['url'])
                    if path is None:
                        path = download_artwork(candidate['url'], destination / f'artwork-{index}.img')
                        self.downloaded_urls[candidate['url']] = path
                    result.append((candidate.get('label', 'Artwork'), path, types))
                    downloaded.add(candidate['url'])
                except Exception as error:
                    errors.append(f"{candidate.get('label', 'Artwork')}: {error}")
            return (result, errors), pages, downloaded
        def complete(payload):
            result, pages, urls = payload
            previous = self.catalogues.get(catalogue_key, ([], []))
            combined = {}
            for label, path, types in previous[0] + result[0]:
                if path in combined:
                    combined[path][2].update(types)
                else:
                    combined[path] = (label, path, set(types))
            result = (list(combined.values()), result[1])
            self.catalogues[catalogue_key] = result
            self.catalogue_games[identity] = selected
            self.catalogue_pages[catalogue_key] = pages
            self.catalogue_urls[catalogue_key] = previous_urls | urls
            self.loaded_searches[kind] = identity
            for tab, (tab_source, tab_query, _, label) in self.controls.items():
                if (tab_source.currentData(), tab_query.text().strip()) == identity:
                    self.selected_games[tab] = selected
                    self.loaded_searches[tab] = identity
                    label.setText(f"{tab_source.currentText()} — {selected['name']}")
                    self.show_images({tab: result})
            self.filter_images(self.active_key)
            if more:
                self.images.verticalScrollBar().setValue(scroll)
        self.run(fetch, complete)

    def show_images(self, payload):
        total, warnings = 0, []
        for key, (results, errors) in payload.items():
            images = self.image_lists[key]
            images.clear()
            for entry in results:
                label, path = entry[:2]
                types = entry[2] if len(entry) > 2 else {key}
                pixmap = self.image_pixmaps.get(path)
                if pixmap is None:
                    pixmap = QPixmap(path)
                    self.image_pixmaps[path] = pixmap
                caption = label
                if not pixmap.isNull():
                    width, height = pixmap.width(), pixmap.height()
                    divisor = gcd(width, height)
                    caption = f'{width}×{height} ({width // divisor}:{height // divisor})'
                item = QListWidgetItem(caption)
                if not pixmap.isNull():
                    item.setData(Qt.ItemDataRole.DecorationRole, pixmap.scaled(
                        600, 600, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                item.setData(Qt.ItemDataRole.UserRole + 2, types)
                item.setData(Qt.ItemDataRole.UserRole + 3, (pixmap.width(), pixmap.height()))
                item.setSizeHint(images.gridSize())
                item.setToolTip(label)
                item.setData(Qt.ItemDataRole.UserRole, path)
                item.setData(Qt.ItemDataRole.UserRole + 1, self.applied.get(key) == path)
                images.addItem(item)
            total += len(results)
            warnings.extend(f'{key}: {error}' for error in errors)
            images.setToolTip('\n'.join(errors) if errors else 'No images available.' if not results else '')
            if results:
                images.setCurrentRow(0)
        self.status.setText(f'{total} images available.' if total else 'No artwork available.')
        self.status.setToolTip('\n'.join(warnings))
        for key in payload:
            self.filter_images(key)

    def reset_filters(self, key):
        category, shape, resolution = self.filters[key]
        for name, widget in zip(OPTIONS, (category, shape, resolution)):
            widget.blockSignals(True)
            widget.set_values(self.filter_defaults[key][name])
            widget.blockSignals(False)
        self.filter_images(key)

    def filter_images(self, key):
        if key not in self.image_lists:
            return
        category, shape, resolution = self.filters[key]
        images = self.image_lists[key]
        visible = 0
        for index in range(images.count()):
            item = images.item(index)
            types = item.data(Qt.ItemDataRole.UserRole + 2) or {key}
            width, height = item.data(Qt.ItemDataRole.UserRole + 3) or (0, 0)
            edge = max(width, height)
            show = (bool(set(category.values()).intersection(types))
                    and matches_shape(width, height, shape.values())
                    and matches_resolution(edge, resolution.values()))
            item.setHidden(not show)
            visible += int(show)
        if key == self.active_key and images.count():
            self.status.setText(f'{visible} of {images.count()} images shown. Double-click an image to select it.')
            if images.currentItem() is None or images.currentItem().isHidden():
                images.setCurrentItem(next((images.item(i) for i in range(images.count())
                                            if not images.item(i).isHidden()), None))
        if key == self.active_key:
            self.update_load_more()

    def select_image(self, item=None, key=None):
        key = key or self.active_key
        item = item or self.image_lists[key].currentItem()
        if item and not self.busy:
            self.applied[key] = item.data(Qt.ItemDataRole.UserRole)
            images = self.image_lists[key]
            for row in range(images.count()):
                candidate = images.item(row)
                candidate.setData(Qt.ItemDataRole.UserRole + 1, candidate is item)
            images.viewport().update()
            self.apply_button.setEnabled(True)
            self.status.setText('Image selected. Apply to fill the editor, then Save to keep it.')

    def finish(self, result):
        self.closed = True
        self.pending_searches.clear()
        self.image_pixmaps.clear()
        self.downloaded_urls.clear()
        for images in self.image_lists.values():
            images.clear()
        if result != QDialog.DialogCode.Accepted and not self.busy:
            self.cache.cleanup()
