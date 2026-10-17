import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tools.import_snapshot import import_snapshot


class SnapshotImportTests(unittest.TestCase):
    def test_invalid_ids_and_duplicates_are_rejected_before_writes(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            export = root / 'export.json'
            destination = root / 'data'
            for games in ([{'Id': '../escape', 'Name': 'Bad'}],
                          [{'Id': 'same', 'Name': 'A'}, {'Id': 'same', 'Name': 'B'}]):
                export.write_text(json.dumps(games))
                with self.assertRaises(ValueError):
                    import_snapshot(export, root, destination)
                self.assertFalse(destination.exists())

    def test_explicit_replace_and_failed_commit_preserve_existing_data(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            destination = root / 'data'
            destination.mkdir()
            library = destination / 'library.json'
            original = '[{"Id":"old","Name":"Keep"}]'
            library.write_text(original)
            artwork = destination / 'artwork/game'
            artwork.mkdir(parents=True)
            (artwork / 'Icon.png').write_bytes(b'existing art')
            source = root / 'image.png'
            source.write_bytes(b'imported artwork')
            export = root / 'export.json'
            export.write_text(json.dumps([{'Id': 'game', 'Name': 'New', 'Icon': 'image.png'}]))
            with self.assertRaisesRegex(ValueError, '--replace'):
                import_snapshot(export, root, destination)
            with patch('tools.import_snapshot.atomic_json', side_effect=OSError('disk full')):
                with self.assertRaises(OSError):
                    import_snapshot(export, root, destination, replace=True)
            self.assertEqual(library.read_text(), original)
            self.assertEqual(list(artwork.iterdir()), [artwork / 'Icon.png'])
            self.assertEqual((artwork / 'Icon.png').read_bytes(), b'existing art')
            games = import_snapshot(export, root, destination, replace=True)
            self.assertEqual(json.loads(library.read_text()), games)
            self.assertEqual((destination / games[0]['Icon']).read_bytes(), b'imported artwork')

    def test_artwork_outside_export_root_is_not_imported(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = root / 'files'
            files.mkdir()
            (root / 'private.txt').write_text('private')
            (files / 'alias').symlink_to(root / 'private.txt')
            export = root / 'export.json'
            export.write_text(json.dumps([{'Id': 'game', 'Name': 'New', 'Icon': 'alias'}]))
            games = import_snapshot(export, files, root / 'data')
            self.assertIsNone(games[0]['Icon'])
