from .theme import set_style
from .lifecycle import choose_file
"""Metadata editing for Playlite's local library."""
from .lifecycle import run_dialog
import copy
from datetime import datetime
from pathlib import Path
import shutil
import uuid

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QImageReader
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QTabWidget, QTableWidget, QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget,
    QHeaderView, QAbstractItemView, QGridLayout, QComboBox,
)

from .metadata_dialog import MetadataDownloader
from .editor_fields import ListField, LinksField, CompletionField
from .artwork import repair_artwork

LIST_FIELDS = [('Platforms', 'Platforms'), ('Genres', 'Genres'), ('Features', 'Features'),
               ('Tags', 'Tags'), ('Categories', 'Categories'), ('CompletionStatus', 'Completion status'),
               ('AgeRatings', 'Age ratings'), ('Regions', 'Regions')]
TEXT_FIELDS = [('Name', 'Name'), ('SortingName', 'Sorting name'), ('Source', 'Source'),
               ('Version', 'Version'), ('Developers', 'Developers'), ('Publishers', 'Publishers'), ('Series', 'Series'),
               ('ReleaseDate', 'Release date (YYYY-MM-DD)')]
NUMBERS = [('CommunityScore', 'Community score (0–100)'), ('CriticScore', 'Critic score (0–100)'),
           ('UserScore', 'User score (0–100)'), ('Playtime', 'Playtime (seconds)'),
           ('PlayCount', 'Play count'), ('InstallSize', 'Installation size (bytes)')]


