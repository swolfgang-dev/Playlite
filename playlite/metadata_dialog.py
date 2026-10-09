from .theme import set_style
"""Search and preview metadata without blocking the desktop interface."""
from pathlib import Path
from .lifecycle import run_dialog
import filecmp
import json
from tempfile import TemporaryDirectory

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal, QSettings, QEvent
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
    QHeaderView, QCheckBox, QComboBox, QStackedWidget, QWidget, QSizePolicy, QTabWidget,
    QRadioButton, QButtonGroup, QTextBrowser, QScrollArea, QAbstractItemView,
)
from PyQt6.QtGui import QPixmap

from .metadata import download_artwork


class MetadataTable(QTableWidget):
    def showEvent(self, event):
        super().showEvent(event)
        if getattr(self, 'fit_all_fields', False):
            self.fit_fields_height()

    def fit_fields_height(self):
        height = sum(self.rowHeight(row) for row in range(self.rowCount()))
        height += self.horizontalHeader().height() + self.frameWidth() * 2
        margins = self.viewportMargins()
        height += max(0, margins.top() - self.horizontalHeader().height()) + margins.bottom()
        self.setFixedHeight(height + 4)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if getattr(self, 'fit_cell_contents', False):
            self.fit_rows()

    def fit_rows(self):
        for row in range(1, self.rowCount()):
            heights = [28]
            for column in range(self.columnCount()):
                widget = self.cellWidget(row, column)
                if widget is not None and widget.layout() is not None:
                    layout = widget.layout()
                    margins = layout.contentsMargins()
                    width = max(1, self.columnWidth(column) - margins.left() - margins.right())
                    height = margins.top() + margins.bottom()
                    count = 0
                    for index in range(layout.count()):
                        child = layout.itemAt(index).widget()
                        if child is None:
                            continue
                        count += 1
                        height += child.heightForWidth(width) if child.hasHeightForWidth() else child.sizeHint().height()
                    heights.append(height + max(0, count - 1) * layout.spacing())
            self.setRowHeight(row, max(heights) + 2)

    def setCellWidget(self, row, column, widget):
        super().setCellWidget(row, column, widget)
        for child in [widget] + widget.findChildren(QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.Wheel and isinstance(watched, QWidget):
            parent = watched
            while parent is not None and parent is not self:
                if isinstance(parent, (CellScrollArea, CellTextBrowser)):
                    bar = parent.verticalScrollBar()
                    if bar.maximum() > bar.minimum():
                        parent.wheelEvent(event)
                        return True
                parent = parent.parentWidget()
            if parent is self:
                self.wheelEvent(event)
                return True
        return super().eventFilter(watched, event)

    def wheelEvent(self, event):
        delta = event.pixelDelta().y()
        if not delta:
            delta = event.angleDelta().y() / 120 * 60
        if not delta:
            super().wheelEvent(event)
            return
        remainder = getattr(self, '_wheel_remainder', 0) + delta
        movement = int(remainder)
        self._wheel_remainder = remainder - movement
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() - movement)
        event.accept()


def scroll_parent_table(cell, event):
    parent = cell.parentWidget()
    while parent is not None:
        if isinstance(parent, MetadataTable):
            parent.wheelEvent(event)
            return
        parent = parent.parentWidget()
    event.ignore()


class CellScrollArea(QScrollArea):
    def wheelEvent(self, event):
        super().wheelEvent(event)
        if self.verticalScrollBar().maximum() > self.verticalScrollBar().minimum():
            event.accept()
        else:
            scroll_parent_table(self, event)


class CellTextBrowser(QTextBrowser):
    def wheelEvent(self, event):
        super().wheelEvent(event)
        if self.verticalScrollBar().maximum() > self.verticalScrollBar().minimum():
            event.accept()
        else:
            scroll_parent_table(self, event)


