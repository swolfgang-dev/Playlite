"""Core dialog for importing an existing Lutris entry."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QComboBox, QPushButton, QListWidget, QListWidgetItem,
                             QDialogButtonBox)
from .lutris_library import library_databases, read_entries, is_linked


class LutrisImportDialog(QDialog):
    def __init__(self, games, database='', parent=None):
        super().__init__(parent)
        self.games = games
        self.selected_entry = None
        self.setWindowTitle('Import from Lutris')
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        hint = QLabel('Choose an existing Lutris entry to add to Playlite. Manage its launch settings in Lutris.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        row = QHBoxLayout()
        self.database = QComboBox()
        self.database.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.database.setMinimumContentsLength(24)
        paths = library_databases()
        if database:
            saved = Path(database).expanduser().resolve()
            if saved not in paths:
                paths.insert(0, saved)
        for path in paths:
            self.database.addItem(str(path), str(path))
        if database:
            self.database.setCurrentIndex(self.database.findData(str(Path(database).expanduser().resolve())))
        row.addWidget(self.database, 1)
        browse = QPushButton('Choose library…')
        browse.clicked.connect(self.choose_database)
        row.addWidget(browse)
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.reload)
        row.addWidget(refresh)
        layout.addLayout(row)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search Lutris entries')
        layout.addWidget(self.search)
        self.entries = QListWidget()
        layout.addWidget(self.entries)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.import_button = buttons.addButton('Import selected', QDialogButtonBox.ButtonRole.AcceptRole)
        self.import_button.setEnabled(False)
        self.import_button.clicked.connect(self.select)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.search.textChanged.connect(self.filter_entries)
        self.entries.currentItemChanged.connect(lambda *_: self.update_selection())
        self.entries.itemDoubleClicked.connect(lambda *_: self.select())
        self.database.currentIndexChanged.connect(self.reload)
        self.reload()

    def choose_database(self):
        from .lifecycle import choose_file
        filename, _ = choose_file(self, 'Choose Lutris library', self.database.currentData() or '', 'Lutris database (pga.db)')
        if filename:
            filename = str(Path(filename).resolve())
            index = self.database.findData(filename)
            if index < 0:
                self.database.addItem(filename, filename)
                index = self.database.count() - 1
            self.database.setCurrentIndex(index)

    def reload(self):
        self.entries.clear()
        self.selected_entry = None
        database = self.database.currentData()
        if not database:
            self.status.setText('No Lutris library found. Open Lutris first, or choose its pga.db file.')
            self.update_selection()
            return
        try:
            entries = read_entries(database)
            linked = 0
            for entry in entries:
                if any(is_linked(game, entry) for game in self.games):
                    linked += 1
                    continue
                item = QListWidgetItem(f"{entry['name']} — {entry['id']}")
                item.setData(Qt.ItemDataRole.UserRole, entry)
                self.entries.addItem(item)
            self.status.setText(f'{self.entries.count()} entries available. {linked} already imported.')
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
        self.filter_entries()

    def filter_entries(self):
        query = self.search.text().strip().casefold()
        for index in range(self.entries.count()):
            item = self.entries.item(index)
            item.setHidden(query not in item.text().casefold())
        self.update_selection()

    def update_selection(self):
        item = self.entries.currentItem()
        self.import_button.setEnabled(item is not None and not item.isHidden())

    def select(self):
        item = self.entries.currentItem()
        if item is not None and not item.isHidden():
            self.selected_entry = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
