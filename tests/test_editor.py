from plugin_test_support import require_plugin
require_plugin('Lutris')
import copy
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QImage, QColor
from playlite.editor import MetadataEditor, save_game


class MetadataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(['playlite'])

    def setUp(self):
        self.directory = TemporaryDirectory()
        self.data = Path(self.directory.name) / 'library'
        self.data.mkdir()
        self.game = {'Id': 'test-game', 'Name': 'Original', 'Description': '<p>Original</p>',
                     'Developers': ['Studio, Inc.'], 'Features': ['Single Player'],
                     'ReleaseDate': {'ReleaseDate': '2026-8-27'}, 'Links': [],
                     'LutrisId': '18', 'UnknownFutureField': {'keep': True}}
        self.original = copy.deepcopy(self.game)
        (self.data / 'library.json').write_text(json.dumps([self.game]))
        self.editor = MetadataEditor(self.game, self.data)

    def tearDown(self):
        self.editor.close()
        self.directory.cleanup()

    def test_images_fit_small_window_and_icon_studio_is_disabled(self):
        from PyQt6.QtWidgets import QTabWidget, QPushButton, QScrollArea
        from playlite.providers import discover_plugins
        image = QImage(600, 900, QImage.Format.Format_RGB32)
        image.fill(QColor('red'))
        path = self.data / 'cover.png'
        image.save(str(path))
        self.editor.media['CoverImage'].setText(str(path))
        tabs = self.editor.findChild(QTabWidget)
        tabs.setCurrentIndex(2)
        self.editor.resize(1000, 650)
        self.editor.show()
        self.app.processEvents()
        self.assertEqual(self.editor.height(), 650)
        self.assertFalse(tabs.widget(2).findChildren(QScrollArea))
        cover = self.editor.media['CoverImage'].parent()
        background = self.editor.media['BackgroundImage'].parent()
        header = self.editor.media['HeaderImage'].parent()
        self.assertGreater(cover.height(), header.height())
        self.assertGreater(background.width(), header.width())
        pixmap = cover.preview.pixmap()
        self.assertFalse(pixmap.isNull())
        self.assertLessEqual(pixmap.width(), cover.preview.width())
        self.assertLessEqual(pixmap.height(), cover.preview.height())
        self.assertAlmostEqual(pixmap.width() / pixmap.height(), 2 / 3, delta=0.01)
        self.assertNotIn('IconStudio', discover_plugins())
        self.assertIn('IconStudio', discover_plugins(include_disabled=True))
        self.assertFalse(any(button.text() == 'Icon Studio…' for button in self.editor.findChildren(QPushButton)))

    def test_installation_browse_buttons_and_add_game_field_order(self):
        from PyQt6.QtWidgets import QPushButton, QFormLayout
        form = self.editor.installation_widget.layout()
        labels = [form.itemAt(row, QFormLayout.ItemRole.LabelRole).widget().text()
                  for row in range(form.rowCount())]
        self.assertEqual(labels, ['Installation folder'])
        with patch('playlite.manual_installation.choose_directory', return_value='/games/install'):
            self.editor.findChild(QPushButton, 'browseInstallDirectory').click()
        self.assertEqual(self.editor.fields['InstallDirectory'].text(), '/games/install')
        details = self.editor.play_actions.cards[0].settings
        self.assertEqual(set(details.fields), {'Executable', 'Prefix', 'Arguments', 'InstallDirectory'})
        details.fields['Executable'].setText('/games/install/game.exe')
        details.fields['Prefix'].setText('/games/prefix')
        action = self.editor.collect()['PlayActions'][0]
        self.assertEqual(action['Executable'], '/games/install/game.exe')
        self.assertEqual(action['Prefix'], '/games/prefix')

    def test_full_description_html_round_trip(self):
        content = '<h2>Story</h2><p>Full text</p><img src="https://shared.fastly.steamstatic.com/story.png">'
        self.editor.apply_metadata({'FullDescription': content})
        self.assertEqual(self.editor.full_description.toPlainText(), content)
        self.assertEqual(self.editor.collect()['FullDescription'], content)

    def test_round_trip_and_metadata_changes(self):
        self.editor.fields['Name'].setText('Updated')
        self.editor.fields['Publishers'].setText('Publisher A')
        self.editor.fields['Genres'].setPlainText('Adventure\nRPG')
        self.editor.fields['Platforms'].setPlainText('Linux')
        self.editor.fields['Features'].setPlainText('Single Player\nController support')
        self.editor.add_link('Website', 'https://example.com/game')
        updated = self.editor.collect()
        saved = save_game(self.data, [self.game], updated)
        self.assertEqual(saved, json.loads((self.data / 'library.json').read_text()))
        self.assertEqual(saved[0]['Developers'], 'Studio, Inc.')
        self.assertEqual(saved[0]['Publishers'], 'Publisher A')
        self.assertEqual(saved[0]['Platforms'], ['Linux'])
        self.assertEqual(saved[0]['ReleaseDate'], {'ReleaseDate': '2026-08-27'})
        self.assertEqual(saved[0]['UnknownFutureField'], {'keep': True})
        self.assertEqual(json.loads((self.data / 'library.json.bak').read_text()), [self.original])
        self.assertEqual(self.game, self.original)

    def test_compact_lists_and_ordered_links_preserve_edits(self):
        field = self.editor.fields['Developers']
        self.assertEqual(field.text(), 'Studio, Inc.')
        field.setText('Second studio')
        self.editor.add_link('First', 'https://example.com/first')
        self.editor.add_link('Second', 'https://example.com/second')
        self.editor.links.move(self.editor.links.rows[1], -1)
        self.editor.links.rows[0][1].setText('Updated second')
        updated = self.editor.collect()
        self.assertEqual(updated['Developers'], 'Second studio')
        self.assertEqual([link['Name'] for link in updated['Links']], ['Updated second', 'First'])
        self.editor.links.remove(self.editor.links.rows[1])
        self.assertEqual(len(self.editor.collect()['Links']), 1)
        self.editor.apply_metadata({'Links': [{'Name': 'Replacement', 'Url': 'https://example.com/new'}],
                                    'Features': ['Single player', 'Controller support']})
        self.assertEqual(self.editor.collect()['Links'][0]['Name'], 'Replacement')
        self.assertEqual(self.editor.collect()['Features'], ['Single player', 'Controller support'])

    def test_header_background_separation_preserves_legacy_header(self):
        image = QImage(80, 30, QImage.Format.Format_RGB32)
        image.fill(QColor('red'))
        header = self.data / 'old-header.png'
        image.save(str(header))
        legacy = dict(self.game, BackgroundImage='old-header.png')
        editor = MetadataEditor(legacy, self.data)
        self.assertEqual(editor.media['HeaderImage'].text(), str(header))
        self.assertEqual(editor.media['BackgroundImage'].text(), '')
        background = self.data / 'new-background.png'
        image.fill(QColor('blue'))
        image.save(str(background))
        editor.media['BackgroundImage'].setText(str(background))
        saved = save_game(self.data, [legacy], editor.collect())[0]
        self.assertEqual(saved['HeaderImage'], 'artwork/test-game/header.png')
        self.assertEqual(saved['BackgroundImage'], 'artwork/test-game/background.png')
        reopened = MetadataEditor(saved, self.data)
        reopened.media['HeaderImage'].clear()
        updated = reopened.collect()
        self.assertIsNone(updated['HeaderImage'])
        self.assertEqual(updated['BackgroundImage'], str(self.data / 'artwork/test-game/background.png'))
        reopened.reject()
        editor.reject()

    def test_recalculate_installation_size_updates_saved_editor_value(self):
        from PyQt6.QtCore import QEventLoop, QTimer
        folder = Path(self.directory.name) / 'game'
        folder.mkdir()
        (folder / 'main.bin').write_bytes(b'x' * 1024)
        nested = folder / 'nested'
        nested.mkdir()
        (nested / 'data.bin').write_bytes(b'x' * 2048)
        (folder / 'duplicate').symlink_to(folder / 'main.bin')
        self.editor.fields['InstallDirectory'].setText(str(folder))
        self.editor.recalculate_size()
        loop = QEventLoop()
        self.editor.size_task.signals.succeeded.connect(loop.quit)
        self.editor.size_task.signals.failed.connect(loop.quit)
        QTimer.singleShot(5000, loop.quit)
        loop.exec()
        self.assertTrue(self.editor.recalculate_button.isEnabled())
        self.assertEqual(self.editor.collect()['InstallSize'], 3072)
        saved = save_game(self.data, [self.game], self.editor.collect())[0]
        reopened = MetadataEditor(saved, self.data)
        self.assertEqual(reopened.fields['InstallSize'].text(), '3072')
        reopened.reject()

    def test_cancel_leaves_library_unchanged(self):
        self.editor.fields['Name'].setText('Discarded')
        self.editor.reject()
        self.assertIsNone(self.editor.result_game)
        self.assertEqual(json.loads((self.data / 'library.json').read_text()), [self.original])

    def test_invalid_metadata_keeps_editor_open(self):
        for key, value in [('ReleaseDate', '2026-02-30'), ('UserScore', '101'),
                           ('InstallDirectory', 'relative/path')]:
            before = self.editor.fields[key].text()
            self.editor.fields[key].setText(value)
            with self.assertRaises(ValueError):
                self.editor.collect()
            self.editor.fields[key].setText(before)
        self.editor.add_link('Invalid', 'javascript:alert(1)')
        self.editor.save()
        self.assertIsNone(self.editor.result_game)
        self.assertTrue(self.editor.error.text())

    def test_artwork_is_copied_and_can_be_cleared(self):
        source = Path(self.directory.name) / 'cover.png'
        image = QImage(40, 60, QImage.Format.Format_RGB32)
        image.fill(QColor('red'))
        image.save(str(source))
        original_bytes = source.read_bytes()
        self.editor.media['CoverImage'].setText(str(source))
        saved = save_game(self.data, [self.game], self.editor.collect())[0]
        self.assertEqual((self.data / saved['CoverImage']).read_bytes(), original_bytes)
        self.assertEqual(source.read_bytes(), original_bytes)
        reopened = MetadataEditor(saved, self.data)
        reopened.media['CoverImage'].clear()
        self.assertIsNone(reopened.collect()['CoverImage'])
        reopened.close()

    def test_artwork_replaces_standard_filename(self):
        source = self.data / 'chosen.png'
        image = QImage(16, 16, QImage.Format.Format_ARGB32)
        image.fill(QColor('red'))
        image.save(str(source))
        updated = dict(self.game, Icon=str(source))
        saved = save_game(self.data, [self.game], updated)
        self.assertEqual(saved[0]['Icon'], 'artwork/test-game/icon.png')
        image.fill(QColor('blue'))
        image.save(str(source))
        saved = save_game(self.data, saved, dict(saved[0], Icon=str(source)))
        target = self.data / saved[0]['Icon']
        self.assertEqual(QImage(str(target)).pixelColor(0, 0), QColor('blue'))
        self.assertEqual([p.name for p in target.parent.iterdir()], ['icon.png'])

    def test_write_failure_preserves_original(self):
        updated = self.editor.collect()
        updated['Name'] = 'Failed edit'
        with patch.object(Path, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                save_game(self.data, [self.game], updated)
        self.assertEqual(json.loads((self.data / 'library.json').read_text()), [self.original])
        self.assertEqual(self.game, self.original)


if __name__ == '__main__':
    unittest.main()
