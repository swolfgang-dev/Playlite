import unittest
from unittest.mock import Mock,patch
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget, QListWidget, QMessageBox
from PyQt6.QtCore import QEventLoop, QTimer
from playlite.downloads import DownloadQueue, DownloadsPanel, DownloadsButton

class DownloadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])

    def test_games_start_sequentially_and_failure_advances_queue(self):
        queue=DownloadQueue(); first=Mock();second=Mock()
        a=queue.enqueue('First','/tmp/queue-first',lambda *_:first)
        b=queue.enqueue('Second','/tmp/queue-second',lambda *_:second)
        self.app.processEvents()
        first.start.assert_called_once();second.start.assert_not_called()
        queue.update(a,30,'Downloading files')
        self.assertEqual(a.progress,30)
        queue.finish(a,False,'Connection failed');self.app.processEvents()
        self.assertEqual(a.state,'Failed');second.start.assert_called_once()
        queue.finish(b,True,'Validated');self.assertEqual(b.state,'Complete')

    def test_cancel_waiting_job_does_not_start_it_and_active_waits_for_worker(self):
        queue=DownloadQueue();controller=Mock();factory=Mock()
        a=queue.enqueue('Active','/tmp/active',lambda *_:controller)
        b=queue.enqueue('Waiting','/tmp/waiting',factory)
        self.app.processEvents();queue.cancel(b);queue.cancel(a)
        factory.assert_not_called();controller.cancel.assert_called_once()
        self.assertIs(queue.active,a)
        queue.finish(a,False,'Stopped');self.app.processEvents()
        self.assertEqual(a.state,'Cancelled');self.assertEqual(b.state,'Cancelled')

    def test_duplicate_destination_rejected_and_clear_keeps_active(self):
        queue=DownloadQueue();controller=Mock()
        a=queue.enqueue('One','/tmp/same',lambda *_:controller)
        with self.assertRaises(ValueError):queue.enqueue('Two','/tmp/../tmp/same',Mock())
        self.app.processEvents();queue.clear_finished();self.assertEqual(queue.entries,[a])
        queue.shutdown();controller.cancel.assert_called_once()
        with self.assertRaises(ValueError):queue.enqueue('Three','/tmp/three',Mock())

    def test_drawer_reverses_from_current_position_and_tracks_resize(self):
        host=QWidget();host.resize(700,650);queue=DownloadQueue()
        panel=DownloadsPanel(host,queue);host.show()
        panel.set_open(True);panel.animation.setCurrentTime(120)
        amount=panel.amount;self.assertGreater(amount,0)
        panel.set_open(False);self.assertAlmostEqual(panel.animation.startValue(),amount)
        host.resize(500,400);self.app.processEvents()
        self.assertEqual(panel.width(),500)
        panel.animation.setCurrentTime(panel.animation.duration())
        self.assertFalse(panel.isVisible())
        host.close()

    def test_sidebar_footer_reserves_space_and_compact_label_has_tooltip(self):
        sidebar=QListWidget();sidebar.resize(80,400);host=QWidget();queue=DownloadQueue()
        panel=DownloadsPanel(host,queue);binding=DownloadsButton(sidebar,panel,queue)
        sidebar.show();self.app.processEvents()
        self.assertEqual(sidebar.viewportMargins().bottom(),56)
        self.assertEqual(binding.button.text(),'↓')
        self.assertEqual(binding.button.toolTip(),'Downloads')
        self.assertGreaterEqual(binding.button.y(),sidebar.viewport().geometry().bottom())
        sidebar.resize(300,400);self.app.processEvents()
        self.assertEqual(binding.button.text(),'Downloads')
        sidebar.close()

    def test_restart_retains_completed_and_pauses_unfinished(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/'downloads.json';queue=DownloadQueue(storage=path)
            queue.pump=Mock()
            complete=queue.enqueue('Complete','/tmp/complete',Mock(),metadata={'backend':'test','app':10})
            complete.state='Complete';complete.progress=100
            active=queue.enqueue('Active','/tmp/active',Mock());active.state='Downloading'
            queued=queue.enqueue('Queued','/tmp/queued',Mock());queue.changed.emit()
            restored=DownloadQueue(storage=path)
            self.assertEqual([r.state for r in restored.entries],['Complete','Paused','Paused'])
            self.assertEqual(restored.entries[0].metadata,{'backend':'test','app':10})
            self.assertEqual(restored.entries[0].progress,100)
            restored.clear_finished()
            self.assertEqual([r.state for r in restored.entries],['Paused','Paused'])
            self.assertEqual(len(DownloadQueue(storage=path).entries),2)

    def test_pause_resume_and_retry_use_fresh_controller(self):
        queue=DownloadQueue();controllers=[Mock(),Mock(),Mock()]
        factory=Mock(side_effect=controllers)
        row=queue.enqueue('Game','/tmp/game',factory);self.app.processEvents()
        queue.pause(row);controllers[0].cancel.assert_called_once()
        self.assertIs(queue.active,row)
        queue.finish(row,False,'Cancelled');self.assertEqual(row.state,'Paused')
        queue.retry(row);self.app.processEvents();controllers[1].start.assert_called_once()
        queue.finish(row,False,'Network failure');queue.retry(row);self.app.processEvents()
        controllers[2].start.assert_called_once();self.assertFalse(row.cancelled)

    def test_order_pins_active_and_queue_and_clear_retains_paused(self):
        queue=DownloadQueue();queue.pump=Mock()
        states=['Paused','Failed','Complete','Queued','Downloading','Cancelled']
        for index,state in enumerate(states):
            row=queue.enqueue(state,f'/tmp/sort-{index}',Mock());row.state=state
        self.assertEqual([r.state for r in queue.ordered()],['Downloading','Queued','Failed','Paused','Cancelled','Complete'])
        host=QWidget();panel=DownloadsPanel(host,queue)
        self.assertEqual([panel.rows.itemAt(i).widget() for i in range(6)],
                         [panel.cards[r.id][0] for r in queue.ordered()])
        queue.clear_finished();self.assertEqual({r.state for r in queue.entries},{'Queued','Downloading','Paused'})

    def test_close_warning_defaults_to_cancel_without_stopping_queue(self):
        queue=DownloadQueue();queue.pump=Mock();queue.enqueue('Game','/tmp/warning',Mock())
        with patch('playlite.downloads.QMessageBox.warning',return_value=QMessageBox.StandardButton.Cancel) as warning:
            self.assertFalse(queue.confirm_close(None));self.assertFalse(queue.stopped)
            self.assertEqual(warning.call_args.args[-1],QMessageBox.StandardButton.Cancel)
        with patch('playlite.downloads.QMessageBox.warning',return_value=QMessageBox.StandardButton.Close):
            self.assertTrue(queue.confirm_close(None))
