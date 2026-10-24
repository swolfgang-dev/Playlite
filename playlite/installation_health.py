"""Read-only checks of explicit host launch paths and launcher configurations."""
from .play_actions import actions_for


def check_action(game, action, providers, downloads=None):
    from .lutris_launch import resolve_action
    try:
        _, entry = resolve_action(action)
    except (OSError, ValueError) as error:
        return {'issues': [str(error)], 'checked': []}
    return {'issues': [], 'checked': ['Lutris entry exists: ' + entry['name'],
                                     'Lutris manages executable, runner, prefix and arguments.']}


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
