"""Single-instance activation, nonblocking dialogs, and tray lifecycle."""
import os
from pathlib import Path
from PyQt6.QtCore import QObject, QEvent, QEventLoop, QLockFile, QStandardPaths, QTimer, Qt
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog, QInputDialog, QMessageBox, QMenu, QSystemTrayIcon
from PyQt6.QtGui import QAction


def run_dialog(dialog):
    """Wait for a dialog's result without disabling the main window's close button."""
    loop = QEventLoop()
    dialog.setWindowModality(Qt.WindowModality.NonModal)
    dialog.finished.connect(loop.quit)
    dialog.show()
    dialog.raise_()
    loop.exec()
    try:
        dialog.finished.disconnect(loop.quit)
    except TypeError:
        pass
    return dialog.result()


def picker_directory(path):
    """Resolve a starting folder without inheriting another dialog's history."""
    folder = Path(path).expanduser().absolute() if path else Path.home()
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent
    return str(folder)


def choose_file(parent, title, directory='', file_filter=''):
    dialog = QFileDialog(parent, title, directory, file_filter)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setViewMode(QFileDialog.ViewMode.List)
    dialog.setDirectory(picker_directory(directory))
    if directory and Path(directory).expanduser().is_file():
        dialog.selectFile(str(Path(directory).expanduser()))
    dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
    if run_dialog(dialog) == QDialog.DialogCode.Accepted:
        files = dialog.selectedFiles()
        return (files[0] if files else '', dialog.selectedNameFilter())
    return '', ''


def choose_directory(parent, title, directory=''):
    dialog = QFileDialog(parent, title, directory)
    dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
    dialog.setViewMode(QFileDialog.ViewMode.List)
    dialog.setDirectory(picker_directory(directory))
    dialog.setFileMode(QFileDialog.FileMode.Directory)
    dialog.setOption(QFileDialog.Option.ShowDirsOnly, True)
    if run_dialog(dialog) == QDialog.DialogCode.Accepted:
        files = dialog.selectedFiles()
        return files[0] if files else ''
    return ''


def ask_text(parent, title, label):
    dialog = QInputDialog(parent)
    dialog.setWindowTitle(title)
    dialog.setLabelText(label)
    accepted = run_dialog(dialog) == QDialog.DialogCode.Accepted
    return dialog.textValue(), accepted


def show_warning(parent, title, message):
    dialog = QMessageBox(QMessageBox.Icon.Warning, title, message, QMessageBox.StandardButton.Ok, parent)
    run_dialog(dialog)


class SingleInstance(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        runtime = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
        runtime.mkdir(parents=True, exist_ok=True)
        self.name = f'playlite-{os.getuid()}'
        self.lock = QLockFile(str(runtime / (self.name + '.lock')))
        self.server = QLocalServer(self)
        self.server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)

    def start(self, activate):
        if not self.lock.tryLock(0):
            socket = QLocalSocket(self)
            socket.connectToServer(self.name)
            if socket.waitForConnected(2000):
                socket.write(b'activate')
                socket.flush()
                socket.waitForBytesWritten(1000)
                socket.disconnectFromServer()
            return False
        QLocalServer.removeServer(self.name)
        if not self.server.listen(self.name):
            self.lock.unlock()
            raise RuntimeError('Could not start the Playlite activation socket.')
        def connected():
            while self.server.hasPendingConnections():
                socket = self.server.nextPendingConnection()
                activate()
                socket.disconnectFromServer()
                socket.deleteLater()
        self.server.newConnection.connect(connected)
        return True

    def stop(self):
        self.server.close()
        self.lock.unlock()


class TrayLifecycle(QObject):
    def __init__(self, window, app):
        super().__init__(window)
        self.window, self.app = window, app
        self.hidden_dialogs = []
        self.quitting = False
        self.tray = QSystemTrayIcon(app.windowIcon(), self)
        self.tray.setToolTip('Playlite')
        self.menu = QMenu(window)
        show = QAction('Show Playlite', self)
        show.triggered.connect(self.restore)
        self.menu.addAction(show)
        self.menu.addSeparator()
        quit_action = QAction('Quit Playlite', self)
        quit_action.triggered.connect(self.quit)
        self.menu.addAction(quit_action)
        self.tray.setContextMenu(self.menu)
        self.tray.activated.connect(self.activated)
        window.installEventFilter(self)
        app.setQuitOnLastWindowClosed(False)
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

    def activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            self.restore()

    def eventFilter(self, watched, event):
        if watched is self.window and event.type() == QEvent.Type.Close and not self.quitting:
            if hasattr(self.window, 'save_window_state'):
                self.window.save_window_state()
            settings = getattr(self.window, 'settings', None)
            close_to_tray = settings.value('app/closeToTray', True, type=bool) if settings else True
            if not close_to_tray or not QSystemTrayIcon.isSystemTrayAvailable():
                self.quit()
            else:
                self.hidden_dialogs = [widget for widget in self.app.topLevelWidgets()
                                       if isinstance(widget, QDialog) and widget.isVisible()]
                for dialog in self.hidden_dialogs:
                    dialog.hide()
                self.window.hide()
            event.ignore()
            return True
        return super().eventFilter(watched, event)

    def restore(self):
        if self.window.isMinimized():
            self.window.showNormal()
        else:
            self.window.show()
        self.window.raise_()
        self.window.activateWindow()
        for dialog in self.hidden_dialogs:
            dialog.show()
            dialog.raise_()
        if self.hidden_dialogs:
            self.hidden_dialogs[-1].activateWindow()
        self.hidden_dialogs.clear()

    def quit(self):
        if self.quitting:
            return
        self.quitting = True
        from PyQt6.QtCore import QProcess
        jobs = [dialog for dialog in self.window.findChildren(QDialog)
                if dialog.property('playliteBackgroundJob') and dialog.process.state() != QProcess.ProcessState.NotRunning]
        for dialog in jobs:
            dialog.cancel_or_close()
        for dialog in self.app.topLevelWidgets():
            if isinstance(dialog, QDialog) and dialog not in jobs:
                dialog.reject()
        if jobs:
            self.quit_timer = QTimer(self)
            def completed():
                if all(job.process.state() == QProcess.ProcessState.NotRunning for job in jobs):
                    self.quit_timer.stop()
                    self.app.quit()
            self.quit_timer.timeout.connect(completed)
            self.quit_timer.start(100)
        else:
            self.app.quit()
