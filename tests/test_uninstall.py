import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from playlite.ownership import record_tree

spec = importlib.util.spec_from_file_location('playlite_uninstall', Path(__file__).resolve().parents[1] / 'uninstall.py')
uninstall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(uninstall)


class UninstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.home = Path(temporary.name)
        self.data = self.home / '.local/share/playlite'
        self.data.mkdir(parents=True)
        for folder in ('runtime', 'steam-runtime'):
            (self.data / folder).mkdir()
            (self.data / folder / 'file').write_text('retained data')
        record_tree(self.data / 'runtime')
        (self.data / 'library.json').write_text('library')
        (self.home / 'external-game').mkdir()
        (self.home / 'external-game/game.exe').write_text('download')
        binary = self.home / '.local/bin'
        binary.mkdir(parents=True)
        (binary / 'playlite').symlink_to(self.data / 'runtime/bin/playlite')
        (binary / 'playlite-cli').symlink_to(self.data / 'runtime/bin/playlite-cli')
        environment = {'XDG_DATA_HOME': str(self.home / '.local/share'), 'XDG_CONFIG_HOME': str(self.home / '.config'), 'XDG_CACHE_HOME': str(self.home / '.cache'), 'XDG_STATE_HOME': str(self.home / '.local/state'), 'PLAYLITE_BIN_DIR': str(binary)}
        for mock in (patch.dict(os.environ, environment), patch.object(uninstall.Path, 'home', return_value=self.home), patch.object(uninstall, 'running_playlite', return_value=False), patch.object(uninstall.shutil, 'which', return_value=None)):
            mock.start()
            self.addCleanup(mock.stop)

    def test_default_preserves_data(self):
        self.assertEqual(uninstall.main([]), 0)
        self.assertFalse((self.data / 'runtime').exists())
        self.assertFalse((self.home / '.local/bin/playlite').exists())
        self.assertTrue((self.data / 'library.json').exists())
        self.assertTrue((self.data / 'steam-runtime/file').exists())

    def test_keep_plugins_retains_code_and_cleanup_registration(self):
        import json
        plugin=self.data/'plugins/example';plugin.mkdir(parents=True)
        (plugin/'manifest.json').write_text(json.dumps(dict(id='Example')))
        (plugin/'plugin.py').write_text('plugin code');record_tree(plugin)
        registration=self.data/'plugin-cleanup/Example';registration.mkdir(parents=True)
        (registration/'manifest.json').write_text(json.dumps(dict(id='Example')));record_tree(registration)
        self.assertEqual(uninstall.main(['--keep-settings','--keep-plugins']),0)
        self.assertTrue((plugin/'plugin.py').exists())
        self.assertTrue((registration/'manifest.json').exists())
        self.assertFalse((self.data/'runtime').exists())

    def test_dry_run_changes_nothing(self):
        self.assertEqual(uninstall.main(['--dry-run', '--purge-data', '--purge-secrets']), 0)
        self.assertTrue((self.data / 'runtime/file').exists())
        self.assertTrue((self.home / '.local/bin/playlite').is_symlink())

    def test_purge_preserves_external_games_and_repository(self):
        (self.data / 'game-link').symlink_to(self.home / 'external-game', target_is_directory=True)
        self.assertEqual(uninstall.main(['--purge-data']), 0)
        self.assertTrue(self.data.exists())
        self.assertFalse((self.data / 'library.json').exists())
        self.assertTrue((self.home / 'external-game/game.exe').exists())
        self.assertTrue(Path(uninstall.__file__).exists())

    def test_steam_only_preserves_app(self):
        self.assertEqual(uninstall.main(['--steam-only', '--purge-data']), 0)
        self.assertTrue((self.data / 'steam-runtime').exists())
        self.assertTrue((self.data / 'runtime/file').exists())
        self.assertTrue((self.data / 'library.json').exists())

    def test_running_app_prevents_removal(self):
        with patch.object(uninstall, 'running_playlite', return_value=True):
            with self.assertRaises(SystemExit):
                uninstall.main([])
        self.assertTrue((self.data / 'runtime/file').exists())

    def test_repo_launcher_is_preserved(self):
        launcher = self.home / '.local/bin/playlite'
        launcher.unlink()
        launcher.write_text('#!/bin/sh\ncd /repo/playlite\npython3 -m playlite')
        dev = self.home / '.local/bin/playlite-dev'
        dev.symlink_to('/repo/run-dev.sh')
        self.assertEqual(uninstall.main(['--purge-data']), 0)
        self.assertTrue(launcher.exists())
        self.assertTrue(dev.is_symlink())

    def test_plugin_owned_resource_cleanup_hook_and_dry_run(self):
        import json
        plugin=self.data/'plugins/example';plugin.mkdir(parents=True)
        (plugin/'manifest.json').write_text(json.dumps(dict(id='Example',uninstall_hook='cleanup.py')))
        (plugin/'cleanup.py').write_text("def cleanup(data, config, args, remove, run, docker_action, failures):\n    remove(data/'example-resource')\n")
        resource=self.data/'example-resource';resource.write_text('owned')
        self.assertEqual(uninstall.main(['--dry-run']),0)
        self.assertTrue(resource.exists())
        self.assertEqual(uninstall.main([]),0)
        self.assertFalse(resource.exists())

    def test_global_uninstall_removes_managed_plugins_only(self):
        managed=self.data/'plugins/managed';managed.mkdir(parents=True)
        (managed/'plugin.py').write_text('installed')
        record_tree(managed)
        (managed/'user-note.txt').write_text('external addition')
        manual=self.data/'plugins/manual';manual.mkdir()
        (manual/'plugin.py').write_text('manual plugin')
        self.assertEqual(uninstall.main([]),0)
        self.assertFalse((managed/'plugin.py').exists())
        self.assertTrue((managed/'user-note.txt').exists())
        self.assertTrue((manual/'plugin.py').exists())

    def test_settings_choice_preserves_library_and_external_files(self):
        settings = self.home / '.config/Playlite/Lutris.conf'
        settings.parent.mkdir(parents=True)
        settings.write_text('preferences')
        import json
        plugin=self.data/'plugins/example';plugin.mkdir(parents=True)
        (plugin/'manifest.json').write_text(json.dumps(dict(id='Example',settings_groups=['Lutris'])))
        external = settings.parent / 'OtherApp.conf'
        external.write_text('external')
        (self.data / 'ui.ini').write_text('preferences')
        self.assertEqual(uninstall.main(['--dry-run', '--remove-settings']), 0)
        self.assertTrue(settings.exists())
        self.assertEqual(uninstall.main(['--remove-settings']), 0)
        self.assertFalse(settings.exists())
        self.assertFalse((self.data / 'ui.ini').exists())
        self.assertTrue((self.data / 'library.json').exists())
        self.assertTrue(external.exists())

    def test_retained_cleanup_runs_after_plugin_was_removed(self):
        import json
        registration = self.data / 'plugin-cleanup/Example'
        registration.mkdir(parents=True)
        (registration / 'manifest.json').write_text(json.dumps(dict(id='Example', uninstall_hook='cleanup.py')))
        (registration / 'cleanup.py').write_text("def cleanup(data, config, args, remove, run, docker_action, failures):\n    remove(data/'retained-resource')\n")
        record_tree(registration)
        resource = self.data / 'retained-resource'
        resource.write_text('owned')
        self.assertEqual(uninstall.main([]), 0)
        self.assertFalse(resource.exists())
        self.assertFalse(registration.exists())
