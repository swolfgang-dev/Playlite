"""One shared available-plugin snapshot for the running application."""
from PyQt6.QtCore import QObject, QThreadPool, pyqtSignal
from PyQt6.QtWidgets import QApplication
from .metadata_dialog import Task
from .plugin_manager import available_plugins


class PluginCatalogueCache(QObject):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.plugins = []
        self.loaded = False
        self.loading = False
        self.error = ''
        self.task = None
        self.discard_result = False

    def refresh(self):
        if self.loading:
            return
        self.loading = True
        self.error = ''
        self.changed.emit()
        self.task = Task(available_plugins)
        self.task.signals.succeeded.connect(self.complete)
        self.task.signals.failed.connect(self.failed)
        QThreadPool.globalInstance().start(self.task)

    def invalidate(self):
        self.plugins = []
        self.loaded = False
        self.discard_result = self.loading
        self.changed.emit()

    def complete(self, plugins):
        if self.discard_result:
            self.discard_result = False
            self.loading = False
            self.refresh()
            return
        self.plugins = plugins
        self.loaded = True
        self.loading = False
        self.error = ''
        self.changed.emit()

    def failed(self, error):
        if self.discard_result:
            self.discard_result = False
            self.loading = False
            self.refresh()
            return
        self.loading = False
        self.error = str(error)
        self.changed.emit()


def catalogue_cache():
    app = QApplication.instance()
    if not hasattr(app, 'plugin_catalogue_cache'):
        app.plugin_catalogue_cache = PluginCatalogueCache(app)
    return app.plugin_catalogue_cache
