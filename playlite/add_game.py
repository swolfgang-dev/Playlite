from .lifecycle import choose_file
"""Manual library entries and add-game method selection."""
import json
import os
import sqlite3
import uuid
from pathlib import Path
from PyQt6.QtCore import QProcess, QTimer
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout
from .editor import MetadataEditor
ROOT = Path.home() / 'Games'


class AddGameMethods(QDialog):
    def __init__(self, methods, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Game')
        self.resize(380, 200)
        self.selected_method = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('Choose how to add games.'))
        self.method_buttons = []
        for title, callback in methods:
            button = QPushButton(title)
            button.clicked.connect(lambda checked=False, callback=callback: self.choose(callback))
            layout.addWidget(button)
            self.method_buttons.append(button)
        layout.addStretch()
        cancel = QPushButton('Cancel')
        cancel.clicked.connect(self.reject)
        layout.addWidget(cancel)

    def choose(self, callback):
        self.selected_method = callback
        self.accept()


class AddGameEditor(MetadataEditor):
    def __init__(self, executable, data, parent=None, game=None, installation_method=None):
        selected = Path(executable).expanduser().resolve(strict=True) if executable else None
        if selected is not None and not selected.is_file():
            raise ValueError('Select a game executable.')
        from .providers import discover_plugins, GenericPlugin, installation_methods
        plugins = discover_plugins()
        self.installation_plugins = installation_methods(plugins)
        if installation_method is None:
            from PyQt6.QtCore import QSettings
            settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
            installation_method = settings.value('installation/defaultMethod', 'Manual', type=str)
            if installation_method not in self.installation_plugins:
                installation_method = 'Manual'
        self.installation_plugin = self.installation_plugins[installation_method]
        super().__init__(game if game is not None else {
            'Id': str(uuid.uuid4()), 'Name': selected.parent.name if selected else '',
            'InstallDirectory': str(selected.parent) if selected else '',
            'Executable': str(selected) if selected else '',
            'Platforms': [], 'IsInstalled': True}, data, parent)
        self.setWindowTitle(f'Add Game — {self.installation_plugin.name}')
        self.installation_widgets = {self.installation_plugin.id: self.installation_widget}
        self.installation_method.currentIndexChanged.connect(self.change_installation_method)
        self.generic_plugins = [plugin for plugin in plugins.values() if isinstance(plugin, GenericPlugin)]
        for plugin in self.generic_plugins:
            plugin.augment_add_editor(self)
        from PyQt6.QtWidgets import QTabWidget
        self.findChild(QTabWidget).setCurrentIndex(0)

    def change_installation_method(self):
        import copy
        previous = self.installation_widget
        values = {key: field.text() for key, field in previous.fields.items()}
        game = copy.deepcopy(self.game)
        game.update({key: value for key, value in values.items() if not previous.fields[key].property('metadata_provider')})
        from .plugin_fields import collect_fields
        collect_fields(previous.fields, game, validate=False)
        self.installation_plugin = self.installation_plugins[self.installation_method.currentData()]
        self.installation_controls.removeWidget(previous)
        previous.hide()
        widget = self.installation_widgets.get(self.installation_plugin.id)
        if widget is None:
            widget = self.installation_plugin.create_editor(self, game)
            self.installation_widgets[self.installation_plugin.id] = widget
        else:
            for key, field in widget.fields.items():
                if key in values:
                    field.setText(values[key])
        for key in previous.fields:
            self.fields.pop(key, None)
        self.fields.update(widget.fields)
        self.installation_widget = widget
        self.attach_installation_header(widget)
        self.installation_controls.addWidget(widget)
        widget.show()
        self.installation_description.setText(self.installation_plugin.description)
        self.setWindowTitle(f'Add Game — {self.installation_plugin.name}')
        if self.installation_plugin.id == 'Manual':
            self.game['GameProvider'] = None

    def save(self):
        try:
            game = self.collect()
            if self.installation_plugin is not None:
                game = self.installation_plugin.collect(self.installation_widget, game)
            from types import SimpleNamespace
            context = SimpleNamespace(directory=Path(game.get('InstallDirectory') or '.').expanduser().resolve())
            for plugin in self.generic_plugins:
                plugin.prepare_add(self, game, context)
            if self.installation_plugin is not None:
                game = self.installation_plugin.commit(self.installation_widget, game)
            from .play_actions import actions_for
            from .providers import GameProvider, discover_plugins
            providers = [plugin for plugin in discover_plugins().values() if isinstance(plugin, GameProvider)]
            actions = actions_for(game, providers)
            if actions:
                game['PlayActions'] = actions
                from .plugin_fields import legacy_action_fields
                for key in legacy_action_fields(providers):
                    game.pop(key, None)
            self.result_game = game
        except (ValueError, OSError, sqlite3.Error) as error:
            self.error.setText(str(error))
            return
        self.accept()





def choose_game(parent):
    filename, _ = choose_file(parent, 'Add Standalone Game — select executable', str(ROOT), 'Windows executable (*.exe *.EXE)')
    return filename
