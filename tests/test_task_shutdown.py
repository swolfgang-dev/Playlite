import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from PyQt6 import sip
from PyQt6.QtWidgets import QApplication
from playlite.metadata_dialog import Task
APP=QApplication.instance() or QApplication([])


class TaskShutdownTests(unittest.TestCase):
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
