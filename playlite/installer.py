"""First-launch preferences and optional plugin setup."""
import sys
from PyQt6.QtCore import Qt, QThreadPool, QTimer, QSettings
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton, QHBoxLayout, QTabWidget, QWidget, QFormLayout, QComboBox, QCheckBox
from .metadata_dialog import Task
from .plugin_manager import available_plugins, install_plugins, installed_plugins, plugin_directory
from .plugin_lifecycle import installed_setup


class InstallerDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings if settings is not None else QSettings(str(plugin_directory().parent / 'ui.ini'), QSettings.Format.IniFormat)
        self.setWindowTitle('Get started — Playlite')
        self.resize(720, 560)
        self.busy = False
        self.tasks = set()
        layout = QVBoxLayout(self)
        note = QLabel('Choose your preferences, then set up optional plugins. You can reopen Get started from the Playlite menu at any time.')
        note.setWordWrap(True)
        layout.addWidget(note)
        location=QLabel('Installation: '+str(plugin_directory().parent))
        location.setWordWrap(True);layout.addWidget(location)
        tabs = QTabWidget()
        preferences = QWidget()
        form = QFormLayout(preferences)
        self.default_view = QComboBox()
        for label, value in [('Grid', 'grid'), ('List', 'list'), ('Compact list', 'compact'), ('Remember last', 'remember')]:
            self.default_view.addItem(label, value)
        self.default_view.setCurrentIndex(max(0, self.default_view.findData(self.settings.value('app/defaultView', 'remember'))))
        form.addRow('Default library view', self.default_view)
        self.close_to_tray = QCheckBox('Close to system tray')
        self.close_to_tray.setChecked(self.settings.value('app/closeToTray', True, type=bool))
        form.addRow(self.close_to_tray)
        self.reset_filters = QCheckBox('Reset sorting and filters on launch')
        self.reset_filters.setChecked(self.settings.value('app/resetSortingFilters', False, type=bool))
        form.addRow(self.reset_filters)
        hint = QLabel('These preferences can also be changed in Settings. Newly installed plugins become available after restarting Playlite.')
        hint.setWordWrap(True)
        form.addRow(hint)
        tabs.addTab(preferences, '1. Preferences')
        plugin_page = QWidget()
        plugin_layout = QVBoxLayout(plugin_page)
        hint = QLabel('Select plugins and click Install selected plugins. Steam Downloader opens its isolated Steam setup after installation. Configure existing plugins in Settings → Plugins.')
        hint.setWordWrap(True)
        plugin_layout.addWidget(hint)
        self.plugins = QListWidget()
        plugin_layout.addWidget(self.plugins)
        tabs.addTab(plugin_page, '2. Plugins')
        layout.addWidget(tabs)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log)
        controls = QHBoxLayout()
        self.refresh = QPushButton('Refresh plugins')
        self.refresh.clicked.connect(self.load_catalogue)
        self.install = QPushButton('Install selected plugins')
        self.install.clicked.connect(self.install_selected)
        self.install.setEnabled(False)
        self.close_button = QPushButton('Finish')
        self.close_button.clicked.connect(self.finish_setup)
        for button in (self.refresh, self.install, self.close_button): controls.addWidget(button)
        layout.addLayout(controls)
        self.catalogue_requested = False
        def show_page(index):
            if index == 1 and not self.catalogue_requested:
                self.catalogue_requested = True
                self.load_catalogue()
        tabs.currentChanged.connect(show_page)

    def finish_setup(self):
        if self.busy:
            return
        self.settings.setValue('app/defaultView', self.default_view.currentData())
        self.settings.setValue('app/closeToTray', self.close_to_tray.isChecked())
        self.settings.setValue('app/resetSortingFilters', self.reset_filters.isChecked())
        self.settings.setValue('onboarding/completed', True)
        self.settings.sync()
        self.accept()

    def start(self, function, done):
        if self.busy: return
        self.busy = True
        for button in (self.refresh, self.install, self.close_button): button.setEnabled(False)
        self.plugins.setEnabled(False)
        task = Task(lambda: function(task.signals.progress.emit))
        self.tasks.add(task)
        task.signals.progress.connect(self.log.appendPlainText)
        def finish():
            self.tasks.discard(task)
            self.busy = False
            for button in (self.refresh, self.install, self.close_button): button.setEnabled(True)
            self.plugins.setEnabled(True)
        def complete(result):
            finish()
            done(result)
        def failed(error):
            finish()
            self.log.appendPlainText(str(error))
        task.signals.succeeded.connect(complete)
        task.signals.failed.connect(failed)
        QThreadPool.globalInstance().start(task)

    def load_catalogue(self):
        def loaded(entries):
            self.plugins.clear()
            installed = {entry.get('repository', '').casefold() for entry in installed_plugins()}
            for entry in entries:
                suffix = ' (installed)' if entry['repository'].casefold() in installed else ''
                item = QListWidgetItem(entry['name'] + suffix)
                item.setData(Qt.ItemDataRole.UserRole, entry['repository'])
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setToolTip(entry.get('description', ''))
                self.plugins.addItem(item)
            self.log.appendPlainText('Select the plugins you want. Existing plugins and user data are retained.')
        self.start(lambda progress: available_plugins(), loaded)

    def install_selected(self):
        repositories = [self.plugins.item(index).data(Qt.ItemDataRole.UserRole)
                        for index in range(self.plugins.count())
                        if self.plugins.item(index).checkState() == Qt.CheckState.Checked]
        if not repositories:
            self.log.appendPlainText('Choose at least one plugin.'); return
        def complete(results):
            installed_setup([manifest for _, manifest, _ in results if manifest], self, self.log.appendPlainText)
            self.log.appendPlainText('Plugin installation finished. Failed items can be selected and retried.')
        self.start(lambda progress: install_plugins(repositories, progress), complete)

    def closeEvent(self, event):
        if self.busy: event.ignore()
        else: super().closeEvent(event)

    def reject(self):
        if not self.busy: super().reject()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName('playlite')
    dialog = InstallerDialog()
    dialog.exec()


if __name__ == '__main__': main()
