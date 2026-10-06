import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from playlite import updater

class UpdaterTests(unittest.TestCase):
    def test_repo_cannot_install_updates(self):
        with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE':'repo'}):
            with self.assertRaises(ValueError): updater.prepare_update({})

    def test_verified_installer_is_staged_with_standalone_helper(self):
        import shutil
        script = b'#!/bin/bash\nexit 0\n'
        release = {'assets':[{'name':'SHA256SUMS','browser_download_url':'hashes'}, {'name':'install.sh','browser_download_url':'script'}]}
        with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE':''}), patch.object(updater,'fetch',side_effect=[(hashlib.sha256(script).hexdigest()+'  install.sh\n').encode(),script]):
            directory = updater.prepare_update(release)
        try:
            self.assertEqual((directory/'install.sh').read_bytes(),script)
            self.assertTrue((directory/'updater.py').is_file())
        finally: shutil.rmtree(directory)

    def test_bad_checksum_prevents_staging(self):
        release = {'assets':[{'name':'SHA256SUMS','browser_download_url':'hashes'}, {'name':'install.sh','browser_download_url':'script'}]}
        with patch.dict(updater.os.environ, {'PLAYLITE_PROFILE':''}), patch.object(updater,'fetch',side_effect=[b'wrong  install.sh\n',b'installer']):
            with self.assertRaisesRegex(ValueError,'checksum'):updater.prepare_update(release)

    def test_failed_install_does_not_restart_and_cleans_staging(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as folder:
            directory=Path(folder)/'staged';directory.mkdir()
            with patch.object(updater,'__file__',str(directory/'updater.py')), patch.object(updater.subprocess,'run',return_value=SimpleNamespace(returncode=1)), patch.object(updater.subprocess,'Popen') as launch:
                with self.assertRaises(RuntimeError):updater.run_update(999999999,'v1')
                launch.assert_not_called()
            self.assertFalse(directory.exists())
