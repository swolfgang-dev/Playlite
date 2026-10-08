import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from PIL import Image
from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
from playlite.background_art import prepare
from playlite.settings import SettingsDialog


APP = QApplication.instance() or QApplication([])


class BackgroundAppearanceTests(unittest.TestCase):
    def test_darkening_endpoints_and_existing_brightness(self):
        with TemporaryDirectory() as directory:
            image = Path(directory) / 'art.png'
            Image.new('RGB', (32, 32), 'white').save(image)
            for darkness, expected in ((0, 255), (84, 41), (100, 0)):
                rendered = prepare(str(image), 0, '#000000', darkness)
                self.assertAlmostEqual(rendered.pixelColor(16, 16).red(), expected, delta=3)

    def test_darkening_save_cancel_and_reopen(self):
        with TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / 'ui.ini'), QSettings.Format.IniFormat)
            dialog = SettingsDialog(settings)
            self.assertEqual(dialog.background_darken.value(), 84)
            dialog.background_darken.setValue(35)
            dialog.reject()
            self.assertFalse(settings.contains('appearance/backgroundDarken'))
            dialog = SettingsDialog(settings)
            dialog.background_darken.setValue(60)
            self.assertEqual(dialog.background_darken_value.text(), '60%')
            dialog.save()
            reopened = SettingsDialog(settings)
            self.assertEqual(reopened.background_darken.value(), 60)
            reopened.reject()
