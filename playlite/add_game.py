from .lifecycle import choose_file
"""Library entries and Lutris add-game method selection."""
import uuid
from pathlib import Path
from PyQt6.QtWidgets import QDialog, QLabel, QPushButton, QVBoxLayout
from .editor import MetadataEditor
ROOT = Path.home() / 'Games'


def notify_game_added(window, editor):
    """Run independent follow-up hooks after the library entry is committed."""
    import logging
    for plugin in editor.generic_plugins:
        try:
            plugin.after_game_added(window, editor.result_game, editor)
        except Exception as error:
            logging.exception('Plugin %s failed after adding a game', plugin.id)
            window.statusBar().showMessage(f'Game added; {plugin.name} needs attention: {error}', 15000)


class AddGameMethods(QDialog):
    def __init__(self, methods, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Add Game')
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

    def setVisible(self, visible):
        if visible and not self.isVisible():
            # Resolve themed controls and shared margins before the first frame.
            # The play chooser changes its prompt after construction.
            from .ui_layout import configure_dialog
            self.ensurePolished()
            configure_dialog(self)
            self.layout().activate()
            size = self.sizeHint()
            self.resize(max(380, size.width()), size.height())
        super().setVisible(visible)

    def choose(self, callback):
        self.selected_method = callback
        self.accept()


class AddGameEditor(MetadataEditor):
    def __init__(self, executable, data, parent=None, game=None, installation_method=None):
        selected = Path(executable).expanduser().resolve(strict=True) if executable else None
        if selected is not None and not selected.is_file():
            raise ValueError('Select a game executable.')
        from .providers import discover_plugins, installation_methods
        plugins = discover_plugins()
        self.installation_plugins = installation_methods(plugins)
        if not self.installation_plugins:
            raise ValueError('Adding games requires the Lutris integration. It is currently unavailable.')
        if installation_method is None:
            from PyQt6.QtCore import QSettings
            settings = QSettings(str(data / 'ui.ini'), QSettings.Format.IniFormat)
            installation_method = settings.value('installation/defaultMethod', '', type=str)
            if installation_method not in self.installation_plugins:
                installation_method = next(iter(self.installation_plugins))
        if installation_method not in self.installation_plugins:
            raise ValueError('This add-game method is unavailable. Games must be associated with Lutris.')
        self.installation_plugin = self.installation_plugins[installation_method]
        super().__init__(game if game is not None else {
            'Id': str(uuid.uuid4()), 'Name': selected.parent.name if selected else '',
            'InstallDirectory': str(selected.parent) if selected else '',
            'Executable': str(selected) if selected else '',
            'Platforms': [], 'IsInstalled': True}, data, parent)
        self.setWindowTitle(f'Add Game — {self.installation_plugin.name}')
        self.installation_widgets = {self.installation_plugin.id: self.installation_widget}
        self.installation_method.currentIndexChanged.connect(self.change_installation_method)
        self.generic_plugins = list(self.editor_plugins)
        self.pending_installation = None
        for plugin in list(self.generic_plugins):
            try:
                plugin.augment_add_editor(self)
            except Exception as error:
                import logging
                logging.exception('Plugin %s failed to extend the add-game editor', plugin.id)
                self.generic_plugins.remove(plugin)
                self.editor_plugins.remove(plugin)
                self.error.setText(f'{plugin.name} controls are unavailable: {error}')
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

    def save(self):
        try:
            self.pending_installation = None
            game = self.collect()
            if self.installation_plugin is not None:
                game = self.installation_plugin.collect(self.installation_widget, game)
            from types import SimpleNamespace
            context = SimpleNamespace(directory=Path(game.get('InstallDirectory') or '.').expanduser().resolve())
            for plugin in self.generic_plugins:
                plugin.prepare_add(self, game, context)
            if self.installation_plugin is not None:
                integration = self.installation_plugin.deferred_integration
                if integration:
                    from .installation_commit import PendingInstallation
                    game['GameProvider'] = integration
                    self.pending_installation = PendingInstallation(self.installation_plugin, self.installation_widget, game)
                else:
                    game = self.installation_plugin.commit(self.installation_widget, game)
            from .providers import GameProvider, discover_plugins
            providers = [plugin for plugin in discover_plugins().values() if isinstance(plugin, GameProvider)]
            from .installation_commit import set_play_actions
            set_play_actions(game, providers)
            self.result_game = game
        except Exception as error:
            self.error.setText(str(error))
            return
        self.accept()

    def persist(self, save):
        """Save a collected entry, including its pending external registration."""
        pending = self.pending_installation
        if pending is None:
            return save(self.result_game)
        from .providers import GameProvider, discover_plugins
        from .installation_commit import set_play_actions
        providers = [plugin for plugin in discover_plugins().values() if isinstance(plugin, GameProvider)]
        if not any(provider.id == pending.method.deferred_integration for provider in providers):
            raise ValueError('The launching integration is no longer available.')
        with pending.commit() as game:
            set_play_actions(game, providers)
            saved = save(game)
        self.result_game = game
        self.pending_installation = None
        return saved





def choose_game(parent):
    filename, _ = choose_file(parent, 'Add Standalone Game — select executable', str(ROOT), 'Windows executable (*.exe *.EXE)')
    return filename