class Signals(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        from PyQt6 import sip
        try:
            value = self.function()
            signal, payload = self.signals.succeeded, value
        except Exception as error:
            if sip.isdeleted(self.signals):
                return
            signal, payload = self.signals.failed, str(error)
        if not sip.isdeleted(self.signals):
            try:
                signal.emit(payload)
            except RuntimeError:
                # Qt can tear down signal objects while a worker finishes on exit.
                if not sip.isdeleted(self.signals):
                    raise


LABELS = {'Icon': 'Icon', 'Name': 'Name', 'SortingName': 'Sorting name', 'Description': 'Short description', 'FullDescription': 'Description', 'Developers': 'Developers',
          'Publishers': 'Publishers', 'Genres': 'Genres', 'Features': 'Features',
          'Platforms': 'Platforms', 'ReleaseDate': 'Release date', 'CriticScore': 'Critic score',
          'Links': 'Links', 'CommunityScore': 'Community score', 'Tags': 'Tags',
          'Categories': 'Categories', 'Series': 'Series', 'CoverImage': 'Cover art', 'HeaderImage': 'Header artwork', 'BackgroundImage': 'Background artwork'}
FIELD_ORDER = ['Name', 'SortingName', 'ReleaseDate', 'Genres', 'Developers', 'Publishers', 'Platforms',
               'Features', 'Description', 'FullDescription', 'Links', 'CriticScore', 'CommunityScore', 'Tags', 'Categories', 'Series', 'Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage']


def display(value):
    if isinstance(value, dict) and 'ReleaseDate' in value:
        from .date_display import display_date
        return display_date(value['ReleaseDate'])
    if isinstance(value, list):
        return ', '.join(item['Name'] if isinstance(item, dict) else str(item) for item in value)
    return '' if value is None else str(value)


def has_value(value):
    return value is not None and value != '' and value != []


def equivalent(current, incoming):
    if isinstance(current, list) and isinstance(incoming, list):
        def identity(value):
            if isinstance(value, dict):
                return (value.get('Name', '').casefold(), value.get('Url', '').rstrip('/'))
            return str(value).strip().casefold()
        return {identity(value) for value in current} == {identity(value) for value in incoming}
    if isinstance(current, dict) and 'ReleaseDate' in current:
        current = current['ReleaseDate']
    if isinstance(incoming, dict) and 'ReleaseDate' in incoming:
        incoming = incoming['ReleaseDate']
    from .metadata import release_date
    if isinstance(current, str) and isinstance(incoming, str):
        old_date, new_date = release_date(current), release_date(incoming)
        if old_date and new_date:
            return old_date == new_date
    return display(current).strip().casefold() == display(incoming).strip().casefold()


class MetadataDownloader(QDialog):
    def __init__(self, current, parent=None, settings_path=None, mode='all', save_ids=None):
        super().__init__(parent)
        if mode not in ('all', 'metadata', 'images'):
            raise ValueError('Unknown download mode.')
        self.mode = mode
        self.settings_key = 'metadata/fields' if mode != 'images' else 'images/fields'
        current = dict(current)
        self.current = current
        self.save_ids_handler = save_ids
        self.payload = None
        self.applied = None
        self.cache = TemporaryDirectory(prefix='playlite-metadata-')
        self.task = None
        self.closed = False
        self.selected_fields = None
        self.source_toggles = {}
        self.metadata_ids = dict(current.get('MetadataIds') or {})
        self.id_fields = {}
        self.provider_payloads = {}
        self.provider_queue = []
        self.image_keys = ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage')
        self.resolving_id = False
        self.auto_fields = {}
        self.choices = {}
        self.radio_groups = []
        self.settings = QSettings(str(settings_path), QSettings.Format.IniFormat) if settings_path else None
        from .providers import discover_providers
        self.providers = discover_providers()
        self.provider_ids = list(self.providers)
        self.table_providers = dict(self.providers)
        self.provider_columns = list(enumerate(self.table_providers, 1))
        self.provider = self.provider_ids[0]
        self.setWindowTitle('Download metadata')
        self.resize(1000, 700)
        layout = QVBoxLayout(self)
        self.steps = QLabel()
        layout.addWidget(self.steps)
        self.pages = QStackedWidget()
        layout.addWidget(self.pages, 1)

        options = QWidget()
        options_layout = QVBoxLayout(options)
        options_layout.addWidget(QLabel('Select the images to download.' if mode == 'images' else 'Select the fields to download and their metadata source.'))
        source_row = QHBoxLayout()
        source_label = QLabel('Source')
        source_row.addWidget(source_label)
        self.source = QComboBox()
        self.source.addItems(self.provider_ids)
        if mode == 'metadata':
            source_label.hide()
            self.source.hide()
        source_row.addWidget(self.source)
        source_row.addStretch()
        if mode != 'metadata':
            options_layout.addLayout(source_row)
        self.download_tabs = QTabWidget()
        self.fields = MetadataTable(0, 1 + len(self.table_providers))
        self.artwork_fields = MetadataTable(0, 2)
        for table, title in [(self.fields, 'Metadata'), (self.artwork_fields, 'Images')]:
            table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
            table.verticalScrollBar().setSingleStep(20)
            table.setHorizontalHeaderLabels(['Field'] + [provider.name for provider in self.table_providers.values()] if table is self.fields else ['Field', 'Download source'])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            table.verticalHeader().hide()
            table.verticalHeader().setMinimumSectionSize(28)
            set_style(table, 'QTableWidget::item { padding: 2px 6px; }')
            if mode != 'metadata' and (mode == 'all' or (mode == 'images') == (title == 'Images')):
                self.download_tabs.addTab(table, title)
        defaults = [key for key in FIELD_ORDER if key not in ('Name', 'Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage')]
        if mode == 'images':
            defaults = ['CoverImage', 'HeaderImage']
        if self.settings:
            defaults = self.settings.value(self.settings_key, defaults, type=list)
        option_fields = FIELD_ORDER
        for key in option_fields:
            if mode != 'all' and mode != 'metadata' and (mode == 'images') != (key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage')):
                continue
            table = self.artwork_fields if mode != 'metadata' and key in self.image_keys else self.fields
            row_index = table.rowCount()
            table.insertRow(row_index)
            item = QTableWidgetItem(LABELS[key])
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable)
            item.setData(Qt.ItemDataRole.UserRole, key)
            if mode == 'metadata':
                item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            else:
                item.setCheckState(Qt.CheckState.Checked if key in defaults else Qt.CheckState.Unchecked)
            table.setItem(row_index, 0, item)
            if table is self.fields:
                self.source_toggles[key] = {}
                for column, provider in self.provider_columns:
                    toggle = QCheckBox()
                    supported = key in self.table_providers[provider].fields
                    toggle.setEnabled(supported)
                    preferred = self.settings.value(f'metadata/sources/{key}/{provider}', True, type=bool) if self.settings else True
                    toggle.setChecked(supported and preferred)
                    cell = QWidget()
                    set_style(cell, 'background: transparent;')
                    cell_layout = QHBoxLayout(cell)
                    cell_layout.setContentsMargins(0, 0, 0, 0)
                    cell_layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignCenter)
                    table.setCellWidget(row_index, column, cell)
                    self.source_toggles[key][provider] = toggle
            else:
                source = QComboBox()
                source.addItems(self.provider_ids)
                source.currentTextChanged.connect(self.change_provider)
                table.setCellWidget(row_index, 1, source)
            table.setRowHeight(row_index, 28)
        if self.fields.rowCount():
            self.fields.insertRow(0)
            self.fields.setItem(0, 0, QTableWidgetItem('All fields'))
            self.column_toggles = {}
            for column, provider in self.provider_columns:
                cell = QWidget()
                set_style(cell, 'background: transparent;')
                cell_layout = QHBoxLayout(cell)
                cell_layout.setContentsMargins(0, 0, 0, 0)
                toggle = QCheckBox()
                toggle.setChecked(True)
                toggle.clicked.connect(lambda checked, provider=provider: self.toggle_source_column(provider, checked))
                cell_layout.addWidget(toggle, 0, Qt.AlignmentFlag.AlignCenter)
                self.column_toggles[provider] = toggle
                self.fields.setCellWidget(0, column, cell)
                for toggles in self.source_toggles.values():
                    toggles[provider].toggled.connect(lambda checked, provider=provider: self.sync_source_column(provider))
            for provider in self.column_toggles:
                self.sync_source_column(provider)
            self.fields.setRowHeight(0, 28)
            self.fields.insertRow(0)
            self.fields.setItem(0, 0, QTableWidgetItem('Metadata ID'))
            for column, provider in self.provider_columns:
                if provider not in self.providers:
                    self.fields.setItem(0, column, QTableWidgetItem('—'))
                    continue
                field = QLineEdit(str(self.metadata_ids.get(provider) or ''))
                field.setAlignment(Qt.AlignmentFlag.AlignCenter)
                field.setPlaceholderText('ID')
                field.setToolTip(f'{provider} game ID. Use Save metadata IDs to save immediately.')
                field.textChanged.connect(lambda value, provider=provider: self.update_metadata_id(provider, value))
                self.id_fields[provider] = field
                self.fields.setCellWidget(0, column, field)
            self.fields.setRowHeight(0, 34)
            self.fields.horizontalHeader().setStretchLastSection(False)
            for column in range(self.fields.columnCount()):
                self.fields.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Fixed)
            self.fit_metadata_columns()
            table_height = (sum(self.fields.rowHeight(row) for row in range(self.fields.rowCount()))
                            + self.fields.horizontalHeader().sizeHint().height()
                            + self.fields.frameWidth() * 2)
            available_height = self.screen().availableGeometry().height() - 40
            self.fields.setFixedHeight(min(table_height, max(180, available_height - 260)))
            self.fields.fit_all_fields = True
            self.fields.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
            self.resize(self.width(), min(available_height, max(self.height(), table_height + 260)))
        if mode == 'metadata':
            options_layout.addWidget(self.fields)
        else:
            options_layout.addWidget(self.download_tabs)
        defaults_row = QHBoxLayout()
        if self.id_fields:
            save_ids_button = QPushButton('Save metadata IDs')
            save_ids_button.clicked.connect(self.save_metadata_ids)
            defaults_row.addWidget(save_ids_button)
        if mode == 'metadata':
            self.save_field_defaults_button = QPushButton('Save defaults')
            self.save_field_defaults_button.setEnabled(self.settings is not None)
            self.save_field_defaults_button.setToolTip('Use these field and source selections for future metadata downloads. Metadata IDs are not saved.')
            self.save_field_defaults_button.clicked.connect(self.save_field_defaults)
            defaults_row.addWidget(self.save_field_defaults_button)
        defaults_row.addStretch()
        options_layout.addLayout(defaults_row)
        self.skip_existing = QCheckBox('Only download missing images' if mode == 'images' else 'Only download missing metadata')
        options_layout.addWidget(self.skip_existing)
        self.save_defaults = QCheckBox('Save selected fields as default')
        self.save_defaults.setEnabled(self.settings is not None)
        options_layout.addWidget(self.save_defaults)
        if mode == 'metadata':
            self.skip_existing.hide()
            self.save_defaults.hide()
            for toggles in self.source_toggles.values():
                for toggle in toggles.values():
                    toggle.toggled.connect(self.persist_field_defaults)
        self.pages.addWidget(options)

        match_page = QWidget()
        match_layout = QVBoxLayout(match_page)
        match_layout.addWidget(QLabel('Search for the game and select the matching result.'))
        row = QHBoxLayout()
        self.query = QLineEdit(current.get('Name', ''))
        self.query.setPlaceholderText(self.providers[self.provider].query_hint)
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.query)
        self.search_button = QPushButton('Search')
        self.search_button.clicked.connect(self.search)
        row.addWidget(self.search_button)
        match_layout.addLayout(row)
        self.results = QListWidget()
        self.results.itemDoubleClicked.connect(self.choose_result)
        match_layout.addWidget(self.results)
        self.pages.addWidget(match_page)

        comparison = QWidget()
        comparison_layout = QVBoxLayout(comparison)
        self.heading = QLabel('Choose a game, then select fields to apply. Artwork is optional.')
        self.heading.setWordWrap(True)
        comparison_layout.addWidget(self.heading)
        self.defaults_key = 'images/reviewDefaults' if mode == 'images' else 'metadata/reviewDefaults'
        try:
            self.review_defaults = json.loads(self.settings.value(self.defaults_key, '{}')) if self.settings else {}
        except (ValueError, TypeError):
            self.review_defaults = {}
        if 'checked' in self.review_defaults.get('Links', {}):
            self.review_defaults['Links'].pop('checked')
            if self.settings is not None:
                self.settings.setValue(self.defaults_key, json.dumps(self.review_defaults))
                self.settings.sync()
        self.preview = MetadataTable(0, 3)
        self.preview.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.preview.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.preview.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.preview.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.preview.verticalScrollBar().setSingleStep(20)
        self.preview.setHorizontalHeaderLabels(['Field', 'Current', 'Downloaded'])
        self.preview.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.preview.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.preview.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.preview.setWordWrap(True)
        self.preview.verticalHeader().hide()
        comparison_layout.addWidget(self.preview, 1)
        self.image_tabs = None
        if mode == 'images':
            comparison_layout.removeWidget(self.preview)
            self.image_tabs = QTabWidget()
            self.image_tab_keys = ['CoverImage', 'HeaderImage', 'BackgroundImage']
            for key in self.image_tab_keys:
                page = QWidget()
                QVBoxLayout(page).setContentsMargins(0, 0, 0, 0)
                self.image_tabs.addTab(page, LABELS.get(key, key))
            comparison_layout.addWidget(self.image_tabs, 1)
            self.image_tabs.currentChanged.connect(self.update_image_tab)
            self.update_image_tab(0)
        defaults_row = QHBoxLayout()
        self.set_defaults_button = QPushButton('Set as default')
        self.set_defaults_button.clicked.connect(self.set_review_defaults)
        self.unset_defaults_button = QPushButton('Unset default')
        self.unset_defaults_button.clicked.connect(self.unset_review_defaults)
        self.show_defaults_button = QPushButton('Show list defaults')
        self.show_defaults_button.clicked.connect(self.show_list_defaults)
        self.choose_defaults_button = QPushButton('Choose defaults')
        self.choose_defaults_button.clicked.connect(self.choose_review_defaults)
        for button in (self.choose_defaults_button, self.set_defaults_button, self.unset_defaults_button, self.show_defaults_button):
            button.setEnabled(self.settings is not None)
            defaults_row.addWidget(button)
        defaults_row.addStretch()
        comparison_layout.addLayout(defaults_row)
        self.pages.addWidget(comparison)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.apply_button = self.buttons.button(QDialogButtonBox.StandardButton.Apply)
        self.apply_button.setProperty('primary',True)
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.apply)
        self.buttons.rejected.connect(self.reject)
        navigation = QHBoxLayout()
        self.back_button = QPushButton('Back')
        self.back_button.clicked.connect(self.back)
        navigation.addWidget(self.back_button)
        navigation.addStretch()
        self.previous_image = QPushButton('Previous')
        self.next_image = QPushButton('Next')
        self.previous_image.clicked.connect(lambda: self.image_tabs.setCurrentIndex(self.image_tabs.currentIndex() - 1))
        self.next_image.clicked.connect(lambda: self.image_tabs.setCurrentIndex(self.image_tabs.currentIndex() + 1))
        image_button_width = max(self.previous_image.sizeHint().width(), self.next_image.sizeHint().width())
        for button in (self.previous_image, self.next_image):
            button.setFixedWidth(image_button_width)
            button.hide()
            navigation.addWidget(button)
        self.next_button = QPushButton('Download')
        self.skip_provider_button = QPushButton('Skip')
        self.skip_provider_button.setToolTip('Skip this metadata source for this download.')
        self.skip_provider_button.clicked.connect(self.skip_provider)
        navigation.addWidget(self.skip_provider_button)
        self.next_button.clicked.connect(self.next_step)
        navigation.addWidget(self.next_button)
        navigation.addWidget(self.buttons)
        layout.addLayout(navigation)
        self.finished.connect(lambda: setattr(self, 'closed', True))
        self.source.currentTextChanged.connect(self.change_provider)
        key = 'images/provider' if mode == 'images' else 'metadata/provider'
        preferred = self.settings.value(key, self.provider) if self.settings else self.provider
        self.change_provider(preferred if preferred in self.providers else self.provider)
        self.set_step(0)

    def change_provider(self, provider):
        self.provider = provider
        self.source.blockSignals(True)
        self.source.setCurrentText(provider)
        self.source.blockSignals(False)
        for table in (self.fields, self.artwork_fields):
            for row in range(table.rowCount()):
                combo = table.cellWidget(row, 1)
                if isinstance(combo, QComboBox):
                    combo.blockSignals(True)
                    combo.setCurrentText(provider)
                    combo.blockSignals(False)
        if self.settings:
            key = 'images/provider' if self.mode == 'images' else 'metadata/provider'
            self.settings.setValue(key, provider)
        plugin = self.providers[provider]
        self.query.setPlaceholderText(plugin.query_hint)
        linked = plugin.linked_query(self.current)
        explicit = self.id_fields[provider].text().strip() if provider in self.id_fields else ''
        self.query.setText(str(explicit or (self.current.get('MetadataIds') or {}).get(provider)
                               or linked or self.current.get('Name', '')))
        self.setWindowTitle(f'Download {"images" if self.mode == "images" else "metadata"} — {provider}')

    def update_metadata_id(self, provider, value):
        value = value.strip()
        if value:
            self.metadata_ids[provider] = value
        else:
            self.metadata_ids.pop(provider, None)
        self.fit_metadata_columns()

    def fit_metadata_columns(self):
        self.fields.ensurePolished()
        header = self.fields.horizontalHeader()
        header.ensurePolished()
        metrics = self.fields.fontMetrics()
        field_widths = [metrics.horizontalAdvance(self.fields.item(row, 0).text()) + 24
                        for row in range(self.fields.rowCount()) if self.fields.item(row, 0)]
        self.fields.setColumnWidth(0, max([80] + field_widths))
        widths = [field.fontMetrics().horizontalAdvance(field.text() or field.placeholderText()) + 40
                  for field in self.id_fields.values()]
        width = max([80] + widths + [header.sectionSizeHint(column) for column, _ in self.provider_columns]
                    + [header.fontMetrics().horizontalAdvance(plugin.name) + 40 for plugin in self.table_providers.values()])
        for column, provider in self.provider_columns:
            self.fields.setColumnWidth(column, width)

    def save_metadata_ids(self):
        try:
            if self.save_ids_handler is None:
                raise ValueError('Save the game to the library before saving metadata IDs.')
            self.save_ids_handler(dict(self.metadata_ids))
        except Exception as error:
            self.status.setText(f'Could not save metadata IDs: {error}')
            return
        self.current['MetadataIds'] = dict(self.metadata_ids)
        self.status.setText('Metadata IDs saved.')

    def set_step(self, index):
        self.pages.setCurrentIndex(index)
        self.steps.setText(['1. Images and sources' if self.mode == 'images' else '1. Fields and sources', '2. Select game', '3. Compare images' if self.mode == 'images' else '3. Compare metadata'][index])
        self.back_button.setVisible(index > 0)
        self.next_button.setVisible(index < 2)
        self.next_button.setText('Download' if index == 0 else 'Select')
        self.skip_provider_button.setVisible(index == 1)
        self.apply_button.setVisible(index == 2)
        for button in (self.previous_image, self.next_image):
            button.setVisible(self.mode == 'images' and index == 2)
        if self.image_tabs is not None:
            self.update_image_tab(self.image_tabs.currentIndex())

    def update_image_tab(self, index):
        if self.image_tabs is None:
            return
        self.image_tabs.widget(index).layout().addWidget(self.preview)
        key = self.image_tab_keys[index]
        for row in range(self.preview.rowCount()):
            item = self.preview.item(row, 0)
            self.preview.setRowHidden(row, item is None or item.data(Qt.ItemDataRole.UserRole) != key)
        if hasattr(self, 'previous_image'):
            self.previous_image.setEnabled(index > 0)
            self.next_image.setEnabled(index < self.image_tabs.count() - 1)

    def save_field_defaults(self):
        self.persist_field_defaults()
        if self.settings is not None:
            self.status.setText('Default fields and sources saved.')

    def persist_field_defaults(self, *_):
        if self.settings is None:
            return
        checked = [item.data(Qt.ItemDataRole.UserRole) for item in self.field_items()
                   if (any(toggle.isChecked() for toggle in self.source_toggles[item.data(Qt.ItemDataRole.UserRole)].values())
                       if self.mode == 'metadata' else item.checkState() == Qt.CheckState.Checked)]
        self.settings.setValue(self.settings_key, checked)
        for key, toggles in self.source_toggles.items():
            for provider, toggle in toggles.items():
                self.settings.setValue(f'metadata/sources/{key}/{provider}', toggle.isChecked())
        self.settings.sync()

    def next_step(self):
        if self.pages.currentIndex() == 1:
            if self.results.currentItem():
                self.choose_result(self.results.currentItem())
            else:
                self.status.setText('Select a matching game first.')
            return
        checked = [item.data(Qt.ItemDataRole.UserRole) for item in self.field_items()
                   if (any(toggle.isChecked() for toggle in self.source_toggles[item.data(Qt.ItemDataRole.UserRole)].values())
                       if self.mode == 'metadata' else item.checkState() == Qt.CheckState.Checked)]
        selected = list(checked)
        if self.skip_existing.isChecked():
            selected = [key for key in selected if not self.current.get(key)]
        if not selected:
            self.status.setText('Select at least one field with metadata to download.')
            return
        self.selected_fields = selected
        if self.save_defaults.isChecked() and self.settings:
            self.save_field_defaults()
        self.provider_payloads = {}
        self.provider_queue = [provider for provider in self.provider_ids if any(
            key in selected and toggles[provider].isChecked() for key, toggles in self.source_toggles.items())]
        if self.mode != 'metadata' and any(key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage') for key in selected) and self.provider not in self.provider_queue:
            self.provider_queue.append(self.provider)
        if not self.provider_queue:
            self.status.setText('Enable at least one source for a selected field.')
            return
        if self.provider_queue:
            self.start_next_provider()
        else:
            self.show_combined_preview()

    def start_next_provider(self):
        provider = self.provider_queue.pop(0)
        self.change_provider(provider)
        query = self.query.text().strip()
        explicit = self.id_fields[provider].text().strip() if provider in self.id_fields else ''
        self.resolving_id = bool(explicit) and self.providers[provider].is_exact_query(query)
        if self.resolving_id:
            self.set_step(0)
            self.steps.setText(f'Resolving {provider} metadata ID…')
        else:
            self.set_step(1)
            self.steps.setText(f'2. Select the matching game on {provider}')
        self.search()

    def skip_provider(self):
        if self.pages.currentIndex() != 1 or not self.skip_provider_button.isEnabled():
            return
        self.resolving_id = False
        self.results.clear()
        if self.provider_queue:
            self.start_next_provider()
        elif self.provider_payloads:
            self.show_combined_preview()
        else:
            self.set_step(0)
            self.status.setText('All metadata sources were skipped. Choose sources to try again.')

    def sync_source_column(self, provider):
        states = [toggles[provider].isChecked() for toggles in self.source_toggles.values() if toggles[provider].isEnabled()]
        state = Qt.CheckState.Checked if all(states) else Qt.CheckState.Unchecked if not any(states) else Qt.CheckState.PartiallyChecked
        self.column_toggles[provider].setCheckState(state)

    def toggle_source_column(self, provider, enabled):
        for toggles in self.source_toggles.values():
            toggles[provider].setChecked(enabled and toggles[provider].isEnabled())

    def field_items(self):
        return [table.item(row, 0) for table in (self.fields, self.artwork_fields)
                for row in range(table.rowCount()) if table.item(row, 0).data(Qt.ItemDataRole.UserRole) is not None]

    def back(self):
        self.set_step(max(0, self.pages.currentIndex() - 1))
        self.status.clear()

    def select_values(self, downloaded):
        for choice in self.choices.values():
            if choice['kind'] == 'multi':
                side = next(reversed(choice['options'])) if downloaded else 'Current'
                choice['options'][side][0].setChecked(True)
            elif choice['kind'] == 'scalar':
                choice['new' if downloaded else 'current'].setChecked(True)
            else:
                for checkbox, value in choice['current']:
                    checkbox.setChecked(not downloaded)
                for checkbox, value in choice['new']:
                    checkbox.setChecked(downloaded)

    def busy(self, value, message=''):
        self.search_button.setEnabled(not value)
        self.query.setEnabled(not value)
        self.results.setEnabled(not value)
        self.back_button.setEnabled(not value)
        self.next_button.setEnabled(not value)
        self.skip_provider_button.setEnabled(not value)
        self.apply_button.setEnabled(not value and self.payload is not None)
        self.status.setText(message)

    def run_task(self, function, completed, message):
        self.busy(True, message)
        task = Task(function)
        self.task = task
        task.signals.succeeded.connect(completed)
        task.signals.failed.connect(self.failed)
        QThreadPool.globalInstance().start(task)

    def failed(self, message):
        if self.closed:
            return
        if self.resolving_id:
            self.resolving_id = False
            self.set_step(1)
        self.busy(False, message)

    def search(self):
        if self.closed or not self.search_button.isEnabled():
            return
        self.payload = None
        self.preview.setRowCount(0)
        query = self.query.text()
        search = self.providers[self.provider].search
        self.run_task(lambda: search(query), lambda results: self.show_results(results, query), f'Searching {self.provider}…')

    def show_results(self, results, query=None):
        if self.closed:
            return
        self.results.blockSignals(True)
        self.results.clear()
        for result in results:
            item = QListWidgetItem(f'{result["name"]}  ·  {result["id"]}')
            item.setData(Qt.ItemDataRole.UserRole, result['id'])
            self.results.addItem(item)
        self.results.blockSignals(False)
        self.busy(False, '' if results else 'No matches found. Try another game name or a URL from the selected source.')
        if len(results) == 1:
            self.results.setCurrentRow(0)
            query = (query if query is not None else self.query.text()).strip()
            exact = self.providers[self.provider].is_exact_query(query, results[0]['id'])
            explicit = self.id_fields[self.provider].text().strip() if self.provider in self.id_fields else ''
            if exact and explicit:
                self.choose_result(self.results.currentItem())
                return
        if self.resolving_id:
            self.resolving_id = False
            self.set_step(1)

    def choose_result(self, item, previous=None):
        if not item or self.closed:
            return
        self.payload = None
        self.preview.setRowCount(0)
        app_id = item.data(Qt.ItemDataRole.UserRole)
        self.metadata_ids[self.provider] = str(app_id)
        if self.provider in self.id_fields:
            self.id_fields[self.provider].setText(str(app_id))
        selected = {key for key in self.selected_fields or [] if (key not in self.source_toggles or self.source_toggles[key][self.provider].isChecked())}
        destination = Path(self.cache.name) / self.provider
        destination.mkdir(exist_ok=True)
        fetch = self.providers[self.provider].fetch
        def download():
            payload = fetch(app_id, selected)
            payload['files'] = {}
            payload['warnings'] = []
            source = self.providers[self.provider]
            for key in self.image_keys:
                if key not in selected:
                    continue
                try:
                    candidates = source.images(app_id, key) if key in source.image_types else [
                        {'url': payload['images'][key]}] if key in payload.get('images', {}) else []
                    errors = []
                    for candidate in candidates:
                        try:
                            payload['files'][key] = download_artwork(candidate['url'], destination / (key + '.img'))
                            break
                        except Exception as error:
                            errors.append(str(error))
                    if key not in payload['files']:
                        payload['warnings'].append(f'{LABELS[key]}: ' + (errors[-1] if errors else 'No image available.'))
                except Exception as error:
                    payload['warnings'].append(f'{LABELS[key]}: {error}')
            return payload
        provider = self.provider
        self.run_task(download, lambda payload: self.collect_provider(provider, payload), f'Downloading {provider} metadata…')

    def collect_provider(self, provider, payload):
        if self.closed:
            return
        self.resolving_id = False
        self.provider_payloads[provider] = payload
        self.busy(False)
        if self.provider_queue:
            self.start_next_provider()
        else:
            self.show_combined_preview()

    @staticmethod
    def list_identity(value):
        return json.dumps(value, sort_keys=True, ensure_ascii=False).strip().casefold()

    def select_source_values(self, provider):
        for choice in self.choices.values():
            if choice['kind'] == 'multi':
                choice['options'].get(provider, choice['options']['Current'])[0].setChecked(True)
            elif choice['kind'] == 'multi_list':
                radios = choice.get('radios', {})
                if radios:
                    radios.get(provider, radios['Current']).setChecked(True)
                for side, entries in choice['options'].items():
                    for checkbox, value in entries:
                        checkbox.setChecked(side == provider)

    def set_review_defaults(self):
        if self.settings is None:
            return
        for key, choice in self.choices.items():
            if choice['kind'] == 'multi':
                self.review_defaults[key] = {'source': next(side for side, (radio, value) in choice['options'].items() if radio.isChecked())}
            elif choice['kind'] == 'multi_list':
                entries = [entry for side, entries in choice['options'].items() if side != 'Current' for entry in entries]
                seen = {self.list_identity(value) for values in choice['options'].values() for _, value in values}
                selected = {self.list_identity(value) for checkbox, value in entries if checkbox.isChecked()}
                previous = set(self.review_defaults.get(key, {}).get('checked', []))
                self.review_defaults[key] = {'checked': sorted((previous - seen) | selected)}
                if key == 'Links':
                    self.review_defaults[key].pop('checked')
                radios = choice.get('radios', {})
                if radios:
                    self.review_defaults[key]['source'] = next(side for side, radio in radios.items() if radio.isChecked())
        self.settings.setValue(self.defaults_key, json.dumps(self.review_defaults))
        self.settings.sync()
        self.status.setText('Defaults saved: scalar sources and checked list entries will be reused.')

    def choose_review_defaults(self):
        for key, choice in self.choices.items():
            default = self.review_defaults.get(key, {})
            if choice['kind'] == 'multi':
                provider = default.get('source', 'Current')
                choice['options'].get(provider, choice['options']['Current'])[0].setChecked(True)
            elif choice['kind'] == 'multi_list':
                source = default.get('source', 'Current')
                radios = choice.get('radios', {})
                if radios:
                    radios.get(source, radios['Current']).setChecked(True)
                for provider, entries in choice['options'].items():
                    for checkbox, value in entries:
                        if provider == source or self.list_identity(value) in default.get('checked', []):
                            checkbox.setChecked(True)
        self.status.setText('Defaults selected. Additional checked list entries were kept.')

    def unset_review_defaults(self):
        self.review_defaults = {}
        if self.settings:
            self.settings.remove(self.defaults_key)
            self.settings.sync()
        self.select_source_values('Current')
        self.status.setText('Defaults cleared. All fields now keep their current values.')

    def remove_list_defaults(self, entries):
        for key, identity in entries:
            defaults = self.review_defaults.get(key, {})
            defaults['checked'] = [value for value in defaults.get('checked', []) if value != identity]
            choice = self.choices.get(key, {})
            if choice.get('kind') == 'multi_list':
                for values in choice['options'].values():
                    for checkbox, value in values:
                        if self.list_identity(value) == identity:
                            checkbox.setChecked(False)
        if self.settings is not None:
            self.settings.setValue(self.defaults_key, json.dumps(self.review_defaults))
            self.settings.sync()

    def show_list_defaults(self):
        dialog = QDialog(self)
        dialog.setWindowTitle('Saved list defaults')
        dialog.resize(600, 420)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel('Select saved items to remove. Changes are saved immediately.'))
        items = QListWidget()
        items.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(items)
        for key, defaults in self.review_defaults.items():
            for identity in defaults.get('checked', []):
                try:
                    value = json.loads(identity)
                except (ValueError, TypeError):
                    value = identity
                label = f'{value.get("Name", "")} — {value.get("Url", "")}' if isinstance(value, dict) else str(value)
                item = QListWidgetItem(f'{LABELS.get(key, key)}: {label}')
                item.setData(Qt.ItemDataRole.UserRole, (key, identity))
                items.addItem(item)
        empty = QLabel('No saved list defaults.')
        empty.setVisible(items.count() == 0)
        layout.addWidget(empty)
        buttons = QHBoxLayout()
        remove = QPushButton('Remove selected')
        remove.setEnabled(False)
        items.itemSelectionChanged.connect(lambda: remove.setEnabled(bool(items.selectedItems())))
        def remove_selected():
            selected = items.selectedItems()
            next_row = min((items.row(item) for item in selected), default=0)
            self.remove_list_defaults([item.data(Qt.ItemDataRole.UserRole) for item in selected])
            for item in selected:
                items.takeItem(items.row(item))
            if items.count():
                items.setCurrentRow(min(next_row, items.count() - 1))
            empty.setVisible(items.count() == 0)
        remove.clicked.connect(remove_selected)
        buttons.addWidget(remove)
        buttons.addStretch()
        close = QPushButton('Close')
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        run_dialog(dialog)

    def show_combined_preview(self):
        self.payload = {'providers': self.provider_payloads}
        self.auto_fields = {}
        self.choices = {}
        self.radio_groups = []
        self.set_step(2)
        self.heading.setText('Review every field. Choose a source for individual values, or combine checked list entries.')
        review_providers = dict(self.providers)
        review_providers.update({key: self.table_providers[key] for key in self.provider_payloads if key in self.table_providers and key not in self.providers})
        review_ids = list(review_providers)
        self.preview.setColumnCount(2 + len(review_providers))
        self.preview.setHorizontalHeaderLabels(['Field', 'Current'] + [provider.name for provider in review_providers.values()])
        for column in range(1, self.preview.columnCount()):
            self.preview.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        self.preview.setRowCount(1)
        self.preview.setItem(0, 0, QTableWidgetItem('All fields'))
        self.source_select_buttons = {}
        for column, provider in list(enumerate(['Current'] + review_ids, 1)):
            button = QPushButton('Select all')
            button.setFixedHeight(28)
            set_style(button, 'padding: 2px 8px;')
            button.clicked.connect(lambda checked=False, provider=provider: self.select_source_values(provider))
            self.preview.setCellWidget(0, column, button)
            self.source_select_buttons[provider] = button
        self.preview.setRowHeight(0, 32)
        warnings = [warning for payload in self.provider_payloads.values() for warning in payload.get('warnings', [])]
        for key in self.selected_fields:
            candidates = {}
            for provider, payload in self.provider_payloads.items():
                if key in self.source_toggles and (provider not in self.source_toggles[key] or not self.source_toggles[key][provider].isChecked()):
                    continue
                incoming = dict(payload.get('fields', {}), **payload.get('files', {}))
                if key in incoming and has_value(incoming[key]):
                    candidates[provider] = incoming[key]
            row = self.preview.rowCount()
            self.preview.insertRow(row)
            self.preview.setItem(row, 0, QTableWidgetItem(LABELS.get(key, key)))
            self.preview.item(row, 0).setData(Qt.ItemDataRole.UserRole, key)
            is_list = isinstance(self.current.get(key), list) or any(isinstance(value, list) for value in candidates.values())
            if key in ('Developers', 'Publishers', 'Series'):
                is_list = False
            group = QButtonGroup(self)
            self.radio_groups.append(group)
            options = {}
            list_radios = {}
            default_source = next((provider for provider in candidates if key in self.image_keys), 'Current')
            default = self.review_defaults.get(key, {'source': default_source})
            max_entries = 0
            content_height = 0
            for column, provider in list(enumerate(['Current'] + review_ids, 1)):
                if provider != 'Current' and provider not in candidates:
                    self.preview.setItem(row, column, QTableWidgetItem('No value downloaded'))
                    continue
                value = self.current.get(key) if provider == 'Current' else candidates[provider]
                widget = QWidget()
                layout = QVBoxLayout(widget)
                layout.setContentsMargins(6, 4, 6, 4)
                layout.setSpacing(4)
                layout.setAlignment(Qt.AlignmentFlag.AlignTop)
                if is_list:
                    radio = QRadioButton('Keep current' if provider == 'Current' else f'Use {review_providers[provider].name}')
                    group.addButton(radio)
                    list_radios[provider] = radio
                    layout.addWidget(radio)
                    entries = value if isinstance(value, list) else []
                    max_entries = max(max_entries, len(entries))
                    options[provider] = []
                    for entry in entries:
                        label = f'{entry["Name"]} — {entry["Url"]}' if isinstance(entry, dict) else str(entry)
                        checkbox = QCheckBox(label)
                        checkbox.setChecked(self.list_identity(entry) in default.get('checked', []) or
                                            (provider == default.get('source', 'Current') if 'source' in default or 'checked' not in default else False))
                        layout.addWidget(checkbox)
                        options[provider].append((checkbox, entry))
                    if not entries:
                        layout.addWidget(QLabel('(empty)'))
                    content_height = max(content_height, layout.sizeHint().height())
                    self.preview.setCellWidget(row, column, widget)
                    continue
                radio = QRadioButton('Keep current' if provider == 'Current' else f'Use {review_providers[provider].name}')
                group.addButton(radio)
                options[provider] = (radio, value)
                layout.addWidget(radio)
                if key == 'FullDescription':
                    from .rich_description import FullDescription
                    text = FullDescription(str(value or '(empty)'))
                    text.contentResized.connect(self.preview.fit_rows, Qt.ConnectionType.QueuedConnection)
                elif key == 'Description':
                    text = QLabel(str(value or '(empty)'))
                    text.setWordWrap(True)
                    text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                elif key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage'):
                    text = QLabel()
                    text.setPixmap(QPixmap(str(value or '')).scaled(180, 120, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                else:
                    text = QLabel(display(value) or '(empty)')
                    text.setWordWrap(True)
                layout.addWidget(text)
                if key not in ('Description', 'FullDescription', 'CoverImage', 'HeaderImage', 'BackgroundImage'):
                    width = max(1, self.preview.columnWidth(column) - 12)
                    text_height = text.heightForWidth(width) if text.hasHeightForWidth() else text.sizeHint().height()
                    text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                    content_height = max(content_height, radio.sizeHint().height() + text_height)
                self.preview.setCellWidget(row, column, widget)
            if is_list:
                list_radios.get(default.get('source', 'Current'), list_radios['Current']).setChecked(True)
                for provider, radio in list_radios.items():
                    radio.clicked.connect(lambda checked, provider=provider, options=options:
                                          [checkbox.setChecked(side == provider)
                                           for side, entries in options.items() for checkbox, _ in entries])
                self.choices[key] = {'kind': 'multi_list', 'options': options, 'radios': list_radios}
                height = max(28, content_height)
            else:
                preferred = default.get('source', 'Current')
                options.get(preferred, options['Current'])[0].setChecked(True)
                self.choices[key] = {'kind': 'multi', 'options': options}
                height = 200 if key == 'Description' else 170 if key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage') else max(28, content_height)
            self.preview.setRowHeight(row, height)
        self.preview.fit_cell_contents = True
        self.preview.fit_rows()
        if self.image_tabs is not None:
            self.update_image_tab(self.image_tabs.currentIndex())
        self.busy(False, '\n'.join(warnings) or 'Nothing is applied until you choose Apply. Save the editor to commit changes.')

    def show_preview(self, payload):
        if self.closed:
            return
        self.payload = payload
        self.set_step(2)
        if self.results.currentItem():
            self.results.currentItem().setText(f'{payload["name"]}  ·  {payload["id"]}')
        self.heading.setText(f'{payload["name"]} · {payload.get('provider', self.provider)} game {payload["id"]}. Select fields to apply to the editor; Save commits them to your library.')
        self.preview.setRowCount(0)
        self.auto_fields = {}
        self.choices = {}
        self.radio_groups = []
        values = dict(payload['fields'], **payload.get('files', {}))
        for key in FIELD_ORDER:
            if key not in values or (self.selected_fields is not None and key not in self.selected_fields):
                continue
            value = values[key]
            old = self.current.get(key)
            if not has_value(old):
                self.auto_fields[key] = value
                continue
            if equivalent(old, value):
                continue
            if key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage'):
                try:
                    if filecmp.cmp(str(old), str(value), shallow=False):
                        continue
                except OSError:
                    pass
            row = self.preview.rowCount()
            self.preview.insertRow(row)
            field = QTableWidgetItem(LABELS.get(key, key))
            field.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            field.setData(Qt.ItemDataRole.UserRole, key)
            self.preview.setItem(row, 0, field)
            if isinstance(value, list):
                choice = {'kind': 'list', 'current': [], 'new': [], 'value': value}
                for column, side, entries in [(1, 'current', old), (2, 'new', value)]:
                    widget = QWidget()
                    layout = QVBoxLayout(widget)
                    layout.setContentsMargins(6, 6, 6, 6)
                    for entry in entries:
                        text = f'{entry["Name"]} — {entry["Url"]}' if isinstance(entry, dict) else str(entry)
                        checkbox = QCheckBox(text)
                        checkbox.setToolTip(text)
                        checkbox.setChecked(side == 'new' or key == 'Links')
                        layout.addWidget(checkbox)
                        choice[side].append((checkbox, entry))
                    self.preview.setCellWidget(row, column, widget)
                self.preview.setRowHeight(row, max(50, max(len(old), len(value)) * 28 + 12))
            else:
                group = QButtonGroup(self)
                self.radio_groups.append(group)
                choice = {'kind': 'scalar', 'value': value}
                for column, side, entry in [(1, 'current', old), (2, 'new', value)]:
                    widget = QWidget()
                    layout = QVBoxLayout(widget)
                    layout.setContentsMargins(6, 6, 6, 6)
                    radio = QRadioButton('Keep current' if side == 'current' else 'Use downloaded')
                    group.addButton(radio)
                    radio.setChecked(side == 'new')
                    choice[side] = radio
                    layout.addWidget(radio)
                    if key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage'):
                        image = QLabel()
                        image.setPixmap(QPixmap(str(entry)).scaled(180, 120, Qt.AspectRatioMode.KeepAspectRatio,
                                                                 Qt.TransformationMode.SmoothTransformation))
                        layout.addWidget(image)
                    elif key == 'FullDescription':
                        from .rich_description import FullDescription
                        text = FullDescription(str(entry or '(empty)'))
                        layout.addWidget(text)
                    elif key == 'Description':
                        text = CellTextBrowser()
                        text.setObjectName('description')
                        text.setOpenExternalLinks(True)
                        text.setHtml(str(entry))
                        layout.addWidget(text)
                    else:
                        text = QLabel(display(entry))
                        text.setWordWrap(True)
                        text.setToolTip(display(entry))
                        layout.addWidget(text)
                    self.preview.setCellWidget(row, column, widget)
                self.preview.setRowHeight(row, 170 if key in ('Icon', 'CoverImage', 'HeaderImage', 'BackgroundImage') else 190 if key == 'Description' else 78)
            self.choices[key] = choice
        warnings = '\n'.join(payload.get('warnings', []))
        self.busy(False, warnings or 'Choose current or downloaded values. Missing fields will be filled automatically.')
        if not self.choices and self.auto_fields:
            self.apply()
        elif not self.choices:
            self.status.setText(warnings or 'No metadata changes found. Go Back to select other fields or a different game.')
            self.apply_button.setEnabled(False)

    def apply(self):
        if not self.payload:
            return
        updated = dict(self.auto_fields)
        for key, choice in self.choices.items():
            if choice['kind'] == 'multi_list':
                chosen = [value for entries in choice['options'].values() for checkbox, value in entries if checkbox.isChecked()]
                if key == 'Links':
                    from .metadata import merge_links
                    value = merge_links([], chosen)
                else:
                    value = list({self.list_identity(entry): entry for entry in chosen}.values())
                if not equivalent(self.current.get(key) or [], value):
                    updated[key] = value
            elif choice['kind'] == 'multi':
                for provider, (radio, value) in choice['options'].items():
                    if radio.isChecked() and provider != 'Current':
                        updated[key] = ', '.join(value) if key in ('Developers', 'Publishers', 'Series') and isinstance(value, list) else value
            elif choice['kind'] == 'scalar':
                if choice['new'].isChecked():
                    updated[key] = choice['value']
            else:
                chosen = [value for side in ('current', 'new') for checkbox, value in choice[side] if checkbox.isChecked()]
                if key == 'Links':
                    from .metadata import merge_links
                    updated[key] = merge_links([], chosen)
                else:
                    deduplicated = {}
                    for value in chosen:
                        deduplicated.setdefault(str(value).strip().casefold(), value)
                    updated[key] = list(deduplicated.values())
        self.prepared(updated)

    def prepared(self, updated):
        if self.closed:
            return
        self.applied = updated
        if self.metadata_ids != (self.current.get('MetadataIds') or {}):
            self.applied['MetadataIds'] = dict(self.metadata_ids)
        self.accept()
