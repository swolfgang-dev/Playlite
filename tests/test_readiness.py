from types import SimpleNamespace
import unittest
from playlite.readiness import grouped_actions

class MenuTests(unittest.TestCase):
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