class MetadataEditor(QDialog):
    def __init__(self, game, data, parent=None):
        super().__init__(parent)
        self.game = repair_artwork(game, data)
        if 'HeaderImage' not in self.game:
            self.game['HeaderImage'] = self.game.get('BackgroundImage')
            self.game['BackgroundImage'] = None
        game = self.game
        self.data = data
        self.result_game = None
        self.fields = {}
        self.media = {}
        self.flags = {}
        self.download_caches = []
        self.setWindowTitle(f'Edit — {game["Name"]}')
        available = self.screen().availableGeometry()
        self.resize(min(1000, available.width() - 60), min(720, available.height() - 80))
        set_style(self, '''
            QLineEdit, QPlainTextEdit, QTextEdit, QTableWidget {
                background: #2c2d2f; color: #e9e9e9;
                border: 1px solid #404144; border-radius: 6px; padding: 8px;
                selection-background-color: #48566c;
            }
            QLineEdit:focus, QPlainTextEdit:focus, QTextEdit:focus, QTableWidget:focus {
                border: 1px solid #879bb7;
            }
            QPushButton#compact { padding: 0; min-height: 36px; }
            QHeaderView::section {
                background: #2c2d2f; color: #e9e9e9;
                border: 0; padding: 8px; text-align: left;
            }
        ''')
        layout = QVBoxLayout(self)
        tabs = QTabWidget()
        layout.addWidget(tabs)

        def page(title):
            area = QScrollArea()
            area.setWidgetResizable(True)
            widget = QWidget()
            form = QFormLayout(widget)
            form.setContentsMargins(20, 20, 20, 20)
            form.setVerticalSpacing(12)
            form.setHorizontalSpacing(20)
            form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
            form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            area.setWidget(widget)
            tabs.addTab(area, title)
            return form

        general = page('Metadata')
        general.setHorizontalSpacing(12)
        metadata_label_groups = [[], []]
        def align_full_width_label(form, title, field):
            label = QLabel(title)
            metadata_label_groups[0].append(label)
            row_widget = QWidget()
            row_form = QFormLayout(row_widget)
            row_form.setContentsMargins(0, 0, 0, 0)
            row_form.setHorizontalSpacing(12)
            row_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            row_form.addRow(label, field)
            general.addRow(row_widget)
        download = QPushButton('Download metadata…')
        download.clicked.connect(self.download_metadata)

        def section(title):
            heading = QLabel(title)
            set_style(heading, 'font-weight: bold; font-size: 15px; padding-top: 14px;')
            general.addRow(heading)

        def columns():
            widget = QWidget()
            row = QHBoxLayout(widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(28)
            forms = []
            for index in range(2):
                column = QWidget()
                form = QFormLayout(column)
                form.setContentsMargins(0, 0, 0, 0)
                form.setHorizontalSpacing(12)
                form.setVerticalSpacing(10)
                form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
                row.addWidget(column, 1)
                forms.append(form)
                metadata_label_groups[index].append(form)
            general.addRow(widget)
            return forms

        def text_field(form, key, title):
            value = game.get(key)
            value = '' if value is None else value
            if key == 'ReleaseDate' and isinstance(value, dict):
                value = value.get('ReleaseDate', '')
            if isinstance(value, list):
                value = ', '.join(value)
            field = QLineEdit(str(value))
            field.setFixedHeight(40)
            field.setObjectName(key)
            self.fields[key] = field
            if key == 'ReleaseDate':
                field.setPlaceholderText('YYYY-MM-DD')
            if key in ('Added', 'LastActivity'):
                field.setPlaceholderText('YYYY-MM-DD or ISO date and time')
            if key.endswith('Score'):
                field.setPlaceholderText('0–100')
            form.addRow(title, field)

        def list_field(form, key, title):
            values = game.get(key) or []
            field = ListField(values, title)
            field.setObjectName(key)
            self.fields[key] = field
            form.addRow(title, field)

        section('General')
        left, right = columns()
        for key, title in [('Name', 'Name'), ('SortingName', 'Sorting name')]:
            text_field(left, key, title)
        for key, title in [('Platforms', 'Platform'), ('Genres', 'Genres'), ('Developers', 'Developers'),
                           ('Publishers', 'Publishers'), ('Categories', 'Categories'), ('Features', 'Features'), ('Tags', 'Tags')]:
            (text_field if key in ('Developers', 'Publishers') else list_field)(left, key, title)
        text_field(right, 'ReleaseDate', 'Release date')
        for key, title in [('Series', 'Series'), ('AgeRatings', 'Age rating'), ('Regions', 'Region')]:
            (text_field if key == 'Series' else list_field)(right, key, title)
        for key, title in [('Source', 'Source'), ('CompletionStatus', 'Completion status'),
                           ('UserScore', 'User score'), ('CriticScore', 'Critic score'), ('CommunityScore', 'Community score')]:
            if key == 'CompletionStatus':
                value = game.get(key) or []
                field = CompletionField(value if isinstance(value, list) else [str(value)])
                self.fields[key] = field
                right.addRow(title, field)
            else:
                text_field(right, key, title)
        self.description = QTextEdit()
        self.description.setObjectName('Description')
        self.description.setFixedHeight(200)
        self.description.setPlaceholderText('HTML or plain text')
        self.description.setPlainText(game.get('Description') or '')
        align_full_width_label(left, 'Short description', self.description)
        self.full_description = QTextEdit()
        self.full_description.setObjectName('FullDescription')
        self.full_description.setFixedHeight(200)
        self.full_description.setPlaceholderText('HTML or plain text')
        self.full_description.setPlainText(game.get('FullDescription') or '')
        align_full_width_label(left, 'Description', self.full_description)

        section('Links')
        add = QPushButton('Add link')
        add.clicked.connect(lambda: self.add_link())
        add_row = QHBoxLayout()
        add_row.setContentsMargins(0, 0, 0, 0)
        add_row.addWidget(add, 0, Qt.AlignmentFlag.AlignLeft)
        add_row.addStretch()
        general.addRow(add_row)
        self.links = LinksField()
        self.links.add_button = add
        self.links.setObjectName('Links')
        for link in game.get('Links') or []:
            self.add_link(link['Name'], link['Url'])
        general.addRow(self.links)

        section('Advanced')
        left, right = columns()
        for key, title in [('LastActivity', 'Last played'), ('Playtime', 'Time played (seconds)'),
                           ('PlayCount', 'Play count'), ('Version', 'Version')]:
            text_field(left, key, title)
        for key, title in [('Hidden', 'Hidden'), ('Favorite', 'Favorite'), ('IsInstalled', 'Installed')]:
            checkbox = QCheckBox()
            checkbox.setChecked(bool(game.get(key)))
            self.flags[key] = checkbox
            left.addRow(title, checkbox)
        text_field(right, 'Added', 'Added')
        size_row = QHBoxLayout()
        size_row.setContentsMargins(0, 0, 0, 0)
        size_row.setSpacing(8)
        size_field = QLineEdit('' if game.get('InstallSize') is None else str(game['InstallSize']))
        size_field.setFixedHeight(40)
        self.fields['InstallSize'] = size_field
        size_row.addWidget(size_field, 1)
        self.recalculate_button = QPushButton('Recalculate')
        self.recalculate_button.setFixedHeight(40)
        self.recalculate_button.clicked.connect(self.recalculate_size)
        size_row.addWidget(self.recalculate_button)
        right.addRow('Installation size (bytes)', size_row)
        self.notes = QPlainTextEdit(game.get('Notes') or '')
        self.notes.setObjectName('Notes')
        self.notes.setFixedHeight(140)
        align_full_width_label(left, 'Notes', self.notes)
        # Compute widths after every section and full-width row exists.
        for group in metadata_label_groups:
            labels = []
            for entry in group:
                if isinstance(entry, QFormLayout):
                    for row in range(entry.rowCount()):
                        item = entry.itemAt(row, QFormLayout.ItemRole.LabelRole)
                        if item is not None and item.widget() is not None:
                            labels.append(item.widget())
                else:
                    labels.append(entry)
            width = max(label.sizeHint().width() for label in labels)
            for label in labels:
                label.setFixedWidth(width)

        artwork_page = QWidget()
        artwork = QVBoxLayout(artwork_page)
        artwork.setContentsMargins(20, 20, 20, 20)
        artwork.setSpacing(12)
        tabs.addTab(artwork_page, 'Images')
        self.artwork_layout = artwork
        artwork.addWidget(QLabel('Selected images are copied into Playlite when you save.'))
        download_images = QPushButton('Download images…')
        download_images.clicked.connect(self.download_images)
        from .media import MediaCard
        cards = QWidget()
        grid = QGridLayout(cards)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        for key, title, row, column, row_span, column_span, height in [
                ('CoverImage', 'Cover', 0, 0, 2, 1, 440),
                ('Icon', 'Icon', 0, 1, 1, 1, 150),
                ('HeaderImage', 'Header', 0, 2, 1, 1, 170),
                ('BackgroundImage', 'Background', 1, 1, 1, 2, 320)]:
            panel = MediaCard(title, str(data / game[key]) if game.get(key) else '', self, height)
            self.media[key] = panel.path
            grid.addWidget(panel, row, column, row_span, column_span)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 4)
        grid.setRowStretch(0, 2)
        grid.setRowStretch(1, 3)
        artwork.addWidget(cards, 1)
        folder = QPushButton('Open metadata folder')
        def open_folder():
            from PyQt6.QtGui import QDesktopServices
            directory = self.data / 'artwork' / self.game['Id']
            directory.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(directory)))
        folder.clicked.connect(open_folder)
        folder_row = QHBoxLayout()
        folder_row.addWidget(folder, 0, Qt.AlignmentFlag.AlignLeft)
        folder_row.addStretch()
        artwork.addLayout(folder_row)

        installation = page('Installation')
        self.installation_form = installation
        if getattr(self, 'installation_plugin', None) is not None:
            self.installation_method = QComboBox()
            for method in self.installation_plugins.values():
                self.installation_method.addItem(method.name, method.id)
            self.installation_method.setCurrentIndex(self.installation_method.findData(self.installation_plugin.id))
            self.installation_method.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
            self.installation_method.setFixedHeight(40)
            self.installation_header_label = QLabel('Installation Method')
            self.installation_description = QLabel(self.installation_plugin.description)
            self.installation_description.setWordWrap(True)
            container = QWidget()
            self.installation_controls = QVBoxLayout(container)
            self.installation_controls.setContentsMargins(0, 0, 0, 0)
            self.installation_widget = self.installation_plugin.create_editor(self, game)
            self.attach_installation_header(self.installation_widget)
            self.installation_controls.addWidget(self.installation_widget)
            installation.addRow(container)
        else:
            from .providers import discover_plugins, GameProvider
            providers = [plugin for plugin in discover_plugins().values() if isinstance(plugin, GameProvider)]
            from .play_actions import PlayActionsEditor
            self.play_actions = PlayActionsEditor(game, providers, self)
            from .manual_installation import ManualInstallation
            self.installation_widget = ManualInstallation().create_editor(
                self, game, field_keys={'InstallDirectory'})
            installation.addRow(self.installation_widget)
            installation.addRow(QLabel('Play actions'))
            installation.addRow(self.play_actions)
            explanation = QLabel('Each play action has its own launch settings. The installation folder is shared unless an action overrides it. Multiple actions open a chooser when you press Play.')
            explanation.setWordWrap(True)
            set_style(explanation, 'color: #999a9d;')
            installation.addRow(explanation)
        installation.addRow(QLabel('Archive information'))
        self.archived = QCheckBox('Archived')
        self.archived.setChecked(bool(game.get('ArchivePath')))
        self.archive_path = QLineEdit(game.get('ArchivePath') or '')
        self.archive_path.setPlaceholderText('Folder containing this archived game')
        archive_row = QHBoxLayout()
        archive_row.addWidget(self.archive_path)
        archive_browse = QPushButton('Browse…')
        def choose_archive():
            from .lifecycle import choose_directory
            path = choose_directory(self, 'Archived game folder', self.archive_path.text())
            if path:
                self.archive_path.setText(path)
        archive_browse.clicked.connect(choose_archive)
        archive_row.addWidget(archive_browse)
        installation.addRow(self.archived)
        installation.addRow('Archive folder', archive_row)
        note = QLabel('This records archive information. Changing these fields does not move files. Restore returns the game to its installation folder.')
        note.setWordWrap(True)
        installation.addRow(note)
        installation_page = tabs.widget(2)
        tabs.removeTab(2)
        tabs.insertTab(0, installation_page, 'Installation')

        self.error = QLabel()
        self.error.setWordWrap(True)
        set_style(self.error, 'color: #ffaaaa;')
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        footer = QHBoxLayout()
        footer.addWidget(download)
        footer.addWidget(download_images)
        footer.addStretch()
        self.previous_tab = QPushButton('Previous')
        self.next_tab = QPushButton('Next')
        navigation_button_width = max(self.previous_tab.sizeHint().width(), self.next_tab.sizeHint().width())
        self.previous_tab.setFixedWidth(navigation_button_width)
        self.next_tab.setFixedWidth(navigation_button_width)
        self.previous_tab.clicked.connect(lambda: tabs.setCurrentIndex(tabs.currentIndex() - 1))
        self.next_tab.clicked.connect(lambda: tabs.setCurrentIndex(tabs.currentIndex() + 1))
        navigation = QWidget()
        navigation_row = QHBoxLayout(navigation)
        navigation_row.setContentsMargins(0, 0, 0, 0)
        navigation_row.addWidget(self.previous_tab)
        navigation_row.addWidget(self.next_tab)
        navigation_row.addWidget(buttons)
        navigation.setFixedWidth(navigation.sizeHint().width())
        footer.addWidget(navigation, 0, Qt.AlignmentFlag.AlignRight)
        layout.addLayout(footer)
        def update_download_buttons(index):
            download.setVisible(index == 1)
            download_images.setVisible(index == 2)
            self.previous_tab.setEnabled(index > 0)
            self.next_tab.setEnabled(index < tabs.count() - 1)
        tabs.currentChanged.connect(update_download_buttons)
        update_download_buttons(tabs.currentIndex())
        self.finished.connect(self.cleanup_downloads)
        from .providers import discover_plugins, GenericPlugin
        for plugin in discover_plugins().values():
            if isinstance(plugin, GenericPlugin):
                plugin.augment_editor(self)

    def attach_installation_header(self, widget):
        previous = getattr(self, 'installation_header_form', None)
        if previous is not None:
            previous.takeRow(self.installation_method)
            previous.takeRow(self.installation_description)
        form = widget.layout()
        form.insertRow(0, self.installation_header_label, self.installation_method)
        form.insertRow(1, self.installation_description)
        self.installation_header_form = form
        self.installation_method.ensurePolished()
        width = self.installation_method.sizeHint().width()
        import_button = getattr(widget, 'import_button', None)
        if import_button is not None:
            import_button.ensurePolished()
            width = max(width, import_button.sizeHint().width())
        self.installation_method.setFixedWidth(width)
        for key in ('LutrisId', 'SteamId'):
            field = widget.fields.get(key)
            if field is not None:
                field.setFixedWidth(width)
        if import_button is not None:
            import_button.setFixedWidth(width)

    def recalculate_size(self):
        from .installation import installation_size
        from .metadata_dialog import Task
        from PyQt6.QtCore import QThreadPool
        directory = self.fields['InstallDirectory'].text().strip()
        if not directory or not Path(directory).is_dir():
            self.error.setText('Choose an existing installation folder first.')
            return
        self.recalculate_button.setEnabled(False)
        self.error.setText('Calculating installation size…')
        self.size_task = Task(lambda: installation_size(directory))
        def complete(value):
            self.recalculate_button.setEnabled(True)
            if self.fields['InstallDirectory'].text().strip() != directory:
                self.error.setText('Installation folder changed. Recalculate for the new folder.')
                return
            self.fields['InstallSize'].setText(str(value))
            from .installation import format_size
            self.error.setText(f'Installation size: {format_size(value)}. Save to keep it.')
        def failed(error):
            self.recalculate_button.setEnabled(True)
            self.error.setText('Could not calculate installation size. Check the folder and permissions.')
        self.size_task.signals.succeeded.connect(complete)
        self.size_task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(self.size_task)

    def cleanup_downloads(self):
        # Keep downloaded files through acceptance; save_game still needs to copy them.
        if self.result() != QDialog.DialogCode.Accepted:
            for cache in self.download_caches:
                cache.cleanup()
            self.download_caches.clear()

    def download_images(self):
        from .image_dialog import ImageDownloader
        current = copy.deepcopy(self.game)
        current['Name'] = self.fields['Name'].text()
        current['Links'] = self.current_links()
        if 'SteamId' in self.fields:
            ids = dict(current.get('MetadataIds') or {})
            ids['Steam'] = self.fields['SteamId'].text().strip()
            current['MetadataIds'] = ids
        dialog = ImageDownloader(current, self, settings_path=self.data / 'ui.ini')
        if run_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.download_caches.append(dialog.cache)
            for key, path in dialog.applied.items():
                self.media[key].setText(path)

    def download_metadata(self, checked=False, mode='metadata'):
        if not self.fields['Name'].text().strip():
            directory = self.fields['InstallDirectory'].text().strip()
            if directory:
                self.fields['Name'].setText(Path(directory).name)
        current = copy.deepcopy(self.game)
        for key, field in self.fields.items():
            current[key] = field.toPlainText().splitlines() if isinstance(field, (QPlainTextEdit, ListField)) else field.text()
        if 'SteamId' in self.fields:
            ids = dict(current.get('MetadataIds') or {})
            steam_id = self.fields['SteamId'].text().strip()
            if steam_id:
                ids['Steam'] = steam_id
            else:
                ids.pop('Steam', None)
            current['MetadataIds'] = ids
        current['Description'] = self.description.toPlainText()
        current['FullDescription'] = self.full_description.toPlainText()
        current['Links'] = self.current_links()
        for key, field in self.media.items():
            current[key] = field.text()
        dialog = MetadataDownloader(current, self, settings_path=self.data / 'ui.ini', mode=mode,
                                    save_ids=self.save_metadata_ids)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted:
            self.download_caches.append(dialog.cache)
            self.apply_metadata(dialog.applied)

    def current_links(self):
        return self.links.values()

    def save_metadata_ids(self, ids):
        import json
        from .storage import atomic_json
        from .library_storage import library_lock
        with library_lock(self.data):
            path = self.data / 'library.json'
            games = json.loads(path.read_text())
            game = next((game for game in games if game['Id'] == self.game['Id']), None)
            if game is None:
                raise ValueError('Save the game to the library first.')
            game['MetadataIds'] = dict(ids)
            shutil.copy2(path, self.data / 'library.json.bak')
            atomic_json(path, games)
        self.game['MetadataIds'] = dict(ids)
        if 'SteamId' in self.fields:
            self.fields['SteamId'].setText(str(ids.get('Steam') or ''))
        parent = self.parent()
        for entry in getattr(parent, 'games', []):
            if entry['Id'] == self.game['Id']:
                entry['MetadataIds'] = dict(ids)

    def apply_metadata(self, metadata):
        for key, value in metadata.items():
            if key == 'MetadataIds':
                self.game[key] = dict(value)
                if 'SteamId' in self.fields:
                    self.fields['SteamId'].setText(str(value.get('Steam') or ''))
            elif key == 'FullDescription':
                self.full_description.setPlainText(value)
            elif key == 'Description':
                self.description.setPlainText(value)
            elif key == 'Links':
                self.links.clear()
                for link in value:
                    self.add_link(link['Name'], link['Url'])
            elif key in self.media:
                self.media[key].setText(value)
            elif key in self.fields:
                field = self.fields[key]
                if isinstance(field, (QPlainTextEdit, ListField)):
                    field.setPlainText('\n'.join(value))
                else:
                    if key == 'ReleaseDate' and isinstance(value, dict):
                        value = value['ReleaseDate']
                    field.setText(', '.join(value) if isinstance(value, list) else str(value))
        self.error.setText('Metadata applied to the editor. Save to keep these changes.')

    def add_link(self, name='', url=''):
        self.links.add(name, url)

    def choose_image(self, field):
        filename, _ = choose_file(self, 'Select artwork', '', 'Images (*.png *.jpg *.jpeg *.webp *.bmp);;All files (*)')
        if filename:
            field.setText(filename)

    def collect(self):
        result = copy.deepcopy(self.game)
        for key, _ in TEXT_FIELDS:
            result[key] = self.fields[key].text().strip()
        if not result['SortingName']:
            from .sorting_name import sorting_name
            generated = sorting_name(result['Name'])
            result['SortingName'] = generated if generated != result['Name'] else ''
        if not result['Name']:
            raise ValueError('Name is required.')
        release = result['ReleaseDate']
        if release:
            try:
                release = datetime.strptime(release, '%Y-%m-%d').date().isoformat()
            except ValueError:
                raise ValueError('Release date must be a valid YYYY-MM-DD date.')
        result['ReleaseDate'] = {'ReleaseDate': release} if release else None
        for key, title in LIST_FIELDS:
            result[key] = list(dict.fromkeys(line.strip() for line in self.fields[key].toPlainText().splitlines() if line.strip()))
        for key, checkbox in self.flags.items():
            result[key] = checkbox.isChecked()
        for key, title in NUMBERS:
            text = self.fields[key].text().strip()
            if text and (not text.isascii() or not text.isdigit()):
                raise ValueError(f'{title} must be a nonnegative whole number.')
            result[key] = int(text) if text else None
            if key.endswith('Score') and result[key] is not None and result[key] > 100:
                raise ValueError(f'{title} must be between 0 and 100.')
        for key in ('Added', 'LastActivity'):
            value = self.fields[key].text().strip()
            if value:
                try:
                    datetime.fromisoformat(value)
                except ValueError:
                    raise ValueError(f'{key} must be a valid ISO date or date and time.')
            result[key] = value or None
        for key in ('InstallDirectory', 'Executable', 'Prefix'):
            if key not in self.fields:
                continue
            value = self.fields[key].text().strip()
            if value and not Path(value).is_absolute():
                raise ValueError(f'{key} must be an absolute Linux path.')
            result[key] = value
        if self.archived.isChecked():
            archive = self.archive_path.text().strip()
            original = result.get('InstallDirectory') or ''
            if not archive or not Path(archive).is_absolute() or not original or not Path(original).is_absolute():
                raise ValueError('Archived games need absolute archive and original installation folders.')
            source, target = Path(original).resolve(), Path(archive).resolve()
            if source == target or source in target.parents or target in source.parents:
                raise ValueError('Archive and installation folders must be separate.')
            result.update(ArchivePath=archive, ArchiveOriginalDirectory=original, IsInstalled=False)
            result['Tags'] = list(dict.fromkeys((result.get('Tags') or []) + ['Archived']))
        else:
            result.pop('ArchivePath', None)
            result.pop('ArchiveOriginalDirectory', None)
            result['Tags'] = [tag for tag in result.get('Tags') or [] if tag != 'Archived']
            if self.game.get('ArchivePath'):
                result['IsInstalled'] = True
        archive_keys = ('ArchivePath', 'ArchiveOriginalDirectory')
        if any(result.get(key) != self.game.get(key) for key in archive_keys):
            result['_ArchiveEditBase'] = {key: self.game.get(key) for key in archive_keys}
        lutris = self.fields['LutrisId'].text().strip() if 'LutrisId' in self.fields else str(result.get('LutrisId') or '')
        if lutris and (not lutris.isascii() or not lutris.isdigit() or int(lutris) < 1):
            raise ValueError('Lutris game ID must be a positive whole number.')
        result['LutrisId'] = lutris or None
        if hasattr(self, 'play_actions'):
            result['PlayActions'] = self.play_actions.collect()
            # Retain the legacy field for integrations that read it on import.
            result['GameProvider'] = result['PlayActions'][0]['Integration'] if result['PlayActions'] else None
            for action in result['PlayActions']:
                if action['Integration'] == 'Lutris' and not action.get('GameId'):
                    raise ValueError('Enter a Lutris game ID for each Lutris play action.')
            if result['PlayActions'] or self.play_actions.had_actions or 'PlayActions' in self.game:
                for key in ('Executable', 'Prefix', 'LaunchArguments', 'LutrisId', 'ProviderGameId'):
                    result.pop(key, None)
        result['Description'] = self.description.toPlainText()
        result['FullDescription'] = self.full_description.toPlainText()
        result['Notes'] = self.notes.toPlainText()
        result['Links'] = []
        for row, link in enumerate(self.current_links()):
            name, url = link['Name'], link['Url']
            if not name and not url:
                continue
            parsed = QUrl(url)
            if not name or not parsed.isValid() or parsed.scheme() not in ('https', 'http') or not parsed.host():
                raise ValueError(f'Link {row + 1} needs a name and a valid HTTP or HTTPS URL.')
            result['Links'].append({'Name': name, 'Url': url})
        for key, field in self.media.items():
            filename = field.text().strip()
            if filename and not QImageReader(filename).canRead():
                raise ValueError(f'{key}: select a readable image file.')
            result[key] = filename or None
        # An editor can stay open while running detection updates play history.
        # Preserve those updates unless the user explicitly changed that field.
        library = self.data / 'library.json'
        if library.exists():
            import json
            latest = next((game for game in json.loads(library.read_text())
                           if game['Id'] == result['Id']), {})
            for key in ('Playtime', 'PlayCount', 'LastActivity'):
                if result.get(key) == self.game.get(key) and key in latest:
                    result[key] = latest[key]
        return result

    def save(self):
        try:
            self.result_game = self.collect()
        except ValueError as error:
            self.error.setText(str(error))
            return
        self.accept()


