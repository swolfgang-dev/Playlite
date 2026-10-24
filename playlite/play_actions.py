"""Lutris entry selection and the play-action editor."""
import copy
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QFormLayout, QLineEdit, QFrame, QGridLayout, QMenu, QDialog, QLabel, QCheckBox, QDialogButtonBox, QToolButton,
    QLayout, QSizePolicy)
from .theme import set_style


def actions_for(game, providers):
    """Migrate legacy entry-level launch fields without changing the entry."""
    if 'PlayActions' in game:
        actions = copy.deepcopy(game['PlayActions'] or [])
    else:
        provider = next((provider for provider in providers if provider.owns(game)), None)
        identity = ('LutrisIntegration' if game.get('LutrisId') and game.get('GameProvider') in (None, 'LutrisIntegration')
                    else provider.id if provider else game.get('GameProvider'))
        name = f"Play {game.get('Name') or ''}".strip()
        actions = [dict(Name=name, Integration=identity)] if identity else []
    for action in actions:
        provider = next((p for p in providers if p.id == action.get('Integration')), None)
        if action.get('Integration') == 'LutrisIntegration':
            action.setdefault('GameId', str(game.get('LutrisId') or ''))
            continue
        action.setdefault('GameId', str(game.get(provider.action_id_field) or '') if provider else '')
        if not action.get('GameId') and provider:
            action['GameId'] = str(game.get(provider.action_id_field) or '')
        for key, legacy in [('Executable', 'Executable'), ('Prefix', 'Prefix'), ('Arguments', 'LaunchArguments')]:
            action.setdefault(key, game.get(legacy) or '')
        action.setdefault('InstallDirectory', '')
    return actions


def action_game(game, action, provider):
    result = dict(game)
    result.pop('PlayActions', None)
    result['GameProvider'] = provider.id
    if 'GameId' in action:
        result[provider.action_id_field] = action['GameId'] or game.get(provider.action_id_field)
    for key, target in [('Executable', 'Executable'), ('Prefix', 'Prefix'), ('Arguments', 'LaunchArguments')]:
        if key in action:
            result[target] = action[key]
    if action.get('InstallDirectory'):
        result['InstallDirectory'] = action['InstallDirectory']
    return result


class LutrisActionSettings(QWidget):
    def __init__(self, action, identity, parent=None, pending=None):
        super().__init__(parent)
        self.pending = pending
        self.identity = identity
        self.database = action.get('LutrisDatabase') or ''
        self.setObjectName('lutrisActionSettings')
        set_style(self, 'QWidget#lutrisActionSettings, QWidget#lutrisEntryDetails { background: transparent; border: none; }')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        self.details = QWidget()
        self.details.setObjectName('lutrisEntryDetails')
        self.details_form = QFormLayout(self.details)
        self.details_form.setContentsMargins(0, 0, 0, 0)
        self.details_form.setVerticalSpacing(8)
        self.details_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self.details_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addWidget(self.details)
        self.details_error = QLabel()
        self.details_error.setWordWrap(True)
        layout.addWidget(self.details_error)
        actions = QHBoxLayout()
        actions.setSpacing(8)
        choose = QPushButton('Change entry…')
        self.choose_button = choose
        choose.setMinimumHeight(36)
        choose.clicked.connect(self.choose_entry)
        choose.setEnabled(pending is None)
        actions.addWidget(choose)
        refresh = QPushButton('Refresh')
        refresh.setMinimumHeight(36)
        refresh.setToolTip('Reload entry details from Lutris')
        refresh.clicked.connect(self.refresh_details)
        actions.addWidget(refresh)
        actions.addStretch()
        layout.addLayout(actions)
        identity.textChanged.connect(self.refresh_details)
        self.refresh_details()

    def refresh_details(self):
        from .lutris_library import entry_details
        from .lutris_launch import resolve_action
        while self.details_form.rowCount():
            self.details_form.removeRow(0)
        self.detail_values = {}
        self.details_error.clear()
        self.details_error.hide()
        if not self.identity.text() and self.pending is None:
            self.details_error.setText('Choose a Lutris entry to view its details.')
            self.details_error.show()
            return
        try:
            if self.pending is not None:
                details = self.pending.details()
            else:
                database = self.database
                if not database:
                    installation, _ = resolve_action(dict(Integration='LutrisIntegration', GameId=self.identity.text()))
                    database = installation['database']
                details = entry_details(database, self.identity.text())
            for title, value in details:
                field = QLabel(value)
                field.setTextFormat(Qt.TextFormat.PlainText)
                field.setWordWrap(True)
                field.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                field.setToolTip(value)
                self.detail_values[title] = field
                if title == 'Entry':
                    suffix = '  ·  #' + self.identity.text() if self.identity.text() else '  ·  created on Save'
                    field.setText(value + suffix)
                self.details_form.addRow('Lutris entry' if title == 'Entry' else title, field)
        except (OSError, ValueError) as error:
            self.details_error.setText(str(error))
            self.details_error.show()
        card = self.parentWidget()
        if card is not None and hasattr(card, 'align_form_labels'):
            card.align_form_labels()

    def choose_entry(self):
        from .lutris_import import LutrisImportDialog
        from .lifecycle import run_dialog
        dialog = LutrisImportDialog([], self.database, self)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted and dialog.selected_entry:
            entry = dialog.selected_entry
            self.database = entry['database']
            self.identity.setText(entry['id'])
            self.refresh_details()

    def collect(self):
        return {'LutrisDatabase': self.database} if self.database else {}


