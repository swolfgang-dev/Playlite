"""Editable domain names for links displayed in the game view."""
import json
from urllib.parse import urlsplit, unquote
import unicodedata
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


def friendly_name(url, fallback, names, game_name=''):
    try:
        host = domain(url)
    except ValueError:
        return fallback
    for match, name in sorted(names, key=lambda item: len(item[0]), reverse=True):
        if host == match or host.endswith('.' + match):
            return name
    parts = urlsplit(url.strip() if '://' in url else '//' + url.strip())
    wiki_hosts = ('fandom.com', 'wikia.com', 'wiki.gg', 'wikidot.com', 'gamepedia.com')
    host_labels = host.split('.')
    path_segments = [unquote(segment).casefold() for segment in parts.path.split('/') if segment]
    if (any(host == site or host.endswith('.' + site) for site in wiki_hosts)
            or any(label in ('wiki', 'wikis') or label.endswith('wiki') for label in host_labels[:-1])
            or any(segment in ('wiki', 'wikis') for segment in path_segments)):
        return 'Wiki'
    if game_name:
        def normalized(value):
            return ''.join(character for character in unicodedata.normalize('NFKD', value).casefold()
                           if character.isalnum())
        title = normalized(game_name)
        variants = {title}
        if game_name.casefold().startswith('the '):
            variants.add(normalized(game_name[4:]))
        candidates = [normalized(unquote(part)) for part in [host, *parts.path.split('/')]]
        if any(variant and (variant == candidate or len(variant) >= 4 and variant in candidate)
               for variant in variants for candidate in candidates):
            return 'Official Website'
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
