import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog, QLabel
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from playlite.ui_layout import configure_dialog, scroll_dialog_body, insert_form_row_after
from playlite.settings import SettingsDialog
from playlite.ui_style import PathButton

APP = QApplication.instance() or QApplication([])


class LayoutWorkflowTests(unittest.TestCase):
    def test_editor_footer_reflows_without_clipping_save_or_navigation(self):
        from PyQt6.QtCore import QPoint, QRect
        from PyQt6.QtWidgets import QDialogButtonBox
        from playlite.editor import MetadataEditor
        with TemporaryDirectory() as directory, patch('playlite.providers.discover_plugins', return_value={}):
            editor = MetadataEditor({'Id': 'one', 'Name': 'Example'}, Path(directory))
            editor.show()
            buttons = editor.findChild(QDialogButtonBox)
            controls = [editor.previous_tab, editor.next_tab,
                        buttons.button(QDialogButtonBox.StandardButton.Save),
                        buttons.button(QDialogButtonBox.StandardButton.Cancel)]
            for width in (760, 480, 352, 760):
                editor.resize(width, 480)
                for index in range(editor.tabs.count()):
                    editor.tabs.setCurrentIndex(index)
                    for _ in range(4):APP.processEvents()
                    for control in controls:
                        with self.subTest(width=width, tab=index, button=control.text()):
                            rectangle = QRect(control.mapTo(editor, QPoint()), control.size())
                            self.assertTrue(editor.rect().contains(rectangle))
                            self.assertGreaterEqual(control.height(), control.minimumSizeHint().height())
            editor.close()

    def test_footer_stays_visible_as_dynamic_content_scrolls_and_collapses(self):
        from PyQt6.QtWidgets import QDialogButtonBox, QLineEdit, QWidget
        from PyQt6.QtCore import QPoint
        dialog = QDialog(); root = QVBoxLayout(dialog)
        toggle = QPushButton('More options'); toggle.setCheckable(True)
        root.addWidget(toggle)
        section = QWidget(); fields = QVBoxLayout(section)
        for index in range(24):
            fields.addWidget(QLineEdit(f'Option {index}'))
        root.addWidget(section); section.hide()
        toggle.toggled.connect(section.setVisible)
        footer = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(footer)
        scroll = scroll_dialog_body(dialog, footer)
        dialog.resize(520, 320); dialog.show(); APP.processEvents()
        collapsed_height = scroll.widget().minimumSizeHint().height()
        for expanded in (True, False, True):
            toggle.setChecked(expanded)
            for _ in range(3): APP.processEvents()
            self.assertTrue(dialog.rect().contains(footer.geometry()))
            self.assertFalse(scroll.isAncestorOf(footer))
            self.assertEqual(scroll.verticalScrollBar().maximum() > 0, expanded)
            if expanded:
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                last = fields.itemAt(fields.count() - 1).widget()
                self.assertTrue(scroll.viewport().rect().contains(last.mapTo(scroll.viewport(), QPoint(0, last.height() - 1))))
            else:
                self.assertEqual(scroll.widget().minimumSizeHint().height(), collapsed_height)
        dialog.close()

    def test_invalid_footer_does_not_reparent_existing_controls(self):
        dialog = QDialog(); root = QVBoxLayout(dialog)
        control = QPushButton('Keep'); root.addWidget(control)
        with self.assertRaises(ValueError):
            scroll_dialog_body(dialog, QHBoxLayout())
        self.assertIs(control.parentWidget(), dialog)
        self.assertEqual(root.count(), 1)
        dialog.close()

    def test_form_contributions_follow_their_anchor_after_rows_are_inserted(self):
        from PyQt6.QtWidgets import QFormLayout, QLineEdit, QWidget
        host = QWidget(); form = QFormLayout(host)
        anchor = QHBoxLayout(); anchor.addWidget(QLineEdit())
        form.addRow('Path', anchor)
        for index in range(5): form.insertRow(0, QLabel(f'Plugin {index}'))
        contribution = QLineEdit()
        insert_form_row_after(form, anchor, 'Runner', contribution)
        self.assertEqual(form.getWidgetPosition(contribution)[0], form.getLayoutPosition(anchor)[0] + 1)
        host.close()

    def test_scrolling_body_reparents_direct_and_nested_controls(self):
        dialog = QDialog();root = QVBoxLayout(dialog)
        explanation = QLabel('Installer instructions');root.addWidget(explanation)
        nested = QHBoxLayout();browse = QPushButton('Browse');nested.addWidget(browse);root.addLayout(nested)
        footer = QHBoxLayout();close = QPushButton('Close');footer.addWidget(close);root.addLayout(footer)
        scroll = scroll_dialog_body(dialog, footer)
        dialog.resize(700, 450);dialog.show();APP.processEvents()
        self.assertIs(explanation.parentWidget(), scroll.widget())
        self.assertIs(browse.parentWidget(), scroll.widget())
        self.assertIs(close.parentWidget(), dialog)
        self.assertTrue(scroll.widget().isAncestorOf(explanation))
        self.assertTrue(scroll.widget().isAncestorOf(browse))
        dialog.close()

    def test_content_fitting_keeps_default_window_below_full_screen_height(self):
        from unittest.mock import Mock
        from PyQt6.QtCore import QMargins, QRect
        from playlite.app import LibraryWindow
        window = Mock()
        window.default_window_height = 1140
        window.height.return_value = 1100
        window.width.return_value = 1200
        window.game_scroll.viewport.return_value.height.return_value = 1000
        window.content.width.return_value = 1000
        window.content.findChildren.return_value = []
        window.details.totalHeightForWidth.return_value = 4000
        window.page.layout.return_value.contentsMargins.return_value = QMargins(24, 24, 0, 24)
        window.games = [{}]
        window.frameGeometry.return_value.height.return_value = 1100
        window.screen.return_value.availableGeometry.return_value = QRect(0, 0, 3840, 2160)
        LibraryWindow.fit_content_height(window, False)
        window.resize.assert_called_with(1200, 1140)
        window.screen.return_value.availableGeometry.return_value = QRect(0, 0, 1280, 800)
        LibraryWindow.fit_content_height(window, False)
        window.resize.assert_called_with(1200, 720)

    def test_play_chooser_has_room_for_labels_before_showing(self):
        from playlite.add_game import AddGameMethods
        from playlite.ui_layout import install
        install(APP)
        dialog = AddGameMethods([('Play Elden Ring', None),
                                 ('Play Elden Ring - Modded with a longer action name', None)])
        dialog.findChild(QLabel).setText('Choose how to launch this game.')
        sizes = []
        original = dialog.showEvent
        def shown(event):
            sizes.append(dialog.size())
            original(event)
        dialog.showEvent = shown
        dialog.show()
        APP.processEvents()
        self.assertEqual(sizes[0], dialog.size())
        for button in dialog.method_buttons:
            self.assertGreaterEqual(button.width(), button.sizeHint().width())
        dialog.close()

    def test_tall_form_scrolls_without_moving_footer_and_preserves_joined_buttons(self):
        dialog = QDialog(); root = QVBoxLayout(dialog)
        root.addWidget(QPushButton('Long form'))
        footer = QHBoxLayout(); footer.setSpacing(0); close = QPushButton('Close'); footer.addWidget(close); root.addLayout(footer)
        scroll = scroll_dialog_body(dialog, footer)
        configure_dialog(dialog)
        self.assertEqual(root.itemAt(0).widget(), scroll)
        self.assertEqual(root.itemAt(1).layout(), footer)
        self.assertFalse(scroll.isAncestorOf(close))
        self.assertEqual(footer.spacing(), 0)
        native = QFileDialog(); original = native.layout().contentsMargins(); configure_dialog(native)
        self.assertEqual(native.layout().contentsMargins(), original)
        dialog.close(); native.close()

    def test_plugin_search_keeps_the_selected_settings_and_filters_navigation(self):
        with TemporaryDirectory() as directory, patch('playlite.providers.discover_plugins',return_value={}):
            settings=QSettings(str(Path(directory)/'ui.ini'),QSettings.Format.IniFormat)
            dialog=SettingsDialog(settings)
            dialog.plugin_search.setText('Manual')
            selected=dialog.plugin_list.currentItem()
            self.assertEqual(selected.text(),'Manual')
            self.assertEqual(dialog.plugin_tabs.currentIndex(),4)
            header,content=dialog.plugin_sections['Manual']
            self.assertFalse(content.isHidden())
            dialog.plugin_search.clear()
            self.assertEqual(dialog.plugin_list.currentItem(),selected)
            dialog.reject()
            self.assertFalse(settings.contains('installation/defaultMethod'))

    def test_path_button_retains_folder_suffix_and_full_tooltip(self):
        path='/very/long/installation/path/Game Folder'
        button=PathButton(path);button.resize(120,32);button.show();APP.processEvents()
        self.assertEqual(button.toolTip(),path)
        self.assertTrue(button.text().endswith('Game Folder'))
        self.assertNotEqual(button.text(),path)
        button.close()