class LaunchSettings(QWidget):
    """Default integration launch fields; integrations can supply their own editor."""
    def __init__(self, action, parent=None, directory_defaults=None, hide_prefix=False):
        super().__init__(parent)
        self.setObjectName('actionLaunchSettings')
        from .lifecycle import choose_file, choose_directory
        form = QFormLayout(self)
        form.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.fields = {}
        self.hide_prefix = hide_prefix
        advanced_rows = {}
        self.advanced_rows = []
        self.advanced_form = form
        directory_defaults = directory_defaults or {}
        for key, title in [('Executable', 'Executable'), ('Prefix', 'Wine prefix'),
                           ('Arguments', 'Arguments'), ('InstallDirectory', 'Folder override')]:
            if hide_prefix and key == 'Prefix':continue
            field = QLineEdit(str(action.get(key) or ''))
            field.setFixedHeight(40)
            self.fields[key] = field
            field.setToolTip(field.text())
            field.textChanged.connect(field.setToolTip)
            if key == 'InstallDirectory':
                field.setPlaceholderText('Use the shared installation folder')
            if key == 'Arguments':
                advanced_rows[key] = field
                form.addRow(title, field)
                continue
            row_widget = QWidget()
            row_widget.setObjectName('launchPathRow')
            set_style(row_widget, 'QWidget#launchPathRow { background: transparent; border: none; }')
            row_widget.setMinimumHeight(40)
            row = QHBoxLayout(row_widget)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(8)
            row.addWidget(field)
            browse = QPushButton('Browse…')
            browse.setFixedHeight(40)
            def select(checked=False, key=key, field=field):
                if key == 'Executable':
                    value, _ = choose_file(self, 'Select game executable', field.text() or directory_defaults.get('InstallDirectory', ''), 'All files (*)')
                else:
                    value = choose_directory(self, 'Select folder', field.text() or directory_defaults.get(key, ''))
                if value:
                    field.setText(value)
            browse.clicked.connect(select)
            row.addWidget(browse)
            if key == 'InstallDirectory': advanced_rows[key] = row_widget
            form.addRow(title, row_widget)

        advanced = QToolButton()
        self.advanced_button = advanced
        advanced.setText('Advanced launch settings')
        advanced.setFixedHeight(32)
        set_style(advanced, 'QToolButton { background: transparent; border: 0; padding: 4px 0; text-align: left; } QToolButton:hover, QToolButton:focus { color: #2196f3; }')
        advanced.setCheckable(True)
        advanced.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        # Keep the disclosure above its fields so its position stays stable.
        advanced_row, _ = form.getWidgetPosition(advanced_rows['Arguments'])
        form.insertRow(advanced_row, advanced)
        def expanded(visible):
            advanced.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
            for key in ('Arguments','InstallDirectory'):
                form.setRowVisible(advanced_rows[key], visible)
            for widget in self.advanced_rows:
                form.setRowVisible(widget, visible)
        advanced.toggled.connect(expanded)
        visible=any(self.fields[key].text() for key in ('Arguments','InstallDirectory'))
        advanced.setChecked(visible);expanded(visible)

    def add_advanced_widget(self, widget):
        self.advanced_form.addRow(widget)
        self.advanced_rows.append(widget)
        self.advanced_form.setRowVisible(widget, self.advanced_button.isChecked())

    def collect(self):
        result = {key: field.text().strip() for key, field in self.fields.items()}
        if self.hide_prefix:result['Prefix'] = ''
        for key in ('Executable', 'Prefix', 'InstallDirectory'):
            if result[key] and not Path(result[key]).is_absolute():
                raise ValueError(f'{key} must be an absolute Linux path.')
        return result


