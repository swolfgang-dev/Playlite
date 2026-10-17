import io
import unittest
from unittest.mock import MagicMock, Mock, patch

from PIL import Image
from PyQt6.QtWidgets import QApplication, QDialog, QLabel
from playlite.media import MediaCard

APP = QApplication.instance() or QApplication([])


class MediaDownloadTests(unittest.TestCase):
    def test_late_download_preserves_a_newer_choice_or_closed_editor(self):
        content = io.BytesIO()
        Image.new('RGB', (16, 16)).save(content, format='PNG')
        for close_editor in (False, True):
            with self.subTest(close_editor=close_editor):
                editor = QDialog()
                editor.error = QLabel(editor)
                editor.download_caches = []
                card = MediaCard('Icon', '', editor, 112)
                response = MagicMock()
                response.__enter__.return_value.read.return_value = content.getvalue()
                pool = Mock()
                try:
                    with patch('playlite.media.ask_text', return_value=('https://example.com/image.png', True)), \
                            patch('playlite.media.QThreadPool.globalInstance', return_value=pool):
                        card.from_url()
                    if close_editor:
                        editor.reject()
                    else:
                        card.path.setText('/tmp/a-newer-choice.png')
                    chosen = card.path.text()
                    with patch('playlite.media.urllib.request.urlopen', return_value=response):
                        pool.start.call_args.args[0].run()
                    self.assertEqual(card.path.text(), chosen)
                finally:
                    for cache in editor.download_caches:
                        cache.cleanup()
                    editor.close()
                    card.deleteLater()
