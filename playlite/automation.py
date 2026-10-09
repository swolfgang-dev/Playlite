"""User-configured host commands around Playlite-launched game sessions."""
import copy
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import threading
import time
from PyQt6.QtCore import QObject, QThreadPool, QTimer
from PyQt6.QtWidgets import QCheckBox, QLabel, QPlainTextEdit, QSpinBox
from .theme import set_style
from .metadata_dialog import Task

PHASES = [('before_launch', 'Before launch'), ('after_launch', 'After launch'), ('after_exit', 'After exit')]


def settings_for(game):
    settings = game.get('Automation') or {}
    if not isinstance(settings, dict): raise ValueError('Invalid game automation settings.')
    timeout = settings.get('timeout', 60)
    if isinstance(timeout, bool) or not isinstance(timeout, int) or not 1 <= timeout <= 3600:
        raise ValueError('Automation timeout must be between 1 and 3600 seconds.')
    enabled = settings.get('enabled', False)
    if not isinstance(enabled, bool): raise ValueError('Automation enabled must be true or false.')
    result = {'enabled': enabled, 'timeout': timeout}
    for key, _ in PHASES:
        command = settings.get(key, '')
        if not isinstance(command, str) or '\0' in command: raise ValueError('Automation commands must be text without null characters.')
        result[key] = command
    return result


def add_editor(editor, form):
    saved = settings_for(editor.game)
    form.setRowWrapPolicy(form.RowWrapPolicy.WrapLongRows)
    editor.automation_enabled = QCheckBox('Enable automation for this game')
    editor.automation_enabled.setChecked(saved['enabled']); form.addRow(editor.automation_enabled)
    hint = QLabel('Commands run on this computer using Bash. Before launch must finish successfully before the game starts. After exit runs when Playlite detects the end of a session it started. Saving does not run commands.')
    hint.setWordWrap(True); set_style(hint, 'color: #999a9d;'); form.addRow(hint)
    editor.automation_commands = {}
    for key, title in PHASES:
        command = QPlainTextEdit(saved[key]); command.setObjectName('automation_' + key)
        command.setPlaceholderText('Leave empty to skip this stage'); command.setFixedHeight(110)
        command.setEnabled(saved['enabled']); editor.automation_enabled.toggled.connect(command.setEnabled)
        editor.automation_commands[key] = command; form.addRow(title, command)
    editor.automation_timeout = QSpinBox(); editor.automation_timeout.setRange(1, 3600); editor.automation_timeout.setSuffix(' seconds')
    editor.automation_timeout.setMaximumWidth(220); editor.automation_timeout.setFixedHeight(40)
    editor.automation_timeout.setValue(saved['timeout']); editor.automation_timeout.setEnabled(saved['enabled'])
    editor.automation_enabled.toggled.connect(editor.automation_timeout.setEnabled); form.addRow('Command timeout', editor.automation_timeout)
    variables = QLabel('Available variables: $PLAYLITE_GAME_NAME, $PLAYLITE_GAME_ID, $PLAYLITE_INSTALL_DIR, $PLAYLITE_PREFIX, $PLAYLITE_ACTION_NAME. Quote variables when using them as paths. Command output appears in Background tasks. To start a companion app without waiting for it to close, append &.')
    variables.setWordWrap(True); set_style(variables, 'color: #999a9d;'); form.addRow(variables)


def collect_editor(editor, game):
    value = {'enabled': editor.automation_enabled.isChecked(), 'timeout': editor.automation_timeout.value(),
             **{key: field.toPlainText() for key, field in editor.automation_commands.items()}}
    settings_for({'Automation': value})
    if 'Automation' in game or value['enabled'] or any(value[key].strip() for key, _ in PHASES): game['Automation'] = value


