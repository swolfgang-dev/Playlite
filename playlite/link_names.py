"""Editable domain names for links displayed in the game view."""
import json
from urllib.parse import urlsplit
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                            QTableWidget, QTableWidgetItem, QHeaderView, QDialogButtonBox)

DEFAULT_NAMES = [
    ('steampowered.com', 'Steam'), ('igdb.com', 'IGDB'), ('gog.com', 'GOG'),
    ('playstation.com', 'PlayStation Store'), ('nintendo.com', 'Nintendo'),
    ('xbox.com', 'Xbox'), ('wiki.gg', 'Wiki'), ('reddit.com', 'Reddit'),
    ('facebook.com', 'Facebook'), ('apps.apple.com', 'App Store'),
    ('wikipedia.org', 'Wikipedia'), ('play.google.com', 'Google Play'),
    ('epicgames.com', 'Epic Games Store'), ('twitch.tv', 'Twitch'),
    ('twitter.com', 'X'), ('x.com', 'X'), ('youtube.com', 'YouTube'),
    ('youtu.be', 'YouTube'), ('discord.com', 'Discord'), ('discord.gg', 'Discord'),
    ('itch.io', 'itch.io'),
]


def domain(value):
    host = urlsplit(value.strip() if '://' in value else '//' + value.strip()).hostname or ''
    return host.lower().removeprefix('www.').rstrip('.')


def load_names(settings):
    try:
        saved = json.loads(settings.value('links/friendlyNames', 'null', type=str))
        if isinstance(saved, list):
            return [(str(host), str(name)) for host, name in saved]
    except (ValueError, TypeError):
        pass
    return list(DEFAULT_NAMES)


def friendly_name(url, fallback, names):
    try:
        host = domain(url)
    except ValueError:
        return fallback
    for match, name in sorted(names, key=lambda item: len(item[0]), reverse=True):
        if host == match or host.endswith('.' + match):
            return name
    return fallback


class LinkNamesDialog(QDialog):
    def __init__(self, names, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Link names')
        self.resize(640, 500)
        self.names = list(names)
        layout = QVBoxLayout(self)
        hint = QLabel('Choose a friendly name for each website. Domains also match their subdomains.')
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Website domain', 'Friendly name'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().hide()
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        for title, callback in [('Add', self.add_row), ('Remove', self.remove_rows),
                                ('Restore defaults', lambda: self.populate(DEFAULT_NAMES))]:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, callback=callback: callback())
            actions.addWidget(button)
        actions.addStretch()
        layout.addLayout(actions)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.populate(names)

    def populate(self, names):
        self.table.setRowCount(0)
        for host, name in names:
            self.add_row(host, name)

    def add_row(self, host='', name=''):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, value in enumerate((host, name)):
            self.table.setItem(row, column, QTableWidgetItem(value))
        self.table.setCurrentCell(row, 0)

    def remove_rows(self):
        rows = {index.row() for index in self.table.selectedIndexes()}
        for row in sorted(rows, reverse=True):
            self.table.removeRow(row)

    def save(self):
        names = []
        seen = set()
        for row in range(self.table.rowCount()):
            host, name = [self.table.item(row, column).text().strip() for column in (0, 1)]
            if not host and not name:
                continue
            try:
                host = domain(host)
            except ValueError:
                host = ''
            if not host or '.' not in host or any(char.isspace() for char in host) or not name:
                self.error.setText(f'Row {row + 1}: enter a website domain and a friendly name.')
                return
            if host in seen:
                self.error.setText(f'Row {row + 1}: {host} is already listed.')
                return
            seen.add(host)
            names.append((host, name))
        self.names = names
        self.accept()
