import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtWidgets import QApplication, QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QFileDialog
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch
from playlite.ui_layout import configure_dialog, scroll_dialog_body
from playlite.settings import SettingsDialog
from playlite.ui_style import PathButton

APP = QApplication.instance() or QApplication([])


class LayoutWorkflowTests(unittest.TestCase):
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