def execute_command(command, game, action, timeout, cancelled):
    directory = action.get('InstallDirectory') or game.get('InstallDirectory') or ''
    prefix = action.get('Prefix') or ''
    directory = str(Path(directory).expanduser()) if directory else ''
    prefix = str(Path(prefix).expanduser()) if prefix else ''
    from .desktop import host_environment
    environment = host_environment()
    environment.update(PLAYLITE_GAME_NAME=game.get('Name', ''), PLAYLITE_GAME_ID=game['Id'],
        PLAYLITE_INSTALL_DIR=directory, PLAYLITE_PREFIX=prefix, PLAYLITE_ACTION_NAME=action.get('Name', ''))
    if directory and not Path(directory).is_dir():
        raise ValueError('Automation folder does not exist: ' + directory)
    cwd = directory or environment.get('HOME')
    if cancelled.is_set(): return {'state': 'Cancelled', 'details': 'Command cancelled before starting.'}
    with tempfile.TemporaryFile() as output:
        process = subprocess.Popen(['/bin/bash', '-c', command], cwd=cwd, env=environment,
            stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + timeout
        state = None
        while process.poll() is None:
            if cancelled.is_set() or time.monotonic() >= deadline:
                state = 'Cancelled' if cancelled.is_set() else 'Failed'
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                    process.wait()
                # The shell can exit before its children; cancel the whole group.
                try: os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError: pass
                break
            cancelled.wait(.1)
        output.seek(0); data = output.read(1024 * 1024 + 1)
        text = data[:1024 * 1024].decode('utf-8', errors='replace')
        if len(data) > 1024 * 1024: text += '\n[Output truncated after 1 MiB.]'
        if state == 'Cancelled': message = 'Command cancelled.'
        elif state == 'Failed': message = f'Command timed out after {timeout} seconds.'
        else:
            state = 'Complete' if process.returncode == 0 else 'Failed'
            message = f'Command exited with code {process.returncode}.'
        return {'state': state, 'details': message + ('\n\n' + text if text else '')}


class Automation(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window; self.pending = {}; self.tasks = {}; self.sessions = {}; self.after_launch_jobs = set(); self.waiting_exits = {}

    def busy(self, identity):
        return self.pending.get(identity)

    def run(self, game, action, phase, completed=None, continue_on_error=False):
        settings = settings_for(game)
        command = settings[phase]
        if not settings['enabled'] or not command.strip():
            if completed: completed()
            return
        game, action = copy.deepcopy(game), copy.deepcopy(action)
        title = dict(PHASES)[phase]
        event = threading.Event()
        identity = self.window.background_tasks.update(title=game['Name'] + ' — ' + title, kind='Automation',
            state='Running', summary=title + ' command is running.', cancel=event.set)
        if phase != 'after_launch':
            self.pending[game['Id']] = phase
            self.window.game_status_changed(game['Id'], self.window.game_detection.status(game['Id']))
        task = Task(lambda: execute_command(command, game, action, settings['timeout'], event))
        self.tasks[identity] = (task, event)
        def finish(result):
            self.window.background_tasks.update(identity, state=result['state'], summary=title + ': ' + result['state'].lower() + '.', details=result['details'], cancel=None)
            if phase == 'before_launch' and result['state'] == 'Failed':
                self.window.game_detection.launch_failed(game['Id'])
            if self.pending.get(game['Id']) == phase:
                self.pending.pop(game['Id'])
                self.window.game_status_changed(game['Id'], self.window.game_detection.status(game['Id']))
            if result['state'] != 'Complete': self.window.statusBar().showMessage(game['Name'] + ': ' + title + ' failed or was cancelled. See Background tasks.', 15000)
            QTimer.singleShot(0, lambda: self.tasks.pop(identity, None))
            if completed and (result['state'] == 'Complete' or continue_on_error): completed()
        task.signals.succeeded.connect(finish)
        task.signals.failed.connect(lambda error: finish({'state': 'Failed', 'details': error}))
        QThreadPool.globalInstance().start(task)

    def launched(self, game, action):
        if settings_for(game)['enabled']:
            self.sessions[game['Id']] = (copy.deepcopy(game), copy.deepcopy(action))
        settings = settings_for(game)
        if settings['enabled'] and settings['after_launch'].strip(): self.after_launch_jobs.add(game['Id'])
        def finished():
            self.after_launch_jobs.discard(game['Id'])
            waiting = self.waiting_exits.pop(game['Id'], None)
            if waiting is not None: self.exited(game['Id'], waiting)
        self.run(game, action, 'after_launch', completed=finished, continue_on_error=True)

    def exited(self, identity, completed):
        if identity in self.after_launch_jobs:
            self.waiting_exits[identity] = completed
            self.pending[identity] = 'after_exit'
            self.window.game_status_changed(identity, self.window.game_detection.status(identity))
            return
        self.pending.pop(identity, None)
        captured = self.sessions.pop(identity, None)
        if captured: self.run(*captured, 'after_exit', completed=completed, continue_on_error=True)
        else: completed()
        self.window.game_status_changed(identity, self.window.game_detection.status(identity))

    def cancel_all(self):
        for _, event in self.tasks.values(): event.set()
