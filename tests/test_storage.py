import json
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from playlite.storage import atomic_json


class LibraryLockTests(unittest.TestCase):
    def test_nested_lock_reuses_process_lock_and_releases_after_failure(self):
        # A subprocess gives a deadlock a strict deadline instead of hanging Qt.
        script = '''
import tempfile
from pathlib import Path
from playlite.library_storage import library_lock
with tempfile.TemporaryDirectory() as directory:
    try:
        with library_lock(directory):
            with library_lock(Path(directory) / '.'):
                raise ValueError('rollback')
    except ValueError:
        pass
    with library_lock(directory):
        pass
'''
        subprocess.run([sys.executable, '-c', script], check=True, timeout=5)


class AtomicJsonTests(unittest.TestCase):
    def test_private_creation_and_permission_preserving_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            atomic_json(path, {'name': 'Spelunky — 日本語'})
            self.assertEqual(json.loads(path.read_text())['name'], 'Spelunky — 日本語')
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
            path.chmod(0o640)
            atomic_json(path, [])
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o640)
            atomic_json(path, [], mode=0o600)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_failed_serialization_or_replace_preserves_original_and_cleans_stage(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            path.write_text('original')
            with self.assertRaises(TypeError):
                atomic_json(path, object())
            with patch('playlite.storage.os.replace', side_effect=OSError('full disk')):
                with self.assertRaises(OSError):
                    atomic_json(path, {'new': True})
            self.assertEqual(path.read_text(), 'original')
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_staging_names_do_not_collide_with_other_writers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'data.json'
            other = path.with_suffix('.tmp')
            other.write_text('another operation')
            atomic_json(path, [1])
            self.assertEqual(other.read_text(), 'another operation')
