import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from PIL import Image
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap,QColor,QImage
from PyQt6.QtTest import QTest
from playlite.app import ArtworkPage
from playlite.background_art import prepare
APP=QApplication.instance() or QApplication([])


def pixmap(colour):
    image=QPixmap(160,160);image.fill(QColor(colour));return image


class BackgroundTransitionTests(unittest.TestCase):
    def test_crossfade_and_interrupted_switch_preserve_visible_frame(self):
        page=ArtworkPage();page.resize(160,160);page.show()
        page.background=pixmap('red')
        before=page.grab().toImage().pixelColor(80,80)
        page.transition_background(pixmap('blue'))
        self.assertEqual(page.grab().toImage().pixelColor(80,80),before)
        page.background_fade.setCurrentTime(120)
        middle=page.grab().toImage().pixelColor(80,80)
        self.assertGreater(middle.red(),0);self.assertGreater(middle.blue(),0)
        page.transition_background(pixmap('green'))
        self.assertEqual(page.grab().toImage().pixelColor(80,80),middle)
        page.background_fade.setCurrentTime(240)
        self.assertEqual(page.grab().toImage().pixelColor(80,80),QColor('green'))
        self.assertEqual(page.previous_backgrounds,[])
        page.background_fade.stop();page.close()

    def test_resize_reuses_full_frame_and_loading_keeps_existing_artwork(self):
        with TemporaryDirectory() as directory,patch('playlite.app.QThreadPool') as pool:
            path=Path(directory)/'art.png';Image.new('RGB',(160,160),'blue').save(path)
            page=ArtworkPage();page.resize(160,160);page.background=pixmap('red');original=page.background.cacheKey()
            page.set_background(str(path))
            task=pool.globalInstance.return_value.start.call_args.args[0]
            self.assertEqual(page.background.cacheKey(),original)
            task.signals.succeeded.emit(task.function())
            page.background_fade.setCurrentTime(240)
            key=page.background.cacheKey()
            page.resize(300,160);QTest.qWait(250)
            self.assertEqual(page.background.cacheKey(),key)
            page.set_background(str(path))
            self.assertEqual(pool.globalInstance.return_value.start.call_count,1)
            page.background_fade.stop();page.close()

    def test_display_sizing_preserves_source_edges_instead_of_cropping(self):
        with TemporaryDirectory() as directory:
            path=Path(directory)/'art.png';image=Image.new('RGB',(200,100),'blue')
            image.paste('red',(0,0,30,100));image.paste('green',(170,0,200,100));image.save(path)
            prepared=prepare(str(path),0,'#000000',0,(400,400))
            self.assertEqual((prepared.width(),prepared.height()),(400,200))
            self.assertEqual(prepared.pixelColor(0,100),QColor('red'))
            self.assertEqual(prepared.pixelColor(399,100),QColor('green'))
