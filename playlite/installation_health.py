"""Read-only checks of explicit host launch paths and launcher configurations."""
from pathlib import Path
import re
import sqlite3
from .play_actions import actions_for


def check_action(game, action, providers, downloads=None):
    issues = []; checked = []
    if action.get('IsVM') or str(action.get('Environment', '')).lower() in ('vm', 'virtual'):
        return {'issues': [], 'checked': ['VM launch: host paths were not inspected.']}
    provider = next((p for p in providers if p.id == action.get('Integration')), None)
    if provider is None:
        return {'issues': ['The play action integration is unavailable.'], 'checked': []}
    config = {}
    if action.get('Integration') == 'LutrisIntegration' and (action.get('Prefix') or str(action.get('Executable', '')).lower().endswith('.exe')) and callable(getattr(provider, 'launch_configuration', None)):
        try:
            config = provider.launch_configuration(action.get('GameId')) or {}
            checked.append('Lutris configuration is readable.')
        except (OSError, ValueError, sqlite3.Error) as error:
            issues.append('Could not read the Lutris configuration: ' + str(error))
    values = config.get('game') or {}
    prefix = values.get('prefix') or action.get('Prefix') or ''
    directory = values.get('working_dir') or action.get('InstallDirectory') or game.get('InstallDirectory') or ''
    executable = values.get('exe') or action.get('Executable') or ''
    if downloads is not None and directory:
        folder = Path(directory).expanduser().resolve()
        for row in downloads.entries:
            target = Path(row.destination).expanduser().resolve()
            if row.state != 'Complete' and (folder == target or folder.is_relative_to(target)):
                issues.append('Download is not complete: ' + row.name + ' (' + row.state + ')')
    if prefix:
        path = Path(prefix).expanduser()
        if not path.is_dir(): issues.append('Wine/Proton prefix is missing: ' + str(path))
        elif (config.get('runner') == 'wine' or str(executable).lower().endswith('.exe')) and not (path / 'drive_c').is_dir():
            issues.append('Wine prefix has no drive_c directory: ' + str(path))
        else: checked.append('Prefix exists: ' + str(path))
    if directory:
        path = Path(directory).expanduser()
        if not path.is_dir(): issues.append('Installation/working folder is missing: ' + str(path))
        else: checked.append('Installation/working folder exists: ' + str(path))
    if executable:
        if re.match(r'^[A-Za-z]:[\\/]', executable):
            checked.append('Windows executable path is handled by the launcher: ' + executable)
        else:
            path = Path(executable).expanduser()
            if not path.is_absolute() and directory: path = Path(directory).expanduser() / path
            if path.is_absolute():
                if not path.is_file(): issues.append('Executable is missing: ' + str(path))
                else: checked.append('Executable exists: ' + str(path))
            else: checked.append('Executable is resolved by the launcher: ' + executable)
    if not executable and action.get('Integration') == 'SteamIntegration':
        checked.append('Steam chooses the executable; game-file integrity was not verified.')
    if not checked and not issues: checked.append('No explicit paths to inspect; launch is handled by the integration.')
    return {'issues': issues, 'checked': checked}


def inspect_games(games, providers, downloads=None):
    rows = []
    for game in games:
        actions = actions_for(game, providers)
        if not actions:
            rows.append({'game': game['Name'], 'action': '', 'issues': ['No play actions configured.'], 'checked': []})
        for action in actions:
            rows.append({'game': game['Name'], 'action': action.get('Name', ''), **check_action(game, action, providers, downloads)})
    return rows


def show_health(window, games):
    from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QVBoxLayout, QLabel, QPlainTextEdit, QApplication
    from .lifecycle import run_dialog
    rows = inspect_games(games, window.game_providers, window.download_queue)
    dialog = QDialog(window); dialog.setWindowTitle('Installation health'); dialog.resize(800, 520)
    layout = QVBoxLayout(dialog)
    count = sum(bool(row['issues']) for row in rows)
    layout.addWidget(QLabel(f'{len(rows)} play actions checked; {count} need attention. No game files were changed.'))
    text = '\n\n'.join(row['game'] + (' — ' + row['action'] if row['action'] else '') + '\n' + '\n'.join(['Issue: ' + s for s in row['issues']] + row['checked']) for row in rows)
    window.background_tasks.update(title='Installation health', kind='Installation check', state='Needs attention' if count else 'Complete', summary=f'{len(rows)} play actions checked; {count} need attention.', details=text)
    details = QPlainTextEdit(text); details.setReadOnly(True); layout.addWidget(details)
    buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); layout.addWidget(buttons)
    copy = buttons.addButton('Copy report', QDialogButtonBox.ButtonRole.ActionRole)
    copy.clicked.connect(lambda: QApplication.clipboard().setText(text)); buttons.rejected.connect(dialog.reject)
    run_dialog(dialog)
