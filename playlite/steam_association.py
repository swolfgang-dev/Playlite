"""Choose a Steam association without requiring a Steam installation or launch."""
from PyQt6.QtCore import Qt, QThreadPool
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
                             QListWidget, QListWidgetItem, QLabel, QDialogButtonBox)
from .steam_library import installed_games
from .lutris_add import normalize_steam_id
from .tasks import Task


class SteamAssociationDialog(QDialog):
    def __init__(self, query='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Choose Steam association')
        self.resize(640, 480)
        self.selected_game = None
        self.task = None
        self.remote_results = False
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.query = QLineEdit(query)
        self.query.setPlaceholderText('Steam game name or app ID')
        row.addWidget(self.query)
        self.search_button = QPushButton('Search Steam')
        self.search_button.clicked.connect(self.search)
        self.query.returnPressed.connect(self.search)
        row.addWidget(self.search_button)
        layout.addLayout(row)
        self.results = QListWidget()
        layout.addWidget(self.results)
        self.status = QLabel('Installed games are listed below. Search Steam for other games, or enter an app ID in the executable dialog.')
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.use_button = buttons.addButton('Use selected game', QDialogButtonBox.ButtonRole.AcceptRole)
        self.use_button.clicked.connect(self.select)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.results.currentItemChanged.connect(lambda *_: self.update_selection())
        self.results.itemDoubleClicked.connect(lambda *_: self.select())
        self.query.textChanged.connect(self.query_changed)
        self.populate([{'id': game['app_id'], 'name': game['name']} for game in installed_games()])

    def populate(self, games):
        self.results.clear()
        for game in games:
            try:
                identity = normalize_steam_id(game['id'])
                name = str(game['name']).strip()
                if not name:
                    continue
            except (ValueError, KeyError, TypeError):
                continue
            item = QListWidgetItem(f'{name} — {identity}')
            item.setData(Qt.ItemDataRole.UserRole, {'id': identity, 'name': name})
            self.results.addItem(item)
        self.filter_results()

    def query_changed(self):
        self.remote_results = False
        self.filter_results()

    def filter_results(self):
        query = '' if self.remote_results else self.query.text().strip().casefold()
        for index in range(self.results.count()):
            item = self.results.item(index)
            item.setHidden(query not in item.text().casefold())
        self.update_selection()

    def update_selection(self):
        item = self.results.currentItem()
        self.use_button.setEnabled(self.task is None and item is not None and not item.isHidden())

    def search(self):
        if self.task is not None:
            return
        query = self.query.text().strip()
        if not query:
            self.status.setText('Enter a Steam game name or app ID.')
            return
        from .providers import discover_providers
        provider = discover_providers().get('SteamMetadata')
        if provider is None:
            from .steam_catalogue import search_games
            search = search_games
        else:
            search = provider.search
        self.search_button.setEnabled(False)
        self.query.setEnabled(False)
        self.status.setText('Searching Steam…')
        self.task = Task(lambda: search(query))
        def finish(games=None, error=''):
            self.task = None
            self.search_button.setEnabled(True)
            self.query.setEnabled(True)
            if games is not None:
                self.remote_results = True
                self.populate(games)
                self.status.setText(f'{self.results.count()} Steam results.')
            else:
                self.status.setText(error)
            self.update_selection()
        self.task.bind(self, lambda games: finish(games), lambda error: finish(error=error))
        self.update_selection()
        QThreadPool.globalInstance().start(self.task)

    def select(self):
        item = self.results.currentItem()
        if self.task is None and item is not None and not item.isHidden():
            self.selected_game = item.data(Qt.ItemDataRole.UserRole)
            self.accept()
