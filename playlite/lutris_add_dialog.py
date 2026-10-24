"""Review a new Lutris Wine entry before creating any files."""
from pathlib import Path
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
                             QPushButton, QHBoxLayout, QLabel, QDialogButtonBox)
from .lutris_library import installations
from .lutris_add import ExecutablePlan, installation_folder, prefix_slug, normalize_steam_id
from .lifecycle import choose_file, choose_directory, run_dialog


def defaults(data):
    settings = QSettings(str(Path(data) / 'ui.ini'), QSettings.Format.IniFormat)
    return (settings.value('installation/defaultFolder', '', type=str),
            settings.value('installation/defaultPrefixFolder', '', type=str) or str(Path(data) / 'prefixes'))


def choose_executable_entry(parent, data, database='', steam_id=''):
    root, _ = defaults(data)
    executable, _ = choose_file(parent, 'Choose Windows executable', root, 'Windows executables (*.exe *.EXE)')
    if not executable:
        return None
    dialog = AddExecutableDialog(executable, data, database, parent, steam_id=steam_id)
    return dialog.result_plan if run_dialog(dialog) == QDialog.DialogCode.Accepted else None


class AddExecutableDialog(QDialog):
    def __init__(self, executable, data, database='', parent=None, steam_id=''):
        super().__init__(parent)
        self.setWindowTitle('Add executable to Lutris')
        self.resize(700, 360)
        self.root, prefix_root = defaults(data)
        self.prefix_root = Path(prefix_root).expanduser()
        self.result_plan = None
        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setVerticalSpacing(12)
        self.name = QLineEdit()
        self.executable = QLineEdit()
        self.executable.setReadOnly(True)
        row = QHBoxLayout()
        row.addWidget(self.executable)
        browse = QPushButton('Browse…')
        browse.clicked.connect(self.browse_executable)
        row.addWidget(browse)
        self.directory = QLineEdit()
        self.directory.setReadOnly(True)
        self.prefix = QLineEdit()
        prefix_row = QHBoxLayout()
        prefix_row.addWidget(self.prefix)
        prefix_browse = QPushButton('Browse…')
        prefix_browse.clicked.connect(self.browse_prefix)
        prefix_row.addWidget(prefix_browse)
        self.library = QComboBox()
        for installation in installations():
            if installation['database'].is_file():
                self.library.addItem('Flatpak Lutris' if installation['flatpak'] else 'Native Lutris', str(installation['database']))
                self.library.setItemData(self.library.count()-1, str(installation['database']), Qt.ItemDataRole.ToolTipRole)
        if database and self.library.findData(str(Path(database).resolve())) >= 0:
            self.library.setCurrentIndex(self.library.findData(str(Path(database).resolve())))
        form.addRow('Name', self.name)
        form.addRow('Executable', row)
        form.addRow('Installation folder', self.directory)
        form.addRow('Wine prefix', prefix_row)
        form.addRow('Lutris', self.library)
        self.steam_id = QLineEdit(str(steam_id or ''))
        self.steam_id.setPlaceholderText('Optional Steam app ID')
        self.steam_id.setToolTip('Associates this Wine entry with Steam for Lutris ID allocation. Launching still uses the executable.')
        steam_row = QHBoxLayout()
        steam_row.addWidget(self.steam_id)
        steam_choose = QPushButton('Choose Steam game…')
        steam_choose.clicked.connect(self.choose_steam_game)
        steam_row.addWidget(steam_choose)
        form.addRow('Steam association', steam_row)
        layout.addLayout(form)
        note = QLabel('The entry uses Lutris’s configured Wine runner. Wine initializes the prefix when you first launch the game.')
        note.setWordWrap(True)
        layout.addWidget(note)
        self.error = QLabel()
        self.error.setWordWrap(True)
        layout.addWidget(self.error)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        add = buttons.addButton('Use this executable', QDialogButtonBox.ButtonRole.AcceptRole)
        add.clicked.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.auto_name = ''
        self.auto_prefix = ''
        self.set_executable(executable)

    def set_executable(self, executable):
        try:
            folder = installation_folder(executable, self.root)
        except (OSError, ValueError) as error:
            self.error.setText(str(error))
            return
        self.executable.setText(str(Path(executable).expanduser().resolve()))
        self.directory.setText(str(folder))
        if not self.name.text() or self.name.text() == self.auto_name:
            self.name.setText(folder.name)
        self.auto_name = folder.name
        if not self.prefix.text() or self.prefix.text() == self.auto_prefix:
            self.prefix.setText(str(self.prefix_root / prefix_slug(folder.name)))
        self.auto_prefix = str(self.prefix_root / prefix_slug(folder.name))

    def browse_executable(self):
        executable, _ = choose_file(self, 'Choose Windows executable', self.executable.text() or self.root, 'Windows executables (*.exe *.EXE)')
        if executable:
            self.set_executable(executable)

    def browse_prefix(self):
        prefix = choose_directory(self, 'Choose Wine prefix', self.prefix.text() or str(self.prefix_root))
        if prefix:
            self.prefix.setText(prefix)

    def choose_steam_game(self):
        from .steam_association import SteamAssociationDialog
        dialog = SteamAssociationDialog(self.steam_id.text().strip() or self.name.text(), self)
        if run_dialog(dialog) == QDialog.DialogCode.Accepted and dialog.selected_game:
            self.steam_id.setText(dialog.selected_game['id'])

    def save(self):
        try:
            if not self.library.currentData():
                raise ValueError('Open Lutris once to create its library, then try again.')
            steam_id = self.steam_id.text().strip()
            if steam_id:
                steam_id = normalize_steam_id(steam_id)
            plan = ExecutablePlan(self.name.text().strip(), Path(self.executable.text()),
                                  Path(self.directory.text()), Path(self.prefix.text().strip()).expanduser(),
                                  Path(self.library.currentData()), steam_id=steam_id)
            plan.validate()
            self.result_plan = plan
        except (OSError, ValueError) as error:
            self.error.setText(str(error))
            return
        self.accept()
