"""Qt background work shared by core services and plugins, without UI imports."""
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal
from PyQt6 import sip


class Signals(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def run(self):
        try:
            value = self.function()
        except Exception as error:
            self._emit('failed', str(error))
        else:
            self._emit('succeeded', value)

    def progress(self, message):
        """Report progress safely while the application's Qt objects exist."""
        self._emit('progress', message)

    def _emit(self, name, payload):
        if not sip.isdeleted(self.signals):
            try:
                getattr(self.signals, name).emit(payload)
            except RuntimeError:
                # Qt can tear down signal objects while a worker finishes on exit.
                if not sip.isdeleted(self.signals):
                    raise

