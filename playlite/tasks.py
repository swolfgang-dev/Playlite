"""Qt background work shared by core services and plugins, without UI imports."""
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from PyQt6 import sip


class Signals(QObject):
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)


class _Callbacks(QObject):
    """Qt disconnects these slots automatically when their owning view dies."""
    def __init__(self, owner, succeeded, failed):
        super().__init__(owner)
        self.succeeded = succeeded
        self.failed = failed

    def deliver(self, callback, value):
        try:
            if callback is not None:
                callback(value)
        finally:
            self.succeeded = self.failed = None
            self.deleteLater()

    @pyqtSlot(object)
    def success(self, value):
        self.deliver(self.succeeded, value)

    @pyqtSlot(str)
    def failure(self, value):
        self.deliver(self.failed, value)


class Task(QRunnable):
    def __init__(self, function):
        super().__init__()
        self.function = function
        self.signals = Signals()

    def bind(self, owner, succeeded=None, failed=None):
        """Deliver completion callbacks only while a QObject owner exists."""
        receiver = _Callbacks(owner, succeeded, failed)
        self.signals.succeeded.connect(receiver.success)
        self.signals.failed.connect(receiver.failure)
        return self

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