def save_game(data, games, updated):
    from .library_storage import library_lock
    with library_lock(data):
        return _save_game(data, games, updated)


def _save_game(data, games, updated):
    """Copy new artwork and atomically persist an edited game without mutating the input."""
    import json
    result = repair_artwork(updated, data)
    # Other entries may have been migrated since this window loaded them.
    if (data / 'library.json').exists():
        games = json.loads((data / 'library.json').read_text())
    games = [repair_artwork(game, data) for game in games]
    backups = {}
    obsolete = set()
    temporary = data / 'library.tmp'
    names = {'Icon': 'icon', 'HeaderImage': 'header', 'CoverImage': 'cover-art', 'BackgroundImage': 'background'}
    directory = data / 'artwork' / result['Id']
    previous = next((game for game in games if game['Id'] == result['Id']), {})
    archive_edit = result.pop('_ArchiveEditBase', None)
    if archive_edit is not None:
        current_archive = {key: previous.get(key) for key in ('ArchivePath', 'ArchiveOriginalDirectory')}
        if current_archive != archive_edit:
            raise ValueError('Archive information changed while editing. Reopen the editor before changing it.')
    if previous and archive_edit is None:
        # Archive state belongs to the archiver, not a stale editor snapshot.
        for key in ('ArchivePath', 'ArchiveOriginalDirectory'):
            if key in previous:
                result[key] = previous[key]
            else:
                result.pop(key, None)
        if previous.get('ArchivePath'):
            result['IsInstalled'] = False
            result['Tags'] = list(dict.fromkeys((result.get('Tags') or []) + ['Archived']))
    if not result.get('Added'):
        if previous.get('Added'):
            result['Added'] = previous['Added']
        elif not previous:
            result['Added'] = datetime.now().astimezone().isoformat(timespec='seconds')
    try:
        for key, name in names.items():
            value = result.get(key)
            old = previous.get(key)
            if old:
                old_path = Path(old)
                if not old_path.is_absolute():
                    old_path = data / old_path
                if old_path.parent == directory:
                    obsolete.add(old_path)
            if not value:
                continue
            source = Path(value)
            if not source.is_absolute():
                source = data / source
            target = directory / f'{name}{source.suffix.lower()}'
            directory.mkdir(parents=True, exist_ok=True)
            if source != target:
                backups[target] = target.read_bytes() if target.exists() else None
                pending = target.with_name(target.name + '.tmp')
                try:
                    shutil.copy2(source, pending)
                    pending.replace(target)
                finally:
                    pending.unlink(missing_ok=True)
                if source.parent == directory:
                    obsolete.add(source)
            result[key] = str(target.relative_to(data))
        retained = {data / result[key] for key in names if result.get(key)}
        if directory.exists():
            for path in directory.iterdir():
                if path.is_file() and (path.stem in names or any(path.stem.startswith(key + '-') for key in names) or path.stem in names.values()):
                    obsolete.add(path)
        replacement = [result if game['Id'] == result['Id'] else game for game in games]
        if not any(game['Id'] == result['Id'] for game in games):
            replacement.append(result)
        data.mkdir(parents=True, exist_ok=True)
        temporary.write_text(json.dumps(replacement, indent=2, ensure_ascii=False))
        if (data / 'library.json').exists():
            shutil.copy2(data / 'library.json', data / 'library.json.bak')
        temporary.replace(data / 'library.json')
        for path in obsolete - retained:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        return replacement
    except OSError:
        temporary.unlink(missing_ok=True)
        for path, original in backups.items():
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise
