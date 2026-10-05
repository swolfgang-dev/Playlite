import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtCore import QLockFile, QTimer
from PyQt6.QtWidgets import QApplication, QDialog, QLineEdit, QMainWindow
from playlite.lifecycle import SingleInstance, TrayLifecycle, run_dialog

APP = QApplication.instance() or QApplication([])


class LifecycleTests(unittest.TestCase):
    def test_pickers_allow_native_desktop_dialogs(self):
        from playlite.lifecycle import choose_directory, choose_file
        from PyQt6.QtWidgets import QFileDialog
        with patch('playlite.lifecycle.QFileDialog') as picker, \
                patch('playlite.lifecycle.run_dialog', return_value=QDialog.DialogCode.Accepted):
            picker.return_value.selectedFiles.return_value = ['/games/Example']
            self.assertEqual(choose_directory(None, 'Folder', '/games'), '/games/Example')
            picker.assert_called_with(None, 'Folder', '/games')
            self.assertNotIn(unittest.mock.call(QFileDialog.Option.DontUseNativeDialog, True),
                             picker.return_value.setOption.call_args_list)
            picker.return_value.selectedFiles.return_value = ['/games/Example/game.exe']
            picker.return_value.selectedNameFilter.return_value = 'All files (*)'
            self.assertEqual(choose_file(None, 'Executable', '/games', 'All files (*)')[0],
                             '/games/Example/game.exe')
            picker.assert_called_with(None, 'Executable', '/games', 'All files (*)')
            self.assertNotIn(unittest.mock.call(QFileDialog.Option.DontUseNativeDialog, True),
                             picker.return_value.setOption.call_args_list)

    def test_second_instance_activates_first_and_lock_is_released(self):
        with tempfile.TemporaryDirectory() as directory:
            name = 'playlite-test-' + uuid.uuid4().hex
            first, second = SingleInstance(), SingleInstance()
            for instance in (first, second):
                instance.name = name
                instance.lock = QLockFile(str(Path(directory) / 'instance.lock'))
            activated = []
            self.assertTrue(first.start(lambda: activated.append(True)))
            self.assertFalse(second.start(lambda: None))
            APP.processEvents()
            self.assertEqual(activated, [True])
            first.stop()
            self.assertTrue(second.start(lambda: None))
            second.stop()

    def test_close_with_dialog_preserves_edits_and_restores(self):
        window = QMainWindow()
        dialog = QDialog(window)
        field = QLineEdit('Unsaved edit', dialog)
        with patch('playlite.lifecycle.QSystemTrayIcon.isSystemTrayAvailable', return_value=True), patch('playlite.lifecycle.QSystemTrayIcon.show'):
            lifecycle = TrayLifecycle(window, APP)
            window.show()
            dialog.show()
            window.close()
            self.assertFalse(window.isVisible())
            self.assertFalse(dialog.isVisible())
            self.assertEqual(field.text(), 'Unsaved edit')
            lifecycle.restore()
            self.assertTrue(window.isVisible())
            self.assertTrue(dialog.isVisible())
            self.assertEqual(field.text(), 'Unsaved edit')
            dialog.reject()
            lifecycle.quitting = True
            window.close()

    def test_nested_dialog_controls_remain_enabled(self):
        parent = QDialog()
        child = QDialog(parent)
        field = QLineEdit('Editable', child)
        parent.show()
        states = []
        def finish():
            states.append((child.isEnabled(), field.isEnabled()))
            child.accept()
        QTimer.singleShot(0, finish)
        run_dialog(child)
        self.assertEqual(states, [(True, True)])
        parent.reject()

    def test_dialog_wait_keeps_main_window_enabled(self):
        window = QMainWindow()
        dialog = QDialog(window)
        window.show()
        enabled = []
        def finish():
            enabled.append(window.isEnabled())
            dialog.accept()
        QTimer.singleShot(0, finish)
        self.assertEqual(run_dialog(dialog), QDialog.DialogCode.Accepted)
        self.assertEqual(enabled, [True])
        window.close()
