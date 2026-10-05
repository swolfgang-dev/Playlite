import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication, QListView
from playlite.library import query_games
from playlite.app import LibraryWindow

GAMES = [
    {'Id': 'a', 'Name': 'Alpha', 'Genres': ['RPG'], 'Features': ['Single Player'], 'Developers': ['Studio'],
     'IsInstalled': True, 'Favorite': True, 'ReleaseDate': {'ReleaseDate': '2024-5-28'}, 'Playtime': 80},
    {'Id': 'b', 'Name': 'Beta', 'Genres': ['Action'], 'Features': ['Co-op'], 'Developers': ['Studio'],
     'IsInstalled': False, 'ReleaseDate': {'ReleaseDate': '2023-10-01'}, 'Playtime': 0},
    {'Id': 'c', 'Name': 'Gamma', 'Genres': ['RPG'], 'Hidden': True},
    {'Id': 'd', 'Name': 'Delta', 'Genres': ['RPG'], 'IsInstalled': True},
]


class QueryTests(unittest.TestCase):
    def test_combined_filters_search_and_hidden(self):
        self.assertEqual([g['Id'] for g in query_games(GAMES, filters={'Genres': 'RPG', 'Installed': 'Installed'})], ['a', 'd'])
        self.assertEqual([g['Id'] for g in query_games(GAMES, 'ALP', {'Favorite': True})], ['a'])
        self.assertEqual(len(query_games(GAMES, filters={'ShowHidden': True})), 4)
        self.assertEqual(query_games(GAMES, filters={'Features': 'Missing feature'}), [])

    def test_dates_and_missing_values(self):
        self.assertEqual([g['Id'] for g in query_games(GAMES, sort='ReleaseDate')], ['b', 'a', 'd'])
        self.assertEqual([g['Id'] for g in query_games(GAMES, sort='ReleaseDate', descending=True)], ['a', 'b', 'd'])
        self.assertEqual([g['Id'] for g in query_games(GAMES, sort='Playtime')], ['b', 'a', 'd'])


class LibraryControlsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['playlite'])

    def test_installation_and_play_history_show_saved_values_and_empty_defaults(self):
        from PyQt6.QtWidgets import QFrame, QLabel
        from PyQt6.QtTest import QTest
        with TemporaryDirectory() as directory:
            data = Path(directory)
            game = {'Id': 'example', 'Name': 'Example', 'InstallDirectory': directory,
                    'InstallSize': 1234, 'Added': '2026-10-01', 'Playtime': 3720,
                    'LastActivity': '2026-10-04T14:30:00', 'PlayCount': 7}
            (data / 'library.json').write_text(json.dumps([game, {'Id': 'empty', 'Name': 'Empty'}]))
            window = LibraryWindow(data)
            window.resize(1600, 900)
            window.show()
            QTest.qWait(100)
            window.list.setCurrentRow(next(i for i in range(window.list.count())
                                          if window.list.item(i).text() == 'Example'))
            self.app.processEvents()
            panels = window.content.installation_row.findChildren(QFrame)
            installation = next(p for p in panels if p.property('installationPanel'))
            history = next(p for p in panels if p.property('playHistoryPanel'))
            self.assertLess(history.x(), installation.x())
            self.assertIn('2026-10-01', [v.text() for v in installation.findChildren(QLabel)])
            installation_labels = {v.text(): v for v in installation.findChildren(QLabel)}
            history_labels = {v.text(): v for v in history.findChildren(QLabel)}
            for left, right in [('Folder', 'Play time'), ('Size', 'Last played'), ('Added date', 'Play count')]:
                self.assertEqual(installation_labels[left].y(), history_labels[right].y())
            texts = [v.text() for v in history.findChildren(QLabel)]
            for value in ('Play time', '1h 2m', 'Last played', '2026-10-04 14:30', 'Play count', '7'):
                self.assertIn(value, texts)
            window.resize(1000, 900)
            window.split.setSizes([410, 590])
            QTest.qWait(400)
            self.assertLess(window.content.width(), window.content.columns_breakpoint)
            self.assertGreater(installation.y(), history.y())
            self.assertEqual(installation.x(), history.x())
            window.resize(1600, 900)
            QTest.qWait(400)
            self.assertLess(history.x(), installation.x())
            window.list.setCurrentRow(next(i for i in range(window.list.count())
                                          if window.list.item(i).text() == 'Empty'))
            self.app.processEvents()
            panels = window.content.installation_row.findChildren(QFrame)
            installation = next(p for p in panels if p.property('installationPanel'))
            history = next(p for p in panels if p.property('playHistoryPanel'))
            self.assertIn('Unknown', [v.text() for v in installation.findChildren(QLabel)])
            texts = [v.text() for v in history.findChildren(QLabel)]
            for value in ('0s', 'Never', '0'):
                self.assertIn(value, texts)
            window.close()

    def test_links_panel_matches_description_height_and_fits_content_below(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtWidgets import QFrame
        from PyQt6.QtTest import QTest
        from playlite.app import LinksScroll
        from playlite.rich_description import CollapsibleDescription
        with TemporaryDirectory() as directory:
            data = Path(directory)
            cover = QPixmap(600, 900)
            cover.fill(Qt.GlobalColor.blue)
            cover.save(str(data / 'cover.png'))
            game = {'Id': 'example', 'Name': 'Example', 'CoverImage': str(data / 'cover.png'),
                    'FullDescription': '<p>' + 'Description text ' * 100 + '</p>',
                    'Links': [{'Name': f'Link {i}', 'Url': f'https://example.com/{i}'} for i in range(20)]}
            (data / 'library.json').write_text(json.dumps([game]))
            window = LibraryWindow(data)
            window.resize(1600, 900)
            window.show()
            QTest.qWait(100)
            panel = next(frame for frame in window.content.findChildren(QFrame) if frame.property('linksPanel'))
            self.assertEqual(panel.width(), window.content.cover.width())
            self.assertEqual(panel.height(), window.content.findChild(CollapsibleDescription).parentWidget().height())
            description = window.content.findChild(CollapsibleDescription)
            self.assertIs(panel.parentWidget(), description.parentWidget().parentWidget())
            self.assertGreater(panel.x(), description.parentWidget().x())
            description.toggle_expanded()
            description.height_animation.setCurrentTime(175)
            self.app.processEvents()
            self.assertEqual(panel.height(), description.parentWidget().height())
            description.height_animation.setCurrentTime(350)
            self.app.processEvents()
            self.assertEqual(panel.height(), description.parentWidget().height())
            scroll = panel.findChild(LinksScroll)
            self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
            self.assertFalse(scroll.verticalScrollBar().isVisible())
            self.assertTrue(scroll.fades.effect.isEnabled())
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            window.resize(1000, 900)
            window.split.setSizes([410, 590])
            QTest.qWait(400)
            self.assertLess(window.content.width(), window.content.columns_breakpoint)
            self.assertTrue(window.content.cover.isHidden())
            self.assertGreaterEqual(panel.y(), description.parentWidget().geometry().bottom())
            self.assertEqual(panel.width(), panel.parentWidget().width())
            self.assertEqual(scroll.height(), scroll.flow.heightForWidth(scroll.viewport().width()))
            self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
            window.resize(1600, 900)
            QTest.qWait(400)
            self.assertFalse(window.content.cover.isHidden())
            self.assertEqual(panel.width(), window.content.cover.width())
            self.assertEqual(panel.height(), window.content.findChild(CollapsibleDescription).parentWidget().height())
            self.assertGreater(panel.x(), description.parentWidget().x())
            window.close()

    def test_overflow_scrollbar_fades_during_list_opening_animation(self):
        from PyQt6.QtCore import Qt
        from PyQt6.QtTest import QTest
        with TemporaryDirectory() as directory:
            data = Path(directory)
            games = [{'Id': str(i), 'Name': f'Game {i}'} for i in range(40)]
            (data / 'library.json').write_text(json.dumps(games))
            window = LibraryWindow(data)
            window.resize(1200, 600)
            window.show()
            QTest.qWait(80)
            window.toggle_compact_library(True)
            window.library_animation.setCurrentTime(320)
            window.toggle_compact_library(False)
            window.library_animation.setCurrentTime(160)
            self.app.processEvents()
            self.assertGreater(window.list.verticalScrollBar().maximum(), 0)
            self.assertAlmostEqual(window.library_scrollbar_opacity.opacity(), 0.5, places=2)
            window.set_filters_expanded(True)
            self.assertEqual(window.library_scrollbar_opacity.opacity(), 0)
            window.library_animation.setCurrentTime(320)
            self.assertEqual(window.list.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            window.filter_animation.setCurrentTime(240)
            self.app.processEvents()
            self.assertTrue(window.list.verticalScrollBar().isVisible())
            self.assertEqual(window.library_scrollbar_opacity.opacity(), 1)
            window.close()

    def test_switching_games_resets_scroll_and_refresh_preserves_position(self):
        with TemporaryDirectory() as directory:
            data = Path(directory)
            from PyQt6.QtGui import QPixmap, QColor
            header = QPixmap(800, 1000)
            header.fill(QColor('#202020'))
            header.save(str(data / 'header.png'))
            (data / 'library.json').write_text(json.dumps([dict(game, HeaderImage='header.png') for game in GAMES[:2]]))
            window = LibraryWindow(data)
            window.resize(1000, 400)
            window.show()
            for _ in range(5):
                self.app.processEvents()
            bar = window.game_scroll.verticalScrollBar()
            self.assertGreater(bar.maximum(), 0)
            bar.setValue(min(80, bar.maximum()))
            position = bar.value()
            window.select_game(window.list.currentItem())
            for _ in range(5):
                self.app.processEvents()
            self.assertEqual(bar.value(), position)
            other = next(window.list.item(i) for i in range(window.list.count())
                         if window.list.item(i) is not window.list.currentItem())
            window.list.setCurrentItem(other)
            for _ in range(5):
                self.app.processEvents()
            self.assertEqual(bar.value(), 0)
            window.close()

    def test_missing_artwork_does_not_reserve_header_or_cover_space(self):
        from playlite.app import Hero
        from PyQt6.QtWidgets import QLabel
        with TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / 'library.json').write_text(json.dumps([{'Id': 'empty', 'Name': 'Example', 'Description': 'Summary'}]))
            window = LibraryWindow(data)
            window.show()
            for _ in range(4):
                self.app.processEvents()
            self.assertIsNone(window.content.cover)
            self.assertFalse(any(label.text() == 'No cover art' for label in window.content.findChildren(QLabel)))
            hero = window.content.findChild(Hero)
            self.assertTrue(hero.pixmap.isNull())
            self.assertLess(hero.height(), 150)
            self.assertTrue(hero.play_control.isVisible())
            window.game_status_changed('empty', 'Launching')
            self.app.processEvents()
            self.assertGreaterEqual(window.play_button.width(), window.play_button.sizeHint().width())
            self.assertEqual(hero.play_control.x(), hero.height() - hero.play_control.y() - hero.play_control.height())
            window.close()

    def test_narrow_list_hides_names_keeps_tooltips_and_selection(self):
        with TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / 'library.json').write_text(json.dumps(GAMES))
            window = LibraryWindow(data)
            window.list.setCurrentRow(1)
            selected = window.current['Id']
            window.resize(700, 900)
            window.update_compact_library()
            self.assertTrue(window.compact_library)
            self.assertEqual(window.list.item(0).text(), '')
            self.assertEqual(window.list.item(0).toolTip(), '')
            self.assertEqual(window.current['Id'], selected)
            window.resize(1500, 900)
            window.update_compact_library()
            self.assertFalse(window.compact_library)
            self.assertEqual(window.list.item(0).text(), 'Alpha')
            self.assertEqual(window.current['Id'], selected)
            window.close()

    def test_filter_panel_animation_defers_scrollbars_and_right_click_clears(self):
        from PyQt6.QtCore import Qt, QPoint
        from PyQt6.QtTest import QTest
        with TemporaryDirectory() as directory:
            data = Path(directory)
            (data / 'library.json').write_text(json.dumps(GAMES))
            window = LibraryWindow(data)
            window.show()
            QTest.qWait(80)
            self.assertEqual(window.list.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            window.set_filters_expanded(True)
            target = window.filter_animation.endValue()
            window.filter_animation.setCurrentTime(120)
            self.assertGreater(window.filter_panel.height(), 0)
            self.assertLess(window.filter_panel.height(), target)
            self.assertEqual(window.list.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.assertIn('background: transparent', window.game_scroll.verticalScrollBar().styleSheet())
            window.filter_animation.setCurrentTime(240)
            self.assertEqual(window.list.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            genre = window.filter_controls['Genres']
            genre.setCurrentIndex(genre.findData('RPG'))
            self.assertEqual(window.active_filters['Genres'], 'RPG')
            window.filter_button.customContextMenuRequested.emit(QPoint())
            self.assertFalse(any(window.active_filters.values()))
            window.set_filters_expanded(False)
            window.filter_animation.setCurrentTime(240)
            self.assertFalse(window.filter_panel.isVisible())
            window.close()

    def test_compact_scrollbar_space_animates_and_restores_equal_padding(self):
        from playlite.app import LibraryList
        from PyQt6.QtCore import QAbstractAnimation
        view = LibraryList()
        view.compact_enabled = True
        view.resize(80, 400)
        view.update_scrollbar_padding()
        view.show()
        QApplication.processEvents()
        view.toolbar_launch_settled = True
        self.assertEqual(view.width(), 80)
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtCore import Qt, QSize
        for index in range(12):
            item = QListWidgetItem()
            item.setSizeHint(QSize(64, 66))
            item.setData(Qt.ItemDataRole.UserRole, {'Id': str(index), 'Name': str(index)})
            view.addItem(item)
        QApplication.processEvents()
        target = view.compact_width()
        self.assertGreater(target, 80)
        self.assertEqual(view.gutter_animation.state(), QAbstractAnimation.State.Running)
        view.gutter_animation.setCurrentTime(110)
        self.assertGreater(view.width(), 80)
        self.assertLess(view.width(), target)
        view.clear()
        QApplication.processEvents()
        view.gutter_animation.setCurrentTime(220)
        self.assertEqual(view.width(), 80)
        self.assertIn('padding-left: 8px; padding-right: 8px;', view.styleSheet())
        view.close()

    def test_scrollbar_fades_during_compact_gutter_animation(self):
        from PyQt6.QtCore import QAbstractAnimation, QSize, Qt
        from PyQt6.QtWidgets import QListWidgetItem
        from PyQt6.QtTest import QTest
        with TemporaryDirectory() as directory:
            data = Path(directory)
            (data / 'library.json').write_text(json.dumps(GAMES))
            window = LibraryWindow(data)
            window.resize(1200, 600)
            window.toggle_compact_library(True)
            window.show()
            QTest.qWait(100)
            for index in range(40):
                item = QListWidgetItem()
                item.setSizeHint(QSize(64, 66))
                item.setData(Qt.ItemDataRole.UserRole, {'Id': str(index), 'Name': str(index)})
                window.list.addItem(item)
            self.app.processEvents()
            animation = window.list.gutter_animation
            self.assertEqual(animation.state(), QAbstractAnimation.State.Running)
            animation.setCurrentTime(110)
            self.app.processEvents()
            self.assertEqual(window.list.verticalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            self.assertAlmostEqual(window.library_scrollbar_opacity.opacity(), 0.5, places=2)
            animation.setCurrentTime(220)
            self.app.processEvents()
            self.assertTrue(window.list.verticalScrollBar().isVisible())
            self.assertEqual(window.library_scrollbar_opacity.opacity(), 1)
            window.close()

    def test_cover_position_is_immediate_until_launch_has_settled(self):
        from PyQt6.QtWidgets import QWidget, QLabel
        from PyQt6.QtCore import QAbstractAnimation
        from playlite.app import ResponsiveContent
        host = QWidget()
        host.toolbar_launch_settled = False
        content = ResponsiveContent()
        content.setParent(host)
        cover = QLabel(content)
        cover.setFixedSize(190, 285)
        content.cover = cover
        content.resize(500, 500)
        content.update_cover()
        host.show()
        content.resize(800, 500)
        content.update_cover()
        self.assertEqual(content.cover_animation.state(), QAbstractAnimation.State.Stopped)
        self.assertEqual(cover.width(), 190)
        self.assertFalse(cover.isHidden())
        host.toolbar_launch_settled = True
        content.resize(500, 500)
        content.update_cover()
        self.assertEqual(content.cover_animation.state(), QAbstractAnimation.State.Running)
        content.cover_animation.setCurrentTime(320)
        self.assertTrue(cover.isHidden())
        host.close()

    def test_compact_width_animation_can_reverse_without_saving_intermediate_width(self):
        from PyQt6.QtTest import QTest
        with TemporaryDirectory() as directory:
            data = Path(directory)
            (data / 'library.json').write_text(json.dumps(GAMES))
            window = LibraryWindow(data)
            window.resize(1500, 900)
            window.update_compact_library()
            window.show()
            QTest.qWait(80)
            window.update_compact_library()
            initial = window.list.width()
            saved = window.library_widths['list']
            window.toggle_compact_library(True)
            window.library_animation.setCurrentTime(160)
            self.assertTrue(window.list.width_transition)
            self.assertGreater(window.list.width(), 96)
            self.assertLess(window.list.width(), initial)
            window.toggle_compact_library(False)
            QTest.qWait(380)
            self.assertFalse(window.list.width_transition)
            self.assertEqual(window.library_widths['list'], saved)
            self.assertEqual(window.list.maximumWidth(), 16777215)
            window.close()

    def test_compact_rows_animate_independently_without_popups(self):
        from PyQt6.QtTest import QTest
        from PyQt6.QtCore import QSize, Qt
        from PyQt6.QtWidgets import QListWidgetItem, QWidget
        from playlite.app import LibraryList
        host = QWidget()
        host.resize(700, 400)
        view = LibraryList()
        view.setParent(host)
        view.compact_enabled = True
        view.resize(88, 300)
        for game in GAMES[:2]:
            item = QListWidgetItem('')
            item.setData(Qt.ItemDataRole.UserRole, game)
            item.setSizeHint(QSize(64, 66))
            view.addItem(item)
        view.fit_compact_width()
        host.show()
        view.show()
        QTest.qWait(30)
        origin = view.visualItemRect(view.item(0)).topLeft()
        rail_width = view.width()
        view.update_hover(view.visualItemRect(view.item(0)).center())
        QTest.qWait(1100)
        self.assertGreater(view.row_widths['a'], 64)
        self.assertIsNone(view.title_offset(GAMES[0], view.row_widths['a'] - 76))
        self.assertIsNotNone(view.title_offset(GAMES[0], view.row_widths['a'] - 90))
        self.assertEqual(view.width(), rail_width)
        self.assertEqual(view.visualItemRect(view.item(0)).topLeft(), origin)
        self.assertFalse(hasattr(view, 'hover_row'))
        view.update_hover(view.visualItemRect(view.item(1)).center())
        QTest.qWait(1100)
        self.assertEqual(view.row_widths['a'], 64)
        self.assertGreater(view.row_widths['b'], 64)
        view.update_hover(view.visualItemRect(view.item(0)).center())
        self.assertEqual(view.row_widths['a'], 64)
        QTest.qWait(50)
        self.assertGreater(view.row_widths['a'], 64)
        self.assertLess(view.row_widths['a'], view.row_animations['a'].endValue())
        animation = view.row_animations['a']
        self.assertEqual(animation.duration(), 250)
        host.close()

    def test_library_width_persists_without_compact_overwrite(self):
        with TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / 'library.json').write_text(json.dumps(GAMES))
            window = LibraryWindow(data)
            window.resize(1500, 900)
            window.update_compact_library()
            window.split.setSizes([320, 1180])
            window.remember_library_width()
            width = window.library_widths['list']
            window.compact_button.setChecked(True)
            window.remember_library_width()
            self.assertEqual(window.library_widths['list'], width)
            window.close()
            reopened = LibraryWindow(data)
            self.assertEqual(reopened.library_widths['list'], width)
            reopened.close()

    def test_grid_fits_expected_columns_with_real_cover_icons(self):
        from PyQt6.QtCore import QSize
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtWidgets import QListWidgetItem
        from playlite.app import LibraryList, STYLE
        view = LibraryList()
        view.setStyleSheet(STYLE)
        view.resize(600, 600)
        view.setViewMode(QListView.ViewMode.IconMode)
        view.setResizeMode(QListView.ResizeMode.Adjust)
        view.setWrapping(True)
        view.setWordWrap(True)
        view.setUniformItemSizes(True)
        view.setSpacing(0)
        view.setIconSize(QSize(160, 240))
        cover = QPixmap(160, 240)
        cover.fill()
        for index in range(20):
            view.addItem(QListWidgetItem(QIcon(cover), 'A Plague Tale: Requiem'))
        view.show()
        self.app.processEvents()
        view.balance_grid()
        view.doItemsLayout()
        self.app.processEvents()
        from PyQt6.QtTest import QTest
        QTest.qWait(30)
        calls = []
        original = view.doItemsLayout
        def tracked_layout():
            calls.append(True)
            original()
        view.doItemsLayout = tracked_layout
        view.balance_grid()
        QTest.qWait(50)
        self.assertEqual(calls, [])
        columns = max(1, (view.viewport().width() - 16) // 180)
        self.assertEqual(view.visualItemRect(view.item(0)).top(), view.visualItemRect(view.item(columns - 1)).top())
        view.close()

    def test_grid_filters_sort_and_persistence(self):
        with TemporaryDirectory() as tmp:
            data = Path(tmp)
            (data / 'library.json').write_text(json.dumps(GAMES))
            window = LibraryWindow(data)
            window.list.setCurrentRow(1)
            selected = window.current['Id']
            window.view.setCurrentIndex(window.view.findData('grid'))
            self.assertEqual(window.list.viewMode(), QListView.ViewMode.IconMode)
            self.assertEqual(window.current['Id'], selected)
            window.filter_controls['Genres'].setCurrentIndex(window.filter_controls['Genres'].findData('RPG'))
            self.assertEqual(window.list.count(), 2)
            window.sort.setCurrentIndex(window.sort.findData('Playtime'))
            window.order.click()
            self.assertEqual(window.list.item(0).text(), 'Alpha')
            window.close()
            reopened = LibraryWindow(data)
            self.assertTrue(reopened.is_grid)
            self.assertEqual(reopened.list.count(), 2)
            self.assertEqual(reopened.sort.currentData(), 'Playtime')
            self.assertTrue(reopened.order.isChecked())
            reopened.reset_filters()
            self.assertEqual(reopened.list.count(), 3)
            reopened.hidden_filter.setChecked(True)
            self.assertEqual(reopened.list.count(), 4)
            reopened.view.setCurrentIndex(0)
            self.assertEqual(reopened.list.viewMode(), QListView.ViewMode.ListMode)
            reopened.close()


if __name__ == '__main__':
    unittest.main()
