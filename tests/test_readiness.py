from types import SimpleNamespace
import unittest
from playlite.readiness import grouped_actions

class MenuTests(unittest.TestCase):
    def test_failing_plugin_menu_does_not_hide_other_plugin_actions(self):
        def broken(*args):
            raise RuntimeError('broken plugin')
        bad = SimpleNamespace(name='Broken', game_actions=broken)
        good = SimpleNamespace(name='Working', game_actions=lambda *args: [('Run', None)])
        with self.assertLogs(level='ERROR'):
            result = grouped_actions([bad, good], None, [{'Id': 'one'}])
        self.assertEqual(result, [('Tools', [('Working', [('Run', None)])])])

    def test_after_add_hooks_are_isolated_after_successful_commit(self):
        from playlite.add_game import notify_game_added
        from unittest.mock import Mock
        bad = SimpleNamespace(id='Bad', name='Broken', after_game_added=Mock(side_effect=RuntimeError('broken plugin')))
        good = SimpleNamespace(id='Good', name='Working', after_game_added=Mock())
        window = Mock()
        editor = SimpleNamespace(generic_plugins=[bad, good], result_game={'Id': 'one'})
        with self.assertLogs(level='ERROR'):
            notify_game_added(window, editor)
        good.after_game_added.assert_called_once_with(window, editor.result_game, editor)
        self.assertIn('Game added', window.statusBar().showMessage.call_args.args[0])

    def test_plugins_grouped_by_purpose_and_saves_are_flat(self):
        saves=SimpleNamespace(name='Ludusavi Save Backup',action_group='Saves',game_actions=lambda *_:[('Manage saves…',None)])
        tool=SimpleNamespace(name='BepInEx Installer',game_actions=lambda *_:[('Install…',None)])
        groups=grouped_actions([saves,tool],None,[{'Id':'one'}])
        self.assertEqual(groups,[('Saves',[('Manage saves…',None)]),('Tools',[('BepInEx Installer',[('Install…',None)])])])

    def test_nested_tool_menu_connects_leaf_callback(self):
        from PyQt6.QtWidgets import QApplication
        from playlite.app import game_context_menu
        from unittest.mock import Mock
        app=QApplication.instance() or QApplication([])
        callback=Mock()
        menu=game_context_menu(None,None,lambda:None,[('Tools',[('Installer',[('Install…',callback)])])])
        tools=next(a.menu() for a in menu.actions() if a.text()=='Tools')
        tools.actions()[0].menu().actions()[0].trigger()
        callback.assert_called_once()
        menu.close()
