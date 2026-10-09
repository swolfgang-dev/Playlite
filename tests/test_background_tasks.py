import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock
from PyQt6.QtWidgets import QApplication
from playlite.background_tasks import BackgroundTasks
from playlite.downloads import DownloadQueue

APP = QApplication.instance() or QApplication([])


class BackgroundTaskTests(unittest.TestCase):
    def test_restart_marks_unfinished_work_and_preserves_logs_without_callbacks(self):
        with TemporaryDirectory() as temporary:
            path = Path(temporary) / 'tasks.json'
            tasks = BackgroundTasks(storage=path)
            identity = tasks.update(title='Example', kind='Backup', state='Uploading', summary='Uploading', details='Useful error log', retry=Mock())
            restored = BackgroundTasks(storage=path)
            self.assertEqual(restored.records[identity]['state'], 'Interrupted')
            self.assertEqual(restored.records[identity]['details'], 'Useful error log')
            self.assertFalse(restored.callbacks)
            self.assertNotIn('retry', json.loads(path.read_text())[0])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_downloads_expose_real_cancel_and_retry_operations(self):
        queue = DownloadQueue()
        tasks = BackgroundTasks(); tasks.follow_downloads(queue)
        row = queue.enqueue('Example', '/tmp/example-download', Mock())
        identity = 'download-' + row.id
        self.assertEqual(tasks.records[identity]['state'], 'Queued')
        tasks.callbacks[identity]['cancel']()
        self.assertEqual(row.state, 'Cancelled')
        tasks.callbacks[identity]['retry']()
        self.assertEqual(row.state, 'Queued')
        self.assertEqual(tasks.records[identity]['state'], 'Queued')
        self.assertIsNone(tasks.callbacks[identity]['retry'])
        queue.stopped = True

    def test_history_limit_does_not_remove_running_work(self):
        with TemporaryDirectory() as temporary:
            tasks = BackgroundTasks(storage=Path(temporary) / 'tasks.json')
            running = tasks.update(title='Active', state='Running')
            for i in range(205): tasks.update(title=str(i), state='Complete')
            self.assertIn(running, tasks.records)
            self.assertEqual(len(tasks.records), 201)

    def test_task_dialog_can_copy_details_and_use_retry(self):
        from unittest.mock import patch
        from PyQt6.QtWidgets import QDialog, QPushButton, QPlainTextEdit, QTreeWidget
        from playlite.background_tasks import show_tasks
        window = QDialog(); window.background_tasks = BackgroundTasks()
        retry = Mock()
        window.background_tasks.update(title='A long game title', kind='Save backup', state='Failed', summary='Backup failed', details='Specific error', retry=retry)
        def inspect(dialog):
            dialog.show(); APP.processEvents()
            details = dialog.findChild(QPlainTextEdit)
            self.assertFalse(details.isVisible())
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Show details').click()
            self.assertTrue(details.isVisible())
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Copy log').click()
            self.assertEqual(APP.clipboard().text(), 'Backup failed\n\nSpecific error')
            next(b for b in dialog.findChildren(QPushButton) if b.text() == 'Retry').click()
            self.assertGreater(dialog.findChild(QTreeWidget).columnWidth(0), 200)
            dialog.close()
            return 0
        with patch('playlite.background_tasks.run_dialog', side_effect=inspect): show_tasks(window)
        retry.assert_called_once(); window.close()
