import unittest,tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtGui import QImage
from playlite.detail_artwork import load

class ArtworkTests(unittest.TestCase):
    def test_worker_decodes_and_scales_images_without_widgets(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'art.png';image=QImage(1200,1800,QImage.Format.Format_RGB32);image.fill(0xff123456);image.save(str(path))
            with ThreadPoolExecutor(max_workers=1) as pool:header,cover=pool.submit(load,str(path),str(path),1).result()
            self.assertLessEqual(header.height(),1000)
            self.assertLessEqual(cover.width(),190);self.assertLessEqual(cover.height(),295)
            self.assertEqual(cover.pixelColor(0,0).name(),'#123456')
    def test_missing_artwork_returns_empty_images(self):
        header,cover=load('','',1);self.assertTrue(header.isNull());self.assertTrue(cover.isNull())
