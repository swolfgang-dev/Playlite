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

    def test_all_selected_rows_stop_closing_at_icon_box_width(self):
        view = self.create_list()
        for identity in ('a', 'b'):
            view.row_widths[identity] = 180
            view.animate_row(identity, 0)
            animation = view.row_animations[identity]
            self.assertEqual(animation.endValue(), 64)
            animation.setCurrentTime(animation.duration())
            self.assertEqual(view.row_widths[identity], 64)
        view.item(0).setSelected(False)
        self.assertEqual(view.row_animations['a'].endValue(), 0)
        self.assertEqual(view.row_animations['b'].endValue(), 64)
        view.hide_hover_immediately()

    def test_selecting_a_closing_row_reverses_it_before_it_shrinks_below_box(self):
        view = self.create_list()
        view.item(0).setSelected(False)
        view.row_widths['a'] = 180
        view.animate_row('a', 0)
        view.row_animations['a'].setCurrentTime(900)
        view.item(0).setSelected(True)
        self.assertEqual(view.row_animations['a'].endValue(), 64)
        self.assertGreaterEqual(view.row_widths['a'], 64)
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
