import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from playlite.tasks import Task
APP=QApplication.instance() or QApplication([])


class TaskShutdownTests(unittest.TestCase):
    def test_legacy_import_is_the_shared_worker(self):
        from playlite.metadata_dialog import Task as LegacyTask
        self.assertIs(LegacyTask, Task)

    def test_progress_and_failure_after_qt_shutdown_are_safe(self):
        messages=[]
        task=Task(lambda: None)
        task.signals.progress.connect(messages.append)
        task.progress('Working')
        self.assertEqual(messages,['Working'])
        sip.delete(task.signals)
        task.progress('Finished')
        def fail():raise ValueError('Failure during shutdown')
        task.function=fail
        task.run()

    def test_worker_finishing_after_qt_shutdown_does_not_emit_to_deleted_signals(self):
        task=Task(lambda: 'Done')
        sip.delete(task.signals)
        task.run()

    def test_live_workers_still_report_success_and_failure(self):
        values=[]
        task=Task(lambda: 42);task.signals.succeeded.connect(values.append);task.run()
        self.assertEqual(values,[42])
        def fail():raise ValueError('Expected failure')
        task=Task(fail);task.signals.failed.connect(values.append);task.run()
        self.assertEqual(values,[42,'Expected failure'])
