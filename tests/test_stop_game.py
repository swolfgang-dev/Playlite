import unittest
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication, QWidget, QMessageBox
from playlite.app import LibraryWindow


class StopConfirmation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_cancel_does_not_start_stop_task(self):
        window = QWidget()
        window.current = {'Id': 'example', 'Name': 'Example'}
        window.stop_tasks = {}
        with patch('playlite.app.run_dialog', return_value=QMessageBox.StandardButton.Cancel), patch('playlite.app.QThreadPool.globalInstance') as pool:
            LibraryWindow.stop_game(window)
            pool.assert_not_called()
        self.assertEqual(window.stop_tasks, {})
