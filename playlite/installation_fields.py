from pathlib import Path
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QHBoxLayout
from playlite.lifecycle import choose_file, choose_directory


class InstallationFields:
    """Shared path and metadata controls; not an add or launch method."""
    def create_editor(self, editor, game, field_keys=None, directory_defaults=None, extra_fields=None):
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(12)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        widget.fields = {}
        widget.field_rows = {}
        directory_defaults = dict(directory_defaults or {})
        if getattr(editor, 'data', None):
            general = QSettings(str(Path(editor.data) / 'ui.ini'), QSettings.Format.IniFormat)
            for key, setting in [('InstallDirectory', 'defaultFolder'), ('Prefix', 'defaultPrefixFolder')]:
                if not directory_defaults.get(key):
                    directory_defaults[key] = general.value('installation/' + setting, '', type=str)
        from .providers import discover_plugins
        definitions = [{'key': key, 'label': label} for key, label in [
            ('Executable', 'Executable'), ('InstallDirectory', 'Installation folder'),
            ('Prefix', 'Wine prefix'), ('LaunchArguments', 'Launch arguments')]]
        definitions += list(extra_fields or [])
        for plugin in discover_plugins().values():
            definitions += list(getattr(plugin, 'game_fields', []))
        for definition in definitions:
            key, label = definition['key'], definition['label']
            if key in widget.fields or (field_keys is not None and key not in field_keys):
                continue
            source = definition.get('metadata_provider')
            value = (game.get('MetadataIds') or {}).get(source, '') if source else game.get(key)
            field = QLineEdit(str(value or ''))
            field.setFixedHeight(40)
            field.setObjectName(key)
            widget.fields[key] = field
            editor.fields[key] = field
            field.setProperty('metadata_provider', source)
            field.setProperty('positive_id', definition.get('positive_id', False))
            if source or definition.get('positive_id'):
                field.setFixedWidth(160)
            if key in ('Executable', 'InstallDirectory', 'Prefix'):
                row = QHBoxLayout()
                row.setSpacing(8)
                row.addWidget(field)
                browse = QPushButton('Browse…')
                browse.setFixedHeight(40)
                browse.setObjectName('browse' + key)
                def select_executable():
                    filename, _ = choose_file(editor, 'Select game executable',
                                             widget.fields['Executable'].text() or widget.fields['InstallDirectory'].text() or directory_defaults.get('InstallDirectory', ''), 'All files (*)')
                    if filename:
                        widget.fields['Executable'].setText(filename)
                def select_folder(checked=False, folder_key=key):
                    folder = choose_directory(editor, 'Select Wine prefix' if folder_key == 'Prefix' else 'Select installation folder',
                                              widget.fields[folder_key].text() or directory_defaults.get(folder_key, ''))
                    if folder:
                        widget.fields[folder_key].setText(folder)
                browse.clicked.connect(select_executable if key == 'Executable' else select_folder)
                row.addWidget(browse)
                form.addRow(label, row)
                widget.field_rows[key] = row
            else:
                form.addRow(label, field)
                widget.field_rows[key] = field
        widget.default_directory = str(Path(game['Executable']).parent) if game.get('Executable') else ''
        def update_directory(value):
            folder = widget.fields['InstallDirectory']
            default = str(Path(value).parent) if value.strip() and Path(value).is_absolute() else ''
            root = directory_defaults.get('InstallDirectory', '')
            if root and default:
                try:
                    relative = Path(default).resolve().relative_to(Path(root).resolve())
                    if relative.parts:
                        default = str(Path(root).resolve() / relative.parts[0])
                except (ValueError, OSError):
                    pass
            if not folder.text() or folder.text() == widget.default_directory:
                folder.setText(default)
            widget.default_directory = default
        if 'Executable' in widget.fields and 'InstallDirectory' in widget.fields:
            widget.fields['Executable'].textChanged.connect(update_directory)
            if field_keys is None:
                update_directory(widget.fields['Executable'].text())
        return widget

    def collect(self, widget, game):
        for key, field in widget.fields.items():
            value = field.text().strip()
            if key in ('InstallDirectory', 'Executable', 'Prefix') and value and not Path(value).is_absolute():
                raise ValueError(f'{key} must be an absolute path.')
            if field.property('positive_id') and value and (not value.isascii() or not value.isdigit() or int(value) < 1):
                raise ValueError('Game ID must be a positive whole number.')
            if not field.property('metadata_provider'):
                game[key] = value
        from .plugin_fields import collect_fields
        collect_fields(widget.fields, game)
        return game