class ContributedActionSettings(QWidget):
    """Combine integration controls with optional plugin controls."""
    def __init__(self, settings, contributions, parent=None):
        super().__init__(parent)
        self.setObjectName('actionSettingsContributions')
        set_style(self, 'QWidget#actionSettingsContributions { background: transparent; border: none; }')
        self.settings = settings
        self.contributions = contributions
        self.fields = getattr(settings, 'fields', {})
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(settings)
        if hasattr(settings, 'add_advanced_widget'):
            for widget in contributions:
                if (getattr(widget, 'action_settings_position', '') == 'primary'
                        and isinstance(settings.layout(), QFormLayout)):
                    settings.layout().insertRow(0, widget)
                else:
                    settings.add_advanced_widget(widget)
        else:
            button = QToolButton(self)
            button.setText('Advanced launch settings')
            button.setCheckable(True)
            button.setFixedHeight(32)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
            layout.addWidget(button)
            primary = [widget for widget in contributions
                       if getattr(widget, 'action_settings_position', '') == 'primary']
            for widget in primary:layout.insertWidget(layout.count() - 1, widget)
            advanced = [widget for widget in contributions if widget not in primary]
            button.setVisible(bool(advanced))
            for widget in advanced:layout.addWidget(widget)
            def expanded(visible):
                button.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
                for widget in advanced:widget.setVisible(visible)
            button.toggled.connect(expanded)
            expanded(False)

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        height = self.layout().totalHeightForWidth(max(1, self.width()))
        if height >= 0:size.setHeight(max(size.height(), height))
        return size

    def collect(self):
        result = self.settings.collect()
        for widget in self.contributions:result.update(widget.collect())
        return result


