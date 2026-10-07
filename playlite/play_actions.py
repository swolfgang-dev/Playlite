"""Integration-owned launch actions and their installation-page editor."""
import copy
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QPushButton,
    QFormLayout, QLineEdit, QFrame, QGridLayout, QMenu, QDialog)
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
    def __init__(self, action, parent=None, directory_defaults=None):
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
        directory_defaults = directory_defaults or {}
        for key, title in [('Executable', 'Executable'), ('Prefix', 'Wine prefix'),
                           ('Arguments', 'Arguments'), ('InstallDirectory', 'Folder override')]:
            field = QLineEdit(str(action.get(key) or ''))
            field.setFixedHeight(40)
            self.fields[key] = field
            if key == 'InstallDirectory':
                field.setPlaceholderText('Use the shared installation folder')
            if key == 'Arguments':
                form.addRow(title, field)
                continue
            row = QHBoxLayout()
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
            form.addRow(title, row)

    def collect(self):
        result = {key: field.text().strip() for key, field in self.fields.items()}
        for key in ('Executable', 'Prefix', 'InstallDirectory'):
            if result[key] and not Path(result[key]).is_absolute():
                raise ValueError(f'{key} must be an absolute Linux path.')
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
        layout.setSpacing(14)
        columns = QGridLayout()
        columns.setHorizontalSpacing(20)
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
        for title, field in [('Name', self.name), ('Integration', self.integration), ('Game ID', self.game_id)]:
            field.setFixedHeight(40)
            form.addRow(title, field)
        columns.addWidget(left, 0, 0, Qt.AlignmentFlag.AlignTop)
        self.controls = QVBoxLayout()
        self.controls.setContentsMargins(0, 0, 0, 0)
        self.controls.setAlignment(Qt.AlignmentFlag.AlignTop)
        columns.addLayout(self.controls, 0, 1)
        layout.addLayout(columns)
        self.settings = self.create_settings(action)
        self.controls.addWidget(self.settings)
        self.integration.currentIndexChanged.connect(self.change_integration)
        buttons = QHBoxLayout()
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

    def create_settings(self, action):
        provider = next((p for p in self.editor.providers if p.id == self.integration.currentData()), None)
        return provider.create_action_editor(action, self) if provider else LaunchSettings(action, self)

    def change_integration(self):
        try:
            self.action.update(self.settings.collect())
        except ValueError:
            self.action.update({key: field.text() for key, field in getattr(self.settings, 'fields', {}).items()})
        self.controls.removeWidget(self.settings)
        self.settings.deleteLater()
        self.settings = self.create_settings(self.action)
        self.controls.addWidget(self.settings)

    def collect(self):
        action = dict(self.action)
        action.update(self.settings.collect())
        action.update(Name=self.name.text().strip(), Integration=self.integration.currentData(),
                      GameId=self.game_id.text().strip())
        if not action['Name'] or not action['Integration']:
            raise ValueError('Each play action needs a name and an integration.')
        provider = next((p for p in self.editor.providers if p.id == action['Integration']), None)
        if provider:
            provider.validate_action(action)
        return action


class PlayActionsEditor(QWidget):
    def __init__(self, game, providers, parent=None):
        super().__init__(parent)
        self.providers = providers
        self.game = copy.deepcopy(game)
        self.cards = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        buttons = QHBoxLayout()
        add = QPushButton('Add action')
        self.add_button=add
        menu=QMenu(add)
        from .providers import discover_plugins,installation_methods
        self.installation_methods=installation_methods(discover_plugins())
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
        parent=self.parentWidget()
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
        self.card_layout.addWidget(card)
        self.update_buttons()
        return card

    def remove(self, card):
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

    def update_buttons(self):
        for index, card in enumerate(self.cards):
            card.up.setEnabled(index > 0)
            card.down.setEnabled(index < len(self.cards) - 1)

    def collect(self):
        return [card.collect() for card in self.cards]
