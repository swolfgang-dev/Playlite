import unittest
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QApplication, QListWidgetItem, QListView, QStyle, QStyleOptionViewItem
from unittest.mock import patch
from playlite.app import LibraryList

APP = QApplication.instance() or QApplication([])


class SelectedRowTests(unittest.TestCase):
    def create_list(self):
        view = LibraryList()
        for identity in ('a', 'b', 'c'):
            item = QListWidgetItem(identity)
            item.setData(Qt.ItemDataRole.UserRole, dict(Id=identity, Name=identity))
            view.addItem(item)
        view.setSelectionMode(view.SelectionMode.ExtendedSelection)
        view.setCurrentItem(view.item(2))
        view.item(0).setSelected(True)
        view.item(1).setSelected(True)
        view.compact_enabled = True
        return view

    def test_multi_selected_rows_remain_expanded_when_hover_leaves(self):
        view = self.create_list()
        for identity in ('a', 'b'):
            view.row_widths[identity] = 180
            view.animate_row(identity, 0)
            animation = view.row_animations[identity]
            self.assertEqual(animation.endValue(), view.expanded_row_width(view.item(0 if identity == 'a' else 1).data(Qt.ItemDataRole.UserRole)))
            animation.setCurrentTime(animation.duration())
            self.assertEqual(view.row_widths[identity], animation.endValue())
        view.item(0).setSelected(False)
        self.assertEqual(view.row_animations['a'].endValue(), 0)
        self.assertEqual(view.row_animations['b'].endValue(), view.expanded_row_width(view.item(1).data(Qt.ItemDataRole.UserRole)))
        view.hide_hover_immediately()

    def test_selecting_a_closing_row_reverses_it_to_expanded_width(self):
        view = self.create_list()
        view.item(0).setSelected(False)
        view.row_widths['a'] = 180
        view.animate_row('a', 0)
        view.row_animations['a'].setCurrentTime(900)
        view.item(0).setSelected(True)
        self.assertEqual(view.row_animations['a'].endValue(), view.expanded_row_width(view.item(0).data(Qt.ItemDataRole.UserRole)))
        self.assertGreaterEqual(view.row_widths['a'], 64)
        view.hide_hover_immediately()

    def test_context_menu_hover_cleanup_preserves_selected_expansions(self):
        view = self.create_list()
        view.hover_id = 'a'
        expected = {item.data(Qt.ItemDataRole.UserRole)['Id']: view.expanded_row_width(item.data(Qt.ItemDataRole.UserRole)) for item in view.selectedItems()}
        view.hide_hover_immediately(preserve_selected=True)
        self.assertIsNone(view.hover_id)
        for item in view.selectedItems():
            game = item.data(Qt.ItemDataRole.UserRole)
            self.assertEqual(view.row_widths[game['Id']], expected[game['Id']])
        view.hide_hover_immediately()

    def test_selected_border_is_drawn_in_grid_list_and_compact_modes(self):
        view = self.create_list()
        delegate = view.itemDelegate()
        for mode, text in ((QListView.ViewMode.IconMode, 'a'), (QListView.ViewMode.ListMode, 'a'), (QListView.ViewMode.ListMode, '')):
            view.setViewMode(mode)
            view.item(0).setText(text)
            option = QStyleOptionViewItem()
            option.rect = QRect(0, 0, 180, 66)
            option.state = QStyle.StateFlag.State_Selected
            image = QImage(200, 80, QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.transparent)
            painter = QPainter(image)
            with patch('playlite.app.selection_border') as border:
                delegate.paint(painter, option, view.model().index(0, 0))
                border.assert_called_once()
            painter.end()

    def test_single_selection_has_no_blue_border(self):
        view = self.create_list()
        view.clearSelection()
        view.item(0).setSelected(True)
        for mode, text in ((QListView.ViewMode.IconMode, 'a'), (QListView.ViewMode.ListMode, 'a'), (QListView.ViewMode.ListMode, '')):
            view.setViewMode(mode)
            view.item(0).setText(text)
            option = QStyleOptionViewItem()
            option.rect = QRect(0, 0, 180, 66)
            option.state = QStyle.StateFlag.State_Selected
            image = QImage(200, 80, QImage.Format.Format_ARGB32)
            painter = QPainter(image)
            with patch('playlite.app.selection_border') as border:
                view.itemDelegate().paint(painter, option, view.model().index(0, 0))
                border.assert_not_called()
            painter.end()

    def test_multi_selection_expands_only_selected_rows_and_survives_refresh(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from playlite.app import LibraryWindow
        with TemporaryDirectory() as folder:
            data = Path(folder)
            games = [dict(Id=str(i), Name=str(i)) for i in range(3)]
            (data / 'library.json').write_text(json.dumps(games))
            window = LibraryWindow(data)
            window.resize(1400, 1000)
            window.toggle_compact_library(True)
            self.assertTrue(window.compact_library)
            window.list.item(1).setSelected(True)
            self.assertTrue(window.compact_library)
            self.assertTrue(window.prefer_compact_library)
            self.assertEqual(window.list.item(0).text(), '')
            for identity in ('0', '1'):
                self.assertGreater(window.list.row_animations[identity].endValue(), 64)
            self.assertEqual(window.list.row_widths.get('2', 0), 0)
            window.refresh_library()
            self.assertTrue(window.compact_library)
            self.assertEqual(len(window.list.selectedItems()), 2)
            window.list.item(1).setSelected(False)
            self.assertTrue(window.compact_library)
            self.assertTrue(window.prefer_compact_library)
            self.assertEqual(window.list.row_animations['1'].endValue(), 0)
            self.assertEqual(window.list.row_animations['0'].endValue(), 64)
            window.close()

    def test_sidebar_transition_preserves_expanded_row_width_when_reversed(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from playlite.app import LibraryWindow
        from PyQt6.QtTest import QTest
        with TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'library.json').write_text(json.dumps([dict(Id=str(i), Name='Example game ' + str(i)) for i in range(3)]))
            window = LibraryWindow(data)
            window.resize(1400, 1000)
            window.toggle_compact_library(True)
            window.show()
            QTest.qWait(30)
            window.toolbar_launch_settled = True
            window.list.item(1).setSelected(True)
            for animation in window.list.row_animations.values():
                animation.setCurrentTime(animation.duration())
            start = dict(window.list.row_widths)
            window.toggle_compact_library(False)
            self.assertEqual(window.list.row_widths['0'], start['0'])
            self.assertEqual(window.list.row_widths['1'], start['1'])
            window.library_animation.setCurrentTime(160)
            midway = dict(window.list.row_widths)
            window.toggle_compact_library(True)
            self.assertEqual(window.list.row_widths['0'], midway['0'])
            self.assertEqual(window.list.row_widths['1'], midway['1'])
            window.library_animation.setCurrentTime(window.library_animation.duration())
            self.assertTrue(window.compact_library)
            for index in (0, 1):
                game = window.list.item(index).data(Qt.ItemDataRole.UserRole)
                self.assertEqual(window.list.row_widths[game['Id']], window.list.expanded_row_width(game))
            self.assertEqual(window.list.row_widths.get('2', 0), 0)
            window.close()