class ActionCard(QFrame):
    def __init__(self, action, editor, pending_installation=None):
        super().__init__(editor)
        self.editor = editor
        self.action = copy.deepcopy(action)
        self.pending_installation = pending_installation
        self.setObjectName('playActionCard')
        set_style(self, '''
            QFrame#playActionCard { background: #1d1e20; border: 1px solid #404144; border-radius: 8px; }
            QWidget#actionIdentity, QWidget#actionLaunchSettings { background: transparent; border: none; }
            QFrame#playActionCard QLabel { background: transparent; border: none; }
        ''')
        layout = QVBoxLayout(self)
        layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        columns = QGridLayout()
        columns.setAlignment(Qt.AlignmentFlag.AlignTop)
        columns.setHorizontalSpacing(16)
        columns.setVerticalSpacing(16)
        columns.setColumnStretch(0, 1)
        columns.setColumnStretch(1, 2)
        left = QWidget()
        left.setObjectName('actionIdentity')
        form = QFormLayout(left)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(12)
        form.setHorizontalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.name = QLineEdit(action.get('Name', 'Play'))
        self.integration = QComboBox()
        self.integration.addItem('Lutris', 'LutrisIntegration')
        self.integration.hide()
        selected = action.get('Integration')
        if selected and self.integration.findData(selected) < 0:
            self.integration.addItem(f'{selected} (unavailable)', selected)
        if selected:
            self.integration.setCurrentIndex(self.integration.findData(selected))
        self.game_id = QLineEdit(str(action.get('GameId') or ''))
        if pending_installation is not None:
            self.game_id.setReadOnly(True)
            self.game_id.setPlaceholderText('Assigned on save')
        for field in (self.name,self.integration,self.game_id):field.setFixedHeight(40)
        form.addRow('Name',self.name)
        identity_row = QWidget(self)
        identity_row.setObjectName('actionIdentityRow')
        set_style(identity_row, 'QWidget#actionIdentityRow { background: transparent; border: none; }')
        identity_row.setFixedHeight(40)
        identity=QHBoxLayout(identity_row)
        identity.setContentsMargins(0, 0, 0, 0)
        identity.setSpacing(8)
        identity.addWidget(self.integration,3)
        self.game_id_label = QLabel('Game ID')
        set_style(self.game_id_label, 'QLabel { background: transparent; border: none; }')
        identity.addWidget(self.game_id_label)
        identity.addWidget(self.game_id,1)
        identity_row.hide()
        columns.addWidget(left, 0, 0, 1, 2, Qt.AlignmentFlag.AlignTop)
        self.controls = QVBoxLayout()
        self.controls.setContentsMargins(0, 0, 0, 0)
        self.controls.setAlignment(Qt.AlignmentFlag.AlignTop)
        columns.addLayout(self.controls, 1, 0, 1, 2)
        layout.addLayout(columns)
        self.settings = self.create_settings(action)
        self.controls.addWidget(self.settings)
        self.align_form_labels()
        self.integration.currentIndexChanged.connect(self.change_integration)
        buttons = QHBoxLayout()
        self.default = QCheckBox('Default action')
        set_style(self.default, 'QCheckBox { background: transparent; border: none; }')
        self.default.setToolTip('Launch this action directly with Play or a double-click. Right-click Play to choose another action.')
        self.default.setChecked(action.get('Default') is True)
        self.default.toggled.connect(lambda checked: editor.set_default(self) if checked else None)
        buttons.addWidget(self.default)
        buttons.addStretch()
        self.up = QPushButton('▲')
        self.up.setToolTip('Move action up')
        self.down = QPushButton('▼')
        self.down.setToolTip('Move action down')
        remove = QPushButton('Remove')
        self.up.setFixedSize(36, 32)
        self.down.setFixedSize(36, 32)
        for button in (self.up, self.down):
            set_style(button, 'QPushButton { padding: 0; color: #e9e9e9; } QPushButton:disabled { color: #777; }')
        remove.setFixedHeight(32)
        self.up.clicked.connect(lambda: editor.move(self, -1))
        self.down.clicked.connect(lambda: editor.move(self, 1))
        remove.clicked.connect(lambda: editor.remove(self))
        for button in (self.up, self.down, remove):
            buttons.addWidget(button)
        layout.addLayout(buttons)

    def align_form_labels(self):
        forms=self.findChildren(QFormLayout)
        labels=[form.itemAt(row,QFormLayout.ItemRole.LabelRole).widget()
                for form in forms for row in range(form.rowCount())
                if form.itemAt(row,QFormLayout.ItemRole.LabelRole) is not None]
        if labels:
            width=max(label.sizeHint().width() for label in labels)
            for label in labels:label.setFixedWidth(width)
        for form in forms:form.setHorizontalSpacing(16)

    def create_settings(self, action):
        selected = dict(action, Integration=self.integration.currentData(), GameId=self.game_id.text().strip())
        if self.integration.currentData() == 'LutrisIntegration':
            self.game_id.setReadOnly(True)
            settings = LutrisActionSettings(selected, self.game_id, self, pending=self.pending_installation)
        else:
            provider = next((p for p in self.editor.providers if p.id == self.integration.currentData()), None)
            settings = provider.create_action_editor(selected, self) if provider else LaunchSettings(selected, self)
        contributions = [widget for plugin in self.editor.action_plugins
                         if (widget := plugin.create_action_settings(selected, self)) is not None]
        return ContributedActionSettings(settings, contributions, self) if contributions else settings

    def change_integration(self):
        if self.pending_installation is not None:
            self.pending_installation = None
            self.game_id.setReadOnly(False)
            self.game_id.setPlaceholderText('')
            self.game_id.clear()
        try:
            self.action.update(self.settings.collect())
        except ValueError:
            self.action.update({key: field.text() for key, field in getattr(self.settings, 'fields', {}).items()})
        self.controls.removeWidget(self.settings)
        self.settings.deleteLater()
        self.settings = self.create_settings(self.action)
        self.controls.addWidget(self.settings)
        self.align_form_labels()

    def collect(self):
        action = dict(self.action)
        action.update(self.settings.collect())
        action.update(Name=self.name.text().strip(), Integration=self.integration.currentData(),
                      GameId=self.game_id.text().strip())
        if self.default.isChecked() or 'Default' in action:
            action['Default'] = self.default.isChecked()
        if action['Integration'] != 'LutrisIntegration':
            raise ValueError('Each play action must select a Lutris entry.')
        from .lutris_requirement import validate_lutris_association
        if self.pending_installation is None:
            validate_lutris_association({'PlayActions': [action]})
        for key in ('Executable', 'Prefix', 'Arguments', 'InstallDirectory'):
            action.pop(key, None)
        if not action['Name'] or not action['Integration']:
            raise ValueError('Each play action needs a name and an integration.')
        provider = next((p for p in self.editor.providers if p.id == action['Integration']), None)
        if provider and self.pending_installation is None:
            provider.validate_action(action)
        return action


