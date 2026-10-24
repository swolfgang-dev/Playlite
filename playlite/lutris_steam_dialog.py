"""Select an installed Steam game for a new Lutris entry."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
                             QComboBox, QPushButton, QListWidget, QListWidgetItem, QDialogButtonBox)
from .steam_library import installed_games
from .lutris_library import installations
from .lutris_steam import SteamPlan


class AddSteamDialog(QDialog):
    def __init__(self, database='', parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Steam game to Lutris')
        self.resize(640, 520)
        self.result_plan = None
        layout = QVBoxLayout(self)
        note = QLabel('Choose an installed Steam game. Playlite will create a Steam entry in Lutris pointing to its app ID.')
        note.setWordWrap(True)
        layout.addWidget(note)
        row = QHBoxLayout()
        row.addWidget(QLabel('Lutris'))
        self.library = QComboBox()
        for installation in installations():
            if installation['database'].is_file():
                self.library.addItem('Flatpak Lutris' if installation['flatpak'] else 'Native Lutris', str(installation['database']))
                self.library.setItemData(self.library.count()-1, str(installation['database']), Qt.ItemDataRole.ToolTipRole)
        if database:
            index = self.library.findData(str(Path(database).expanduser().resolve()))
            if index >= 0:
                self.library.setCurrentIndex(index)
        row.addWidget(self.library, 1)
        refresh = QPushButton('Refresh')
        refresh.clicked.connect(self.reload)
        row.addWidget(refresh)
        layout.addLayout(row)
        self.search = QLineEdit()
        self.search.setPlaceholderText('Search installed Steam games')
        layout.addWidget(self.search)
        self.games = QListWidget()
        layout.addWidget(self.games)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.add_button = buttons.addButton('Use selected game', QDialogButtonBox.ButtonRole.AcceptRole)
        self.add_button.clicked.connect(self.select)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.games.currentItemChanged.connect(lambda *_: self.update_selection())
        self.games.itemDoubleClicked.connect(lambda *_: self.select())
        self.search.textChanged.connect(self.filter_games)
        self.library.currentIndexChanged.connect(self.update_selection)
        self.reload()

    def reload(self):
        self.games.clear()
        self.result_plan = None
        for game in installed_games():
            item = QListWidgetItem(f"{game['name']} — {game['app_id']}")
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setToolTip(str(game['directory']))
            self.games.addItem(item)
        self.status.setText(f'{self.games.count()} installed Steam games.' if self.games.count()
                            else 'No installed Steam games found. Install a game in Steam, then refresh.')
        self.filter_games()

    def filter_games(self):
        query = self.search.text().strip().casefold()
        for index in range(self.games.count()):
            item = self.games.item(index)
            item.setHidden(query not in item.text().casefold())
        self.update_selection()

    def update_selection(self):
        item = self.games.currentItem()
        self.add_button.setEnabled(item is not None and not item.isHidden() and bool(self.library.currentData()))

    def select(self):
        item = self.games.currentItem()
        if item is None or item.isHidden() or not self.library.currentData():
            return
        game = item.data(Qt.ItemDataRole.UserRole)
        try:
            plan = SteamPlan(game['name'], game['app_id'], game['directory'], game['manifest'], Path(self.library.currentData()))
            plan.validate()
            self.result_plan = plan
        except (OSError, ValueError) as error:
            self.status.setText(str(error))
            return
        self.accept()
