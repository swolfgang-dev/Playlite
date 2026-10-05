import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QTextDocument
from playlite.description_overlap import hide_repeated_sentences

APP = QApplication.instance() or QApplication([])


def plain(html):
    document = QTextDocument()
    document.setHtml(html)
    return document.toPlainText()


class DescriptionOverlapTests(unittest.TestCase):
    def test_rich_sentence_matches_but_other_sentences_keep_formatting(self):
        result = hide_repeated_sentences('<p>Explore <b>the world</b>. Fight monsters!</p>',
            '<p>Explore the world. <i>Discover secrets.</i> Fight monsters!</p><p><a href="https://example.com">More details</a></p>')
        self.assertEqual(plain(result), 'Discover secrets. \nMore details')
        self.assertIn('font-style:italic', result)
        self.assertIn('href="https://example.com"', result)

    def test_complete_overlap_hides_panel(self):
        self.assertEqual(hide_repeated_sentences('Same sentence.', '<p>Same <b>sentence.</b></p>'), '')

    def test_whitespace_entities_and_non_bmp_characters(self):
        result = hide_repeated_sentences('Explore 🚀 &amp; fight. More story.',
            '<p>Explore 🚀 &amp;  fight. Keep this.</p>')
        self.assertEqual(plain(result), 'Keep this.')

    def test_partial_sentence_or_different_case_is_not_identical(self):
        full = '<p>Explore the world with friends. explore the world.</p>'
        self.assertEqual(hide_repeated_sentences('Explore the world.', full), full)

    def test_empty_summary_and_no_overlap_preserve_original_html(self):
        full = '<p><b>Unique text.</b></p>'
        self.assertEqual(hide_repeated_sentences('', full), full)
        self.assertEqual(hide_repeated_sentences('Other text.', full), full)

    def test_duplicate_paragraph_removal_keeps_remaining_list(self):
        result = hide_repeated_sentences('Intro.', '<p>Intro.</p><ul><li>First feature.</li><li>Second feature.</li></ul>')
        self.assertEqual(plain(result), 'First feature.\nSecond feature.')
        self.assertIn('<li ', result)

    def test_general_setting_is_saved_and_restored(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path
        from unittest.mock import patch
        from PyQt6.QtCore import QSettings
        from playlite.settings import SettingsDialog
        with TemporaryDirectory() as directory, patch('playlite.providers.discover_plugins', return_value={}):
            settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            self.assertFalse(dialog.hide_description_overlap.isChecked())
            dialog.hide_description_overlap.setChecked(True)
            dialog.save()
            self.assertTrue(settings.value('descriptions/hideRepeatedSentences', False, type=bool))
            reopened = SettingsDialog(settings)
            self.assertTrue(reopened.hide_description_overlap.isChecked())
            reopened.reject()

    def test_game_view_filters_display_without_changing_saved_text(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from playlite.app import LibraryWindow
        from playlite.rich_description import CollapsibleDescription
        with TemporaryDirectory() as directory:
            data = Path(directory)
            game = dict(Id='overlap', Name='Example', Description='Explore the world.',
                        FullDescription='<p>Explore the world. Discover secrets.</p>')
            library = data / 'library.json'
            library.write_text(json.dumps([game]))
            window = LibraryWindow(data)
            window.game_detection.stop()
            old = window.settings.value('descriptions/hideRepeatedSentences', False, type=bool)
            try:
                for enabled, expected in ((False, 'Explore the world. Discover secrets.'), (True, 'Discover secrets.')):
                    window.settings.setValue('descriptions/hideRepeatedSentences', enabled)
                    window.select_game(window.list.item(0))
                    panel = window.content.findChildren(CollapsibleDescription)[-1]
                    self.assertEqual(panel.description.toPlainText(), expected)
                    self.assertEqual(window.current['FullDescription'], game['FullDescription'])
                self.assertEqual(json.loads(library.read_text())[0]['FullDescription'], game['FullDescription'])
            finally:
                window.settings.setValue('descriptions/hideRepeatedSentences', old)
                window.close()