class PlayActionsEditor(QWidget):
    def __init__(self, game, providers, parent=None):
        super().__init__(parent)
        self.game_editor = parent
        self.providers = providers
        self.game = copy.deepcopy(game)
        self.cards = []
        self.pending_removals = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        buttons = QHBoxLayout()
        add = QPushButton('Add action')
        self.add_button=add
        from .providers import discover_plugins, GenericPlugin
        self.action_plugins = [plugin for plugin in discover_plugins().values() if isinstance(plugin, GenericPlugin)]
        self.installation_methods = {}
        menu = QMenu(add)
        menu.addAction('Select existing Lutris entry…').triggered.connect(self.choose_action)
        menu.addAction('Add from executable…').triggered.connect(self.choose_executable)
        menu.addAction('Add Steam game…').triggered.connect(self.choose_steam)
        add.setMenu(menu)
        buttons.addWidget(add)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.card_layout = QVBoxLayout()
        self.card_layout.setSpacing(14)
        self.card_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addLayout(self.card_layout)
        initial_actions = actions_for(game, providers)
        self.had_actions = bool(initial_actions)
        for action in initial_actions:
            self.add(action)

    def choose_executable(self):
        from .lutris_add_dialog import choose_executable_entry
        from .lutris_add import PendingExecutable
        from .lifecycle import show_warning
        data = getattr(self.game_editor, 'data', None)
        if data is None:
            show_warning(self, 'Cannot add executable', 'The game editor has no data folder.')
            return
        database = next((card.action.get('LutrisDatabase') for card in self.cards
                         if card.action.get('LutrisDatabase')), '')
        steam_id = (self.game.get('MetadataIds') or {}).get('SteamMetadata') or self.game.get('SteamAppId') or ''
        for field in getattr(self.game_editor, 'fields', {}).values():
            if field.property('metadata_provider') == 'SteamMetadata':
                steam_id = field.text().strip()
                break
        try:
            plan = choose_executable_entry(self, data, database, steam_id=str(steam_id))
        except (OSError, ValueError) as error:
            show_warning(self, 'Cannot add executable', str(error))
            return
        if plan is not None:
            self.add(dict(Name=plan.name, Integration='LutrisIntegration', GameId='',
                          LutrisDatabase=str(plan.database)), pending_installation=PendingExecutable(plan))

    def choose_steam(self):
        from .lutris_steam_dialog import AddSteamDialog
        from .lutris_steam import PendingSteam
        from .lifecycle import run_dialog, show_warning
        database = next((card.action.get('LutrisDatabase') for card in self.cards
                         if card.action.get('LutrisDatabase')), '')
        try:
            dialog = AddSteamDialog(database, self)
        except (OSError, ValueError) as error:
            show_warning(self, 'Cannot add Steam game', str(error))
            return
        if run_dialog(dialog) == QDialog.DialogCode.Accepted and dialog.result_plan is not None:
            plan = dialog.result_plan
            self.add(dict(Name=plan.name, Integration='LutrisIntegration', GameId='',
                          LutrisDatabase=str(plan.database)), pending_installation=PendingSteam(plan))

    def choose_action(self):
        from .lutris_import import LutrisImportDialog
        from .lifecycle import run_dialog
        database = next((card.action.get('LutrisDatabase') for card in self.cards
                         if card.action.get('LutrisDatabase')), '')
        dialog = LutrisImportDialog([], database, self)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted and dialog.selected_entry:
            entry = dialog.selected_entry
            self.add(dict(Name=entry['name'], Integration='LutrisIntegration',
                          GameId=entry['id'], LutrisDatabase=entry['database']))

    def add(self, action=None, pending_installation=None):
        card = ActionCard(action or {}, self, pending_installation)
        self.cards.append(card)
        if card.default.isChecked():self.set_default(card)
        self.card_layout.addWidget(card)
        self.update_buttons()
        return card

    def remove(self, card):
        provider = next((p for p in self.providers if p.id == card.integration.currentData()), None)
        identity = card.game_id.text().strip()
        if provider and identity and getattr(provider, 'supports_entry_deletion', False):
            from .lifecycle import run_dialog
            dialog = QDialog(self)
            dialog.setWindowTitle('Remove play action')
            layout = QVBoxLayout(dialog)
            layout.addWidget(QLabel(f'Remove “{card.name.text()}”?'))
            cleanup = QCheckBox(f'Also remove its {provider.name} configuration entry')
            layout.addWidget(cleanup)
            layout.addWidget(QLabel('Changes apply when you save. Game files and Wine prefixes are kept.'))
            buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
            confirm = buttons.addButton('Remove', QDialogButtonBox.ButtonRole.AcceptRole)
            confirm.clicked.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)
            layout.addWidget(buttons)
            if run_dialog(dialog) != QDialog.DialogCode.Accepted:
                return
            if cleanup.isChecked():
                self.pending_removals.append((provider, dict(Integration=provider.id, GameId=identity)))
        self.cards.remove(card)
        self.card_layout.removeWidget(card)
        card.deleteLater()
        self.update_buttons()

    def move(self, card, offset):
        index = self.cards.index(card)
        target = index + offset
        if 0 <= target < len(self.cards):
            self.cards.pop(index)
            self.cards.insert(target, card)
            self.card_layout.removeWidget(card)
            self.card_layout.insertWidget(target, card)
            self.update_buttons()

    def set_default(self, selected):
        for card in self.cards:
            if card is not selected:card.default.setChecked(False)

    def update_buttons(self):
        for index, card in enumerate(self.cards):
            card.up.setEnabled(index > 0)
            card.down.setEnabled(index < len(self.cards) - 1)

    def save_with_removals(self, save, game=None):
        from contextlib import ExitStack
        original_actions = copy.deepcopy(game['PlayActions']) if game is not None else None
        backups = []
        removed = set()
        with ExitStack() as registrations:
            try:
                if game is not None:
                    for index, card in enumerate(self.cards):
                        if card.pending_installation is not None:
                            action = registrations.enter_context(card.pending_installation.commit_action(game['PlayActions'][index], self.providers))
                            game['PlayActions'][index] = action
                remaining = ({(action['Integration'], action.get('GameId', '')) for action in game['PlayActions']}
                             if game is not None else
                             {(card.integration.currentData(), card.game_id.text().strip()) for card in self.cards})
                for provider, action in self.pending_removals:
                    key = (provider.id, action['GameId'])
                    if key in remaining or key in removed:
                        continue
                    backups.append((provider, provider.delete_entry(dict(self.game, PlayActions=[action]))))
                    removed.add(key)
                result = save()
            except Exception:
                problems = []
                for provider, backup in reversed(backups):
                    try:
                        provider.restore_deleted_entry(backup)
                    except Exception as error:
                        problems.append(str(error))
                if game is not None:
                    game['PlayActions'] = original_actions
                if problems:
                    raise ValueError('Could not restore all launcher entries: ' + '; '.join(problems))
                raise
        if game is not None:
            self.game = copy.deepcopy(game)
            for card, action in zip(self.cards, game['PlayActions']):
                card.action = copy.deepcopy(action)
                card.pending_installation = None
                settings = card.settings.settings if isinstance(card.settings, ContributedActionSettings) else card.settings
                if isinstance(settings, LutrisActionSettings):
                    settings.pending = None
                    settings.database = action.get('LutrisDatabase') or ''
                    settings.choose_button.setEnabled(True)
                card.game_id.setText(action.get('GameId') or '')
                card.game_id.setReadOnly(True)
                card.game_id.setPlaceholderText('')
                if isinstance(settings, LutrisActionSettings):
                    settings.refresh_details()
        self.pending_removals.clear()
        return result

    def collect(self):
        return [card.collect() for card in self.cards]
