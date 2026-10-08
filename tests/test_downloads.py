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

    def test_enqueue_shows_strip_and_confirmation_without_expanding(self):
        host=QWidget();host.resize(800,600)
        queue=DownloadQueue();panel=DownloadsPanel(host,queue);host.show()
        queue.enqueue('New game','/tmp/new-game-confirmation',lambda *_:Mock())
        self.app.processEvents()
        self.assertFalse(panel.opened)
        self.assertTrue(panel.cards[queue.active.id][0].isVisible())
        self.assertFalse(panel.active_strip.isVisible())
        self.assertEqual(panel.active_label.text(),'Added to downloads · New game')
        panel.clear_confirmation()
        self.assertEqual(panel.cards[queue.active.id][1].text(),'New game')
        host.close()

    def test_active_strip_reserves_space_and_panel_expands_above_it(self):
        from PyQt6.QtWidgets import QScrollArea
        host=QScrollArea();host.resize(800,600);host.setWidget(QWidget())
        queue=DownloadQueue();panel=DownloadsPanel(host,queue)
        host.show()
        row=queue.enqueue('Active game','/tmp/active-strip',lambda *_:Mock())
        self.app.processEvents()
        queue.update(row,35,'Steam downloading · 35% · 35 / 100 MiB · 83.9 Mbps · 1 min remaining · disk 50 / 120 MiB')
        status=panel.cards[row.id][2]
        self.assertEqual(status.text(),'Steam downloading')
        self.assertEqual(status.metrics_label.text(),'35 / 100 MiB · 83.9 Mbps · 1 min remaining')
        queue.update(row,50,'Copying files · 50 / 100 MiB')
        self.assertEqual(status.text(),'Copying files')
        self.assertEqual(status.metrics_label.text(),'50 / 100 MiB')
        queue.update(row,75,'Verifying copied files · 50 / 100 MiB')
        self.assertEqual(status.text(),'Verifying copied files')
        self.assertEqual(status.metrics_label.text(),'50 / 100 MiB')
        queue.update(row,35,'Steam downloading · 35 / 100 MiB · 83.9 Mbps · 1 min remaining')
        card=panel.cards[row.id][0]
        self.assertTrue(card.isVisible())
        self.assertFalse(panel.active_strip.isVisible())
        self.assertEqual(panel.cards[row.id][3].value(),350)
        self.assertEqual(panel.cards[row.id][3].percent_label.text(),'35%')
        start=card.pos()
        reserved=host.viewportMargins().bottom()
        from PyQt6.QtTest import QTest
        from PyQt6.QtCore import Qt,QPoint
        QTest.mouseClick(card,Qt.MouseButton.LeftButton,pos=QPoint(3,3))
        self.assertTrue(panel.opened)
        self.assertFalse(panel.close_button.icon().isNull())
        self.assertEqual(panel.close_button.text(),'')
        panel.animation.setCurrentTime(panel.animation.duration())
        from PyQt6.QtCore import QPoint
        self.assertEqual(card.mapTo(host,QPoint(0,0)),panel.card_slot.mapTo(host,QPoint(0,0)))
        self.assertLess(card.y(),start.y())
        self.assertEqual(panel.panel_opacity.opacity(),1)
        self.assertLessEqual(panel.height(),host.height()*.5)
        self.assertEqual(panel.geometry().bottom()+1,host.height())
        panel.close_button.click();panel.animation.setCurrentTime(panel.animation.duration())
        self.assertTrue(panel.cards[row.id][3].isVisible())
        self.assertEqual(card.pos(),start)
        self.assertEqual(host.viewportMargins().bottom(),reserved)
        queue.finish(row,True,'Done')
        self.assertFalse(panel.active_strip.isVisible())
        self.assertEqual(panel.pinned_id,row.id)
        self.assertTrue(panel.completion_timer.isActive())
        panel.completion_timer.stop();panel.completion_timer.timeout.emit()
        self.assertEqual(panel.pinned_id,row.id)
        panel.card_fade.setCurrentTime(panel.card_fade.duration())
        self.assertIsNone(panel.pinned_id)
        self.assertEqual(host.viewportMargins().bottom(),0)
        host.close()

    def test_completed_card_holds_before_next_download_takes_over(self):
        host=QWidget();host.resize(800,600);host.show()
        queue=DownloadQueue();panel=DownloadsPanel(host,queue)
        first=queue.enqueue('First','/tmp/first',lambda *_:Mock())
        second=queue.enqueue('Second','/tmp/second',lambda *_:Mock())
        self.app.processEvents()
        panel.card_fade.setCurrentTime(panel.card_fade.duration())
        self.assertEqual(panel.card_opacity,1.)
        queue.finish(first,True,'Done');self.app.processEvents()
        self.assertIs(queue.active,second)
        self.assertEqual(panel.pinned_id,first.id)
        queue.update(second,10,'Downloading')
        self.assertEqual(panel.pinned_id,first.id)
        panel.completion_timer.stop();panel.completion_timer.timeout.emit()
        self.assertEqual(panel.pinned_id,second.id)
        self.assertEqual(panel.card_opacity,1.)
        host.close()

    def test_new_download_fades_in_after_completed_card_disappears(self):
        host=QWidget();host.resize(800,600);host.show()
        queue=DownloadQueue();panel=DownloadsPanel(host,queue)
        first=queue.enqueue('First','/tmp/first',lambda *_:Mock())
        self.assertEqual(panel.card_opacity,0.)
        self.app.processEvents()
        panel.card_fade.setCurrentTime(panel.card_fade.duration())
        queue.finish(first,True,'Done')
        panel.completion_timer.stop();panel.completion_timer.timeout.emit()
        panel.card_fade.setCurrentTime(panel.card_fade.duration())
        self.assertIsNone(panel.pinned_id)
        second=queue.enqueue('Second','/tmp/second',lambda *_:Mock())
        self.assertEqual(panel.pinned_id,second.id)
        self.assertEqual(panel.card_opacity,0.)
        panel.card_fade.setCurrentTime(panel.card_fade.duration())
        self.assertEqual(panel.cards[second.id][0].graphicsEffect().opacity(),1.)
        host.close()

    def test_hover_retains_completed_card_and_leave_restarts_countdown(self):
        from PyQt6.QtCore import QEvent
        host=QWidget();host.resize(800,600);host.show()
        queue=DownloadQueue();panel=DownloadsPanel(host,queue)
        first=queue.enqueue('First','/tmp/first',lambda *_:Mock())
        second=queue.enqueue('Second','/tmp/second',lambda *_:Mock())
        self.app.processEvents()
        card=panel.cards[first.id][0]
        panel.eventFilter(card,QEvent(QEvent.Type.Enter))
        queue.finish(first,True,'Done');self.app.processEvents()
        self.assertFalse(panel.completion_timer.isActive())
        panel.release_completed()
        self.assertEqual(panel.pinned_id,first.id)
        queue.update(second,10,'Downloading')
        self.assertFalse(panel.completion_timer.isActive())
        panel.eventFilter(card,QEvent(QEvent.Type.Leave))
        self.assertTrue(panel.completion_timer.isActive())
        self.assertEqual(panel.completion_timer.interval(),3000)
        panel.eventFilter(card,QEvent(QEvent.Type.Enter))
        self.assertFalse(panel.completion_timer.isActive())
        panel.eventFilter(card,QEvent(QEvent.Type.Leave))
        panel.completion_timer.stop();panel.completion_timer.timeout.emit()
        self.assertEqual(panel.pinned_id,second.id)
        host.close()

    def test_pause_all_stops_active_and_queue_until_resume(self):
        host=QWidget();queue=DownloadQueue();panel=DownloadsPanel(host,queue)
        first=queue.enqueue('First','/tmp/all-first',lambda *_:Mock())
        second=queue.enqueue('Second','/tmp/all-second',lambda *_:Mock())
        self.app.processEvents()
        controller=first.controller
        controller.cancel.side_effect=lambda:queue.finish(first,False,'Paused')
        panel.pause_all_button.click();self.app.processEvents()
        self.assertEqual([first.state,second.state],['Paused','Paused'])
        self.assertIsNone(queue.active)
        self.assertEqual(panel.pause_all_button.text(),'Resume all')
        third=queue.enqueue('Third','/tmp/all-third',lambda *_:Mock())
        self.app.processEvents();self.assertIsNone(queue.active)
        panel.pause_all_button.click();self.app.processEvents()
        self.assertIs(queue.active,first)
        self.assertEqual(second.state,'Queued');self.assertEqual(third.state,'Queued')
        self.assertEqual(panel.pause_all_button.text(),'Pause all')
        host.close()

    def test_resume_all_while_active_pause_is_finishing(self):
        queue=DownloadQueue()
        first=queue.enqueue('First','/tmp/resume-all-first',lambda *_:Mock())
        second=queue.enqueue('Second','/tmp/resume-all-second',lambda *_:Mock())
        self.app.processEvents();queue.pause_all();queue.resume_all()
        self.assertTrue(first.paused)
        queue.finish(first,False,'Paused');self.app.processEvents()
        self.assertEqual(first.state,'Downloading')
        self.assertFalse(first.paused);self.assertFalse(first.cancelled)
        self.assertEqual(second.state,'Queued')

    def test_download_now_swaps_active_with_queue_front_after_worker_stops(self):
        host=QWidget();queue=DownloadQueue();panel=DownloadsPanel(host,queue)
        active=queue.enqueue('Active','/tmp/swap-active',lambda *_:Mock())
        first=queue.enqueue('First','/tmp/swap-first',lambda *_:Mock())
        chosen=queue.enqueue('Chosen','/tmp/swap-chosen',lambda *_:Mock())
        self.app.processEvents();queue.update(active,42,'Downloading')
        promote=panel.cards[chosen.id][8]
        self.assertEqual(promote.toolTip(),'Download now')
        promote.click()
        self.assertIs(queue.active,active)
        active.controller.cancel.assert_called_once()
        self.assertFalse(panel.cards[first.id][8].isEnabled())
        queue.finish(active,False,'Paused');self.app.processEvents()
        self.assertIs(queue.active,chosen)
        self.assertEqual([row.name for row in queue.ordered()],['Chosen','Active','First'])
        self.assertEqual(active.state,'Queued');self.assertEqual(active.progress,42)
        self.assertEqual(len(panel.cards[chosen.id]),9)
        host.close()

    def test_remove_completed_entry_keeps_files_and_other_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);files=root/'game';files.mkdir();(files/'game.exe').write_bytes(b'game')
            queue=DownloadQueue(storage=root/'downloads.json')
            row=queue.enqueue('Finished',str(files),lambda *_:Mock())
            other=queue.enqueue('Waiting',str(root/'other'),lambda *_:Mock())
            self.app.processEvents();queue.finish(row,True,'Done')
            host=QWidget();panel=DownloadsPanel(host,queue)
            panel.cards[row.id][0].remove_button.click()
            self.assertNotIn(row,queue.entries)
            self.assertIn(other,queue.entries)
            self.assertNotIn(row.id,panel.cards)
            self.assertEqual((files/'game.exe').read_bytes(),b'game')
            self.assertNotIn(row.id,[entry.id for entry in DownloadQueue(storage=root/'downloads.json').entries])
            queue.remove_completed(other)
            self.assertIn(other,queue.entries)
            host.close()

    def test_status_changes_keep_card_and_panel_height_stable(self):
        host=QWidget();host.resize(1000,800)
        queue=DownloadQueue();row=queue.enqueue('Game','/tmp/stable-download',lambda *_:Mock())
        panel=DownloadsPanel(host,queue);host.show();self.app.processEvents()
        panel.set_open(True);panel.animation.setCurrentTime(panel.animation.duration())
        heights=[]
        for state,progress,message in (
                ('Downloading',None,'Starting'),
                ('Downloading',45,'45 / 100 MiB · 83.9 Mbps · 1 min remaining'),
                ('Paused',45,'Paused · partial files retained'),
                ('Complete',100,'Windows download completed and verified by Steam')):
            row.state=state;row.progress=progress;row.status=message
            panel.refresh();self.app.processEvents()
            if state=='Paused':
                self.assertEqual(panel.cards[row.id][2].text(),'Paused · partial files retained')
            heights.append((panel.height(),panel.cards[row.id][0].sizeHint().height()))
        self.assertEqual(len(set(heights)),1,heights)
        host.close()

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

    def test_reordering_changes_next_download_and_retains_active(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'downloads.json'
            queue=DownloadQueue(storage=path)
            controllers=[Mock(),Mock(),Mock()]
            active=queue.enqueue('Active','/tmp/reorder-active',lambda *_:controllers[0])
            first=queue.enqueue('First','/tmp/reorder-first',lambda *_:controllers[1])
            second=queue.enqueue('Second','/tmp/reorder-second',lambda *_:controllers[2])
            self.app.processEvents()
            queue.move_queued(second,-1)
            self.assertEqual(queue.ordered(),[active,second,first])
            self.assertIs(queue.active,active)
            self.assertEqual([r.name for r in DownloadQueue(storage=path).entries],['Active','Second','First'])
            queue.move_queued(active,1)
            queue.move_queued(second,-1)
            self.assertEqual(queue.ordered(),[active,second,first])
            queue.finish(active,True,'Done');self.app.processEvents()
            self.assertIs(queue.active,second)
            controllers[2].start.assert_called_once()
            controllers[1].start.assert_not_called()

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

    def test_download_pane_reserves_scroll_space_and_restores_it_on_close(self):
        from PyQt6.QtWidgets import QScrollArea
        host=QScrollArea();host.resize(700,650)
        content=QWidget();content.setFixedSize(600,1600);host.setWidget(content)
        panel=DownloadsPanel(host,DownloadQueue());host.show();self.app.processEvents()
        original=host.viewport().height()
        panel.set_open(True);panel.animation.setCurrentTime(panel.animation.duration());self.app.processEvents()
        self.assertLess(host.viewport().height(),original)
        self.assertGreater(host.viewportMargins().bottom(),0)
        host.verticalScrollBar().setValue(host.verticalScrollBar().maximum())
        self.assertEqual(host.verticalScrollBar().value(),host.verticalScrollBar().maximum())
        self.assertLessEqual(host.viewport().geometry().bottom(),panel.y())
        host.resize(700,500);self.app.processEvents()
        self.assertLessEqual(host.viewport().geometry().bottom(),panel.y())
        panel.set_open(False);panel.animation.setCurrentTime(panel.animation.duration());self.app.processEvents()
        self.assertEqual(host.viewportMargins().bottom(),0)
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
        expected=[panel.card_slot if r.id==panel.pinned_id else panel.cards[r.id][0] for r in queue.ordered()]
        self.assertEqual([panel.rows.itemAt(i).widget() for i in range(len(expected))],expected)
        self.assertIs(panel.cards[panel.pinned_id][0].parentWidget(),host)
        queue.clear_finished();self.assertEqual({r.state for r in queue.entries},{'Queued','Downloading','Paused'})

    def test_close_warning_defaults_to_cancel_without_stopping_queue(self):
        queue=DownloadQueue();queue.pump=Mock();queue.enqueue('Game','/tmp/warning',Mock())
        def cancel(dialog):
            self.assertEqual(dialog.defaultButton().text(),'Keep Playlite running')
            self.assertEqual(dialog.button(QMessageBox.StandardButton.Close).text(),'Pause and exit')
            return QMessageBox.StandardButton.Cancel
        with patch('playlite.downloads.QMessageBox.exec',new=cancel):
            self.assertFalse(queue.confirm_close(None));self.assertFalse(queue.stopped)
        with patch('playlite.downloads.QMessageBox.exec',return_value=QMessageBox.StandardButton.Close):
            self.assertTrue(queue.confirm_close(None))

    def test_successful_library_add_is_labelled_and_persisted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'downloads.json'
            queue = DownloadQueue(storage=path)
            controller = Mock(); controller.add_to_library.return_value = None
            row = queue.enqueue('Game', '/tmp/added-download', lambda *_: controller)
            self.app.processEvents(); queue.finish(row, True, 'Complete')
            host = QWidget(); panel = DownloadsPanel(host, queue)
            button = panel.cards[row.id][5]
            button.click()
            self.assertEqual(button.text(), 'Add to Playlite')
            self.assertTrue(button.isEnabled())
            controller.add_to_library.return_value = 'saved-game-id'
            button.click()
            self.assertEqual(button.text(), 'Added')
            self.assertFalse(button.isEnabled())
            self.assertEqual(DownloadQueue(storage=path).entries[0].metadata['library_game_id'], 'saved-game-id')
            host.close()


class ScrollCardTests(unittest.TestCase):
    def test_expanded_active_card_tracks_scroll_and_clips_to_viewport(self):
        from PyQt6.QtCore import QPoint
        app=QApplication.instance() or QApplication([])
        host=QWidget();host.resize(900,700)
        queue=DownloadQueue();queue.pump=Mock()
        for index in range(8):queue.enqueue(str(index),f'/tmp/scroll-card-{index}',Mock())
        queue.entries[0].state='Downloading';queue.active=queue.entries[0]
        panel=DownloadsPanel(host,queue);host.show();panel.show()
        panel.set_amount(1);app.processEvents();panel.place()
        card=panel.cards[panel.pinned_id][0]
        self.assertIs(card.parentWidget(),panel.card_slot)
        before=card.mapTo(panel.rows_scroll.viewport(),QPoint(0,0)).y()
        for value in range(5):
            queue.update(queue.active,value,'Downloading')
            app.processEvents()
            self.assertIs(card.parentWidget(),panel.card_slot)
            self.assertEqual(card.mapTo(panel.rows_scroll.viewport(),QPoint(0,0)).y(),before)
        bar=panel.rows_scroll.verticalScrollBar();bar.setValue(min(60,bar.maximum()))
        self.assertGreater(bar.value(),0)
        self.assertEqual(card.mapTo(panel.rows_scroll.viewport(),QPoint(0,0)).y(),before-bar.value())
        panel.set_amount(0)
        self.assertIs(card.parentWidget(),host)
        host.close()

    def test_reversing_animation_and_resizing_keeps_card_in_correct_layout(self):
        app=QApplication.instance() or QApplication([])
        host=QWidget();host.resize(900,700)
        queue=DownloadQueue();queue.pump=Mock()
        row=queue.enqueue('Game','/tmp/reverse-layout',Mock())
        panel=DownloadsPanel(host,queue);host.show()
        panel.set_open(True);panel.animation.setCurrentTime(130)
        queue.update(row,25,'Downloading')
        panel.set_open(False);panel.animation.setCurrentTime(260)
        card=panel.cards[row.id][0]
        self.assertIs(card.parentWidget(),host)
        panel.set_open(True);panel.animation.setCurrentTime(260)
        self.assertIs(card.parentWidget(),panel.card_slot)
        self.assertFalse(panel.panel_opacity.isEnabled())
        host.resize(1100,800);app.processEvents();panel.place()
        self.assertEqual(card.width(),panel.card_slot.width())
        for index in range(10):queue.update(row,index,'Downloading')
        self.assertIs(card.parentWidget(),panel.card_slot)
        self.assertEqual(panel.card_layout.count(),1)
        panel.set_open(False);panel.animation.setCurrentTime(260)
        self.assertIs(card.parentWidget(),host)
        self.assertEqual(panel.card_layout.count(),0)
        host.close()
