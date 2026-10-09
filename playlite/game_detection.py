"""Poll integration-owned detectors off the UI thread and publish game status."""
import copy
import logging
import time
import json
from datetime import datetime
from PyQt6.QtCore import QObject, QTimer, QThreadPool, pyqtSignal
from .providers import IntegrationPlugin
from .metadata_dialog import Task


class GameDetection(QObject):
    changed = pyqtSignal(str, str)
    recorded = pyqtSignal(str, int, int, str)
    session_finished = pyqtSignal(str)

    def __init__(self, integrations, games, parent=None, recorder=None):
        super().__init__(parent)
        self.integrations = [plugin for plugin in integrations if isinstance(plugin, IntegrationPlugin)]
        self.games = games
        self.recorder = recorder
        self.states = {}
        self.pending = {}
        self.missing = {}
        self.busy = False
        self.closed = False
        self.sessions = {}
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.poll)

    def start(self):
        self.closed = False
        self.timer.start()

    def stop(self):
        now = time.monotonic()
        for identity in list(self.sessions):
            self.checkpoint(identity, min(now, self.missing.get(identity, now)), finish=True)
        self.closed = True
        self.timer.stop()

    def checkpoint(self, identity, now, finish=False):
        session = self.sessions.get(identity)
        if session is None:
            return
        seconds = max(0, int(now - session['start']) - session['saved'])
        count = 0 if session['counted'] else 1
        stamp = datetime.now().astimezone().isoformat(timespec='seconds')
        if seconds or count or finish:
            if self.recorder is not None:
                try:
                    if self.recorder(identity, seconds, count, stamp) is False:
                        return
                except Exception:
                    logging.exception('Could not record play history for %s', identity)
                    return
            self.recorded.emit(identity, seconds, count, stamp)
            session['saved'] += seconds
            session['counted'] = True
        session['checkpoint'] = now
        if finish:
            self.sessions.pop(identity, None)

    def status(self, game_id):
        return self.states.get(game_id, 'Stopped')

    def set_status(self, game_id, state):
        if self.status(game_id) != state:
            self.states[game_id] = state
            self.changed.emit(game_id, state)

    def launching(self, game_id):
        self.pending[game_id] = time.monotonic()
        self.set_status(game_id, 'Launching')

    def launch_failed(self, game_id):
        self.pending.pop(game_id, None)
        self.set_status(game_id, 'Launch failed')

    def poll(self):
        if self.busy or self.closed or not self.integrations:
            return
        games = copy.deepcopy(self.games())
        self.busy = True
        def detect():
            result = {}
            for integration in self.integrations:
                owned = [game for game in games if integration.owns(game)]
                if not owned:
                    continue
                try:
                    result[integration.id] = (owned, set(integration.detect_running(owned)))
                except Exception:
                    logging.exception('Game detection failed for %s', integration.id)
            return result
        self.task = Task(detect)
        def complete(result):
            self.busy = False
            if not self.closed:
                self.observe(result)
        self.task.signals.succeeded.connect(complete)
        self.task.signals.failed.connect(lambda _: setattr(self, 'busy', False))
        QThreadPool.globalInstance().start(self.task)

    def observe(self, result, now=None):
        now = time.monotonic() if now is None else now
        current = {game['Id']: game for game in self.games()}
        for identity in list(self.states):
            if identity not in current or not any(plugin.owns(current[identity]) for plugin in self.integrations):
                self.checkpoint(identity, min(now, self.missing.get(identity, now)), finish=True)
                self.set_status(identity, 'Stopped')
                self.states.pop(identity, None)
                self.pending.pop(identity, None)
                self.missing.pop(identity, None)
        for provider_id, (games, running) in result.items():
            for game in games:
                identity = game['Id']
                integration = next(plugin for plugin in self.integrations if plugin.id == provider_id)
                if (identity not in current or not integration.owns(current[identity]) or
                        str(integration.detection_association_id(game)) != str(integration.detection_association_id(current[identity]))):
                    self.checkpoint(identity, min(now, self.missing.get(identity, now)), finish=True)
                    self.set_status(identity, 'Stopped')
                    self.states.pop(identity, None)
                    self.pending.pop(identity, None)
                    self.missing.pop(identity, None)
                    continue
                if identity in running:
                    if identity not in self.sessions:
                        self.sessions[identity] = dict(start=now, saved=0, counted=False, checkpoint=now)
                        self.checkpoint(identity, now)
                    elif now - self.sessions[identity]['checkpoint'] >= 30:
                        self.checkpoint(identity, now)
                    self.pending.pop(identity, None)
                    self.missing.pop(identity, None)
                    self.set_status(identity, 'Running')
                elif identity in self.pending:
                    if now - self.pending[identity] >= 60:
                        self.launch_failed(identity)
                elif self.status(identity) == 'Running':
                    missing = self.missing.setdefault(identity, now)
                    if now - missing >= 2:
                        self.checkpoint(identity, missing, finish=True)
                        self.missing.pop(identity, None)
                        self.set_status(identity, 'Stopped')
                        if identity not in self.sessions:
                            self.session_finished.emit(identity)


def record_playtime(data, games, identity, seconds, count, stamp):
    from .library_storage import library_lock
    with library_lock(data):
        return _record_playtime(data, games, identity, seconds, count, stamp)


def _record_playtime(data, games, identity, seconds, count, stamp):
    """Merge session increments into the latest library and atomically save it."""
    path = data / 'library.json'
    latest = json.loads(path.read_text()) if path.exists() else copy.deepcopy(games)
    game = next((game for game in latest if game['Id'] == identity), None)
    if game is None:
        return latest
    game['Playtime'] = max(0, int(game.get('Playtime') or 0)) + seconds
    game['PlayCount'] = max(0, int(game.get('PlayCount') or 0)) + count
    game['LastActivity'] = stamp
    data.mkdir(parents=True, exist_ok=True)
    temporary = data / 'library.playtime.tmp'
    temporary.write_text(json.dumps(latest, indent=2, ensure_ascii=False))
    temporary.replace(path)
    return latest


def clear_play_progress(data, games):
    """Reset play history across the latest complete library in one transaction."""
    from .library_storage import library_lock
    from .storage import atomic_json
    with library_lock(data):
        path = data / 'library.json'
        latest = json.loads(path.read_text()) if path.exists() else copy.deepcopy(games)
        for game in latest:
            game.update(Playtime=0, PlayCount=0, LastActivity=None)
        atomic_json(path, latest)
        return latest
