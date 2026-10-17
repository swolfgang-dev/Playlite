from pathlib import Path
import tempfile
import unittest

from playlite.action_settings import update_action_files


class ActionSettingsTransactionTests(unittest.TestCase):
    def test_nested_plugin_updates_to_one_file_roll_back_in_reverse_order(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'game.yml';path.write_text('original')
            path.chmod(0o640)
            with self.assertRaisesRegex(OSError, 'library failure'):
                with update_action_files({path: 'mangohud'}, Path.write_text):
                    with update_action_files({path: 'mangohud and mapper'}, Path.write_text):
                        raise OSError('library failure')
            self.assertEqual(path.read_text(), 'original')
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_one_conflict_does_not_prevent_restoring_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'first.yml';first.write_text('first original')
            second = Path(directory) / 'second.yml';second.write_text('second original')
            with self.assertRaisesRegex(ValueError, 'newer changes were preserved'):
                with update_action_files({first: 'first update', second: 'second update'}, Path.write_text):
                    second.write_text('new external edit')
                    raise OSError('library failure')
            self.assertEqual(first.read_text(), 'first original')
            self.assertEqual(second.read_text(), 'new external edit')

    def test_failure_updating_a_later_file_restores_earlier_updates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'game.yml';path.write_text('original')
            missing = Path(directory) / 'missing.yml'
            with self.assertRaises(FileNotFoundError):
                with update_action_files({path: 'updated', missing: 'cannot update'}, Path.write_text):
                    self.fail('An invalid update must not reach the library save.')
            self.assertEqual(path.read_text(), 'original')
