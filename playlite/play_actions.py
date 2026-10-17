"""Integration-owned launch actions and their installation-page editor."""
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
        identity = provider.id if provider else game.get('GameProvider')
        name = f"Play {game.get('Name') or ''}".strip()
        actions = [dict(Name=name, Integration=identity)] if identity else []
    for action in actions:
        provider = next((p for p in providers if p.id == action.get('Integration')), None)
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


class LaunchSettings(QWidget):
    """Default integration launch fields; integrations can supply their own editor."""
    def __init__(self, action, parent=None, directory_defaults=None, hide_prefix=False):
        super().__init__(parent)
        self.setObjectName('actionLaunchSettings')
        from .lifecycle import choose_file, choose_directory
        form = QFormLayout(self)
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
        form.addRow(advanced)
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
            for widget in contributions:layout.addWidget(widget)
            def expanded(visible):
                button.setArrowType(Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow)
                for widget in contributions:widget.setVisible(visible)
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
    def __init__(self, action, editor):
        super().__init__(editor)
        self.editor = editor
        self.action = copy.deepcopy(action)
        self.setObjectName('playActionCard')
        set_style(self, '''
            QFrame#playActionCard { background: #1d1e20; border: 1px solid #404144; border-radius: 8px; }
            QWidget#actionIdentity, QWidget#actionLaunchSettings { background: transparent; border: none; }
            QFrame#playActionCard QLabel { background: transparent; border: none; }
        ''')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)
        columns = QGridLayout()
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
        for provider in editor.providers:
            self.integration.addItem(provider.name, provider.id)
        selected = action.get('Integration')
        if selected and self.integration.findData(selected) < 0:
            self.integration.addItem(f'{selected} (unavailable)', selected)
        if selected:
            self.integration.setCurrentIndex(self.integration.findData(selected))
        self.game_id = QLineEdit(str(action.get('GameId') or ''))
        for field in (self.name,self.integration,self.game_id):field.setFixedHeight(40)
        form.addRow('Name',self.name)
        identity_row = QWidget()
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
        form.addRow('Integration',identity_row)
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
        self.default = QCheckBox('Default play action')
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
        manual = self.integration.currentData() == 'Manual'
        self.game_id.setVisible(not manual)
        self.game_id_label.setVisible(not manual)
        provider = next((p for p in self.editor.providers if p.id == self.integration.currentData()), None)
        settings = provider.create_action_editor(action, self) if provider else LaunchSettings(action, self)
        selected = dict(action, Integration=self.integration.currentData())
        contributions = [widget for plugin in self.editor.action_plugins
                         if (widget := plugin.create_action_settings(selected, self)) is not None]
        return ContributedActionSettings(settings, contributions, self) if contributions else settings

    def change_integration(self):
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
        if action['Integration'] == 'Manual':action['GameId'] = ''
        if not action['Name'] or not action['Integration']:
            raise ValueError('Each play action needs a name and an integration.')
        provider = next((p for p in self.editor.providers if p.id == action['Integration']), None)
        if provider:
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
        menu=QMenu(add)
        from .providers import discover_plugins,installation_methods
        from .providers import GenericPlugin
        plugins=discover_plugins()
        self.action_plugins=[plugin for plugin in plugins.values() if isinstance(plugin, GenericPlugin)]
        self.installation_methods=installation_methods(plugins)
        for method in self.installation_methods.values():
            item=menu.addAction(method.name)
            item.triggered.connect(lambda checked=False,method=method:self.setup_action(method.id))
        add.setMenu(menu)
        buttons.addWidget(add)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.card_layout = QVBoxLayout()
        self.card_layout.setSpacing(14)
        layout.addLayout(self.card_layout)
        initial_actions = actions_for(game, providers)
        self.had_actions = bool(initial_actions)
        for action in initial_actions:
            self.add(action)

    def setup_action(self,method):
        from .action_setup import ActionSetupDialog
        from .lifecycle import run_dialog,show_warning
        parent=self.game_editor
        data=getattr(parent,'data',None)
        if data is None:
            show_warning(self,'Cannot add action','The game editor has no data folder.');return
        seed=copy.deepcopy(self.game)
        folder=getattr(parent,'fields',{}).get('InstallDirectory')
        if folder is not None:seed['InstallDirectory']=folder.text().strip()
        dialog=ActionSetupDialog(seed,data,self.providers,method,self)
        if run_dialog(dialog)==QDialog.DialogCode.Accepted:self.add(dialog.result_action)

    def add(self, action=None):
        card = ActionCard(action or {}, self)
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

    def save_with_removals(self, save):
        remaining = {(card.integration.currentData(), card.game_id.text().strip()) for card in self.cards}
        backups = []
        removed = set()
        try:
            for provider, action in self.pending_removals:
                key = (provider.id, action['GameId'])
                if key in remaining or key in removed:
                    continue
                backups.append((provider, provider.delete_entry(dict(self.game, PlayActions=[action]))))
                removed.add(key)
            result = save()
        except Exception:
            for provider, backup in reversed(backups):
                provider.restore_deleted_entry(backup)
            raise
        self.pending_removals.clear()
        return result

    def collect(self):
        return [card.collect() for card in self.cards]
