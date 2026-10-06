from pathlib import Path
import tempfile
import unittest
from playlite.ownership import record_tree,remove_owned,carry_external


class OwnershipTests(unittest.TestCase):
    def test_removal_preserves_untracked_modified_and_external_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'installed';root.mkdir()
            external=Path(directory)/'external';external.write_text('outside')
            (root/'owned').write_text('installed')
            (root/'modified').write_text('installed')
            (root/'link').symlink_to(external)
            record_tree(root)
            (root/'modified').write_text('changed externally')
            (root/'manual').write_text('manual')
            remove_owned(root)
            self.assertFalse((root/'owned').exists())
            self.assertFalse((root/'link').is_symlink())
            self.assertEqual(external.read_text(),'outside')
            self.assertEqual((root/'modified').read_text(),'changed externally')
            self.assertTrue((root/'manual').exists())

    def test_plugin_update_preserves_user_additions(self):
        with tempfile.TemporaryDirectory() as directory:
            previous=Path(directory)/'previous';stage=Path(directory)/'stage'
            previous.mkdir();stage.mkdir()
            (previous/'plugin.py').write_text('old');record_tree(previous)
            (previous/'notes.txt').write_text('manual')
            (stage/'plugin.py').write_text('new')
            carried=carry_external(previous,stage);record_tree(stage,carried)
            remove_owned(stage)
            self.assertEqual((stage/'notes.txt').read_text(),'manual')

    def test_modified_file_conflict_refuses_update(self):
        with tempfile.TemporaryDirectory() as directory:
            previous=Path(directory)/'previous';stage=Path(directory)/'stage'
            previous.mkdir();stage.mkdir()
            (previous/'plugin.py').write_text('old');record_tree(previous)
            (previous/'plugin.py').write_text('manual changes')
            (stage/'plugin.py').write_text('new')
            with self.assertRaises(ValueError):carry_external(previous,stage)
            self.assertEqual((previous/'plugin.py').read_text(),'manual changes')

    def test_receipt_cannot_escape_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'installed';root.mkdir()
            external=Path(directory)/'external';external.write_text('outside')
            (root/'.playlite-owned.json').write_text('{"schema":1,"files":{"../external":{"sha256":"anything"}}}')
            with self.assertRaises(ValueError):remove_owned(root)
            self.assertEqual(external.read_text(),'outside')

    def test_added_dependency_receipt_does_not_adopt_manual_files(self):
        from playlite.ownership import file_inventory,record_added_files
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'core').write_text('owned');record_tree(root)
            (root/'manual').write_text('external')
            before=file_inventory(root)
            (root/'dependency').write_text('installed by pip')
            record_added_files(root,before,{'core'})
            remove_owned(root)
            self.assertTrue((root/'manual').exists())
            self.assertFalse((root/'dependency').exists())

    def test_external_empty_directories_and_copied_receipts_are_preserved(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'installed';root.mkdir()
            (root/'owned').write_text('installed');record_tree(root)
            (root/'manual-empty').mkdir()
            copied=Path(directory)/'manual-copy';shutil.copytree(root,copied)
            with self.assertRaises(ValueError):remove_owned(copied)
            remove_owned(root)
            self.assertTrue((root/'manual-empty').is_dir())
            self.assertTrue((copied/'owned').exists())

    def test_replaced_parent_link_cannot_remove_external_directories(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'installed';root.mkdir()
            (root/'nested/empty').mkdir(parents=True);record_tree(root)
            shutil.rmtree(root/'nested')
            external=Path(directory)/'external';(external/'empty').mkdir(parents=True)
            (root/'nested').symlink_to(external,target_is_directory=True)
            remove_owned(root)
            self.assertTrue((external/'empty').is_dir())
