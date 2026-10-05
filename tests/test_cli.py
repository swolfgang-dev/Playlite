import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from playlite.cli import main


class CliTests(unittest.TestCase):
    def test_manual_save_and_dry_run(self):
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['--data', str(data), 'manual', '--exe', '/games/Example/game.exe', '--steam-id', '123', '--dry-run']), 0)
            self.assertFalse((data / 'library.json').exists())
            self.assertEqual(json.loads(output.getvalue())['InstallDirectory'], '/games/Example')
            with contextlib.redirect_stdout(io.StringIO()), patch('PyQt6.QtCore.QLockFile') as lock:
                lock.return_value.tryLock.return_value = True
                self.assertEqual(main(['--data', str(data), 'manual', '--name', 'Example']), 0)
            game = json.loads((data / 'library.json').read_text())[0]
            self.assertEqual(game['InstallationMethod'], 'Manual')
            self.assertEqual(game['Platforms'], [])

    def test_invalid_manual_id_does_not_save(self):
        with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['--data', directory, 'manual', '--name', 'Example', '--steam-id', 'bad']), 1)
            self.assertFalse((Path(directory) / 'library.json').exists())
