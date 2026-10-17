import importlib.util
import os
import runpy
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zipfile import ZipFile

from playlite.desktop import host_environment

spec = importlib.util.spec_from_file_location('workspace_checks', Path(__file__).resolve().parents[1] / 'tools/check_workspace.py')
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)


class IsolatedProfileTests(unittest.TestCase):
    def test_fixture_copy_rejects_escape_through_a_symlinked_parent(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkout = root / 'playlite-plugin-example'; checkout.mkdir()
            (checkout / 'manifest.json').write_text('{}')
            outside = root / 'outside'; outside.mkdir()
            (outside / 'plugin.py').write_text('raise RuntimeError("external code")')
            (checkout / 'code').symlink_to(outside, target_is_directory=True)
            with patch.object(checks, 'CORE', root / 'core'), \
                    patch('subprocess.check_output', return_value=b'code/plugin.py\0'):
                with self.assertRaisesRegex(ValueError, 'must not contain symlinks'):
                    checks.copy_plugin_fixtures(root / 'fixtures')
            self.assertFalse((root / 'fixtures').exists())

    def test_fixture_installation_refuses_a_normal_desktop_profile(self):
        script = Path(__file__).resolve().parents[2] / 'playlite-plugin-image-studio/tools/prepare_test_plugins.py'
        if not script.exists():
            self.skipTest('Sibling plugin source is unavailable')
        with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'argv', [str(script), '/unused/core']), \
                patch('subprocess.run') as run:
            with self.assertRaisesRegex(RuntimeError, 'requires PLAYLITE_PROFILE=test'):
                runpy.run_path(str(script))
        run.assert_not_called()

    def test_plugin_release_excludes_untracked_files_and_symlinks(self):
        builder = Path(__file__).resolve().parents[2] / 'playlite-plugin-steam-metadata/tools/build_release.py'
        if not builder.exists():
            self.skipTest('Sibling plugin source is unavailable')
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'tools').mkdir()
            script = root / 'tools/build_release.py'
            script.write_bytes(builder.read_bytes())
            (root / 'manifest.json').write_text('{}')
            (root / 'plugin.py').write_text('pass\n')
            (root / 'credentials.json').write_text('private')
            (root / 'linked.py').symlink_to(root / 'credentials.json')
            with patch('subprocess.check_output', return_value=b'manifest.json\0plugin.py\0linked.py\0'):
                runpy.run_path(str(script))
            with ZipFile(root / 'dist/plugin.zip') as archive:
                self.assertEqual(set(archive.namelist()), {'manifest.json', 'plugin.py'})

    def test_host_restore_helpers_cannot_fall_back_to_real_home(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            inherited = dict(HOME='/desktop', XDG_DATA_HOME='/desktop/data',
                             PLAYLITE_HOST_HOME='/desktop', PLAYLITE_STEAM_VM_ROOT='/desktop/vm',
                             PLAYLITE_IGDB_CLIENT_SECRET='private', GH_TOKEN='private',
                             WINEPREFIX='/desktop/prefix', PYTHONPATH='/desktop/python',
                             DBUS_SESSION_BUS_ADDRESS='desktop-session')
            with patch.dict(os.environ, inherited, clear=True):
                environment = checks.isolated_environment(root)
            environment['PLAYLITE_PROFILE'] = 'repo'
            with patch.dict(os.environ, environment, clear=True), \
                    patch('playlite.desktop.pwd.getpwuid', side_effect=AssertionError('Real home lookup')):
                restored = host_environment()
            for name in ('HOME', 'XDG_DATA_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_STATE_HOME', 'XDG_RUNTIME_DIR'):
                self.assertTrue(Path(environment[name]).is_relative_to(root))
                self.assertTrue(Path(restored[name]).is_relative_to(root))
            for name in ('PLAYLITE_STEAM_VM_ROOT', 'PLAYLITE_IGDB_CLIENT_SECRET', 'GH_TOKEN',
                         'WINEPREFIX', 'DBUS_SESSION_BUS_ADDRESS'):
                self.assertNotIn(name, environment)

    def test_profiles_do_not_share_paths_or_outlive_their_temporary_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = checks.isolated_environment(root / 'first')
            second = checks.isolated_environment(root / 'second')
            for name in ('HOME', 'PLAYLITE_HOST_HOME', 'XDG_RUNTIME_DIR', 'XDG_DATA_HOME'):
                self.assertNotEqual(first[name], second[name])
                self.assertTrue(Path(first[name]).is_dir())
        self.assertFalse(root.exists())
