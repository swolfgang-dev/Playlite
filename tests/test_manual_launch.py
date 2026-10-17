from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from PyQt6.QtCore import QPoint
from PyQt6.QtWidgets import QApplication, QScrollArea, QWidget, QFormLayout, QToolButton
from playlite.manual_launch import ManualLaunch
from playlite.providers import discover_plugins
from playlite.play_actions import PlayActionsEditor
from playlite.action_setup import ActionSetupDialog

APP = QApplication.instance() or QApplication([])


class ManualLaunchTests(unittest.TestCase):
    def test_integration_row_keeps_full_height_when_advanced_collapses(self):
        provider = ManualLaunch()
        with patch('playlite.providers.discover_plugins', return_value={'Manual': provider}):
            scroll = QScrollArea();scroll.setWidgetResizable(True)
            body = QWidget();form = QFormLayout(body)
            editor = PlayActionsEditor({'PlayActions': [dict(Name='Launch', Integration='Manual', Executable='/usr/bin/true')]}, [provider])
            form.addRow('Play actions', editor);scroll.setWidget(body)
            scroll.resize(650, 190);scroll.show()
            card = editor.cards[0]
            advanced = card.settings.findChild(QToolButton)
            for expanded in (False, True, False):
                advanced.setChecked(expanded)
                for _ in range(15):APP.processEvents()
                row = card.integration.parentWidget()
                self.assertEqual(card.integration.height(), 40)
                self.assertGreaterEqual(row.height(), 40)
                self.assertLessEqual(row.mapTo(row.parentWidget(), QPoint(0, row.height())).y(), row.parentWidget().height())
            scroll.close()

    def test_builtin_available_without_plugins(self):
        with TemporaryDirectory() as folder:
            self.assertIsInstance(discover_plugins(folder)['Manual'], ManualLaunch)

    def test_direct_launch_preserves_arguments_without_shell_expansion(self):
        provider = ManualLaunch()
        with patch('playlite.manual_launch.subprocess.Popen') as launch:
            provider.launch({'Executable': '/usr/bin/printf', 'LaunchArguments': '"hello world" "$(false)"', 'InstallDirectory': '/tmp'})
        launch.assert_called_once_with(['/usr/bin/printf', 'hello world', '$(false)'], cwd='/tmp', start_new_session=True)

    def test_missing_and_nonexecutable_paths_rejected(self):
        provider = ManualLaunch()
        with TemporaryDirectory() as folder:
            path = Path(folder) / 'launcher';path.write_text('#!/bin/sh\nexit 0\n')
            with self.assertRaisesRegex(ValueError, 'execute permission'):
                provider.validate_action({'Executable': str(path)})
            path.chmod(0o755)
            provider.validate_action({'Executable': str(path), 'Arguments': '"quoted argument"'})
            with self.assertRaises(ValueError):provider.validate_action({'Executable': str(path), 'Arguments': '"unterminated'})

    def test_editor_hides_launcher_identity_and_wine_prefix(self):
        provider = ManualLaunch()
        with patch('playlite.providers.discover_plugins', return_value={'Manual': provider}):
            editor = PlayActionsEditor({'PlayActions': [dict(Name='Launch script', Integration='Manual', Executable='/usr/bin/true', Prefix='/old-prefix', GameId='123')]}, [provider])
            card = editor.cards[0]
            self.assertTrue(card.game_id.isHidden())
            self.assertNotIn('Prefix', card.settings.fields)
            action = editor.collect()[0]
            self.assertEqual(action['GameId'], '')
            self.assertEqual(action['Prefix'], '')
            editor.close()

    def test_add_manual_action_needs_no_game_id(self):
        provider = ManualLaunch()
        with TemporaryDirectory() as folder, patch('playlite.providers.discover_plugins', return_value={'Manual': provider}):
            dialog = ActionSetupDialog(dict(Id='existing', Name='Example', PlayActions=[]), Path(folder), [provider], 'Manual')
            dialog.installation_widget.fields['Executable'].setText('/usr/bin/true')
            dialog.save()
            self.assertEqual(dialog.result_action['Integration'], 'Manual')
            self.assertEqual(dialog.result_action['Executable'], '/usr/bin/true')
            self.assertEqual(dialog.result_action['GameId'], '')
            dialog.close()
