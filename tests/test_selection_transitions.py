import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch
from PyQt6.QtCore import QAbstractAnimation,Qt
from PyQt6.QtWidgets import QApplication
from playlite.app import LibraryWindow
APP=QApplication.instance() or QApplication([])

class SelectionTransitionTests(unittest.TestCase):
    def test_late_artwork_does_not_touch_a_deleted_detail_widget(self):
        from PyQt6 import sip
        from PyQt6.QtGui import QImage
        from PyQt6.QtWidgets import QWidget
        window=SimpleNamespace(devicePixelRatioF=lambda:1,content=Mock())
        hero=QWidget();window.play_hero=hero
        with patch('playlite.app.QThreadPool.globalInstance') as pool:
            LibraryWindow.load_detail_artwork(window,'late.png','',hero,Mock(),Mock(),Mock())
            task=pool.return_value.start.call_args.args[0]
            sip.delete(hero)
            task.signals.succeeded.emit((QImage(),QImage()))
        self.assertEqual(window.detail_art_tasks,[])

    def test_custom_library_owns_its_download_queue(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory, patch('playlite.providers.discover_plugins',return_value={}):
            data=Path(directory)
            window=LibraryWindow(data)
            self.assertEqual(window.download_queue.storage,data/'downloads.json')
            window.close()

    def test_selection_builds_immediately_during_animation(self):
        item=Mock();item.data.return_value={'Id':'one'}
        animation=Mock();animation.state.return_value=QAbstractAnimation.State.Running
        window=SimpleNamespace(current=None,game_scroll=Mock(),content=Mock(),library_animation=animation,
                               build_game_view=Mock(),game_view_generation=0)
        with patch('playlite.app.QTimer.singleShot'):
            LibraryWindow.select_game(window,item)
        window.build_game_view.assert_called_once_with(item)
        animation.stop.assert_not_called()
        window.content.cover_animation.stop.assert_called_once()

    def test_late_artwork_does_not_update_previous_selection(self):
        from PyQt6.QtGui import QImage
        window=SimpleNamespace(devicePixelRatioF=lambda:1,content=Mock())
        first=Mock();second=Mock();cover=Mock();row=Mock();info=Mock()
        window.play_hero=first
        with patch('playlite.app.QThreadPool.globalInstance') as pool:
            LibraryWindow.load_detail_artwork(window,'first.png','',first,cover,row,info)
            old_task=pool.return_value.start.call_args.args[0]
            window.play_hero=second
            LibraryWindow.load_detail_artwork(window,'second.png','',second,cover,row,info)
            current_task=pool.return_value.start.call_args.args[0]
            old_task.signals.succeeded.emit((QImage(),QImage()))
            first.update.assert_not_called()
            current_task.signals.succeeded.emit((QImage(),QImage()))
            second.update.assert_called_once()
        self.assertEqual(window.detail_art_tasks,[])
