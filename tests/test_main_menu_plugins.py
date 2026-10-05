import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PyQt6.QtWidgets import QApplication
from playlite.providers import GenericPlugin
from playlite.app import LibraryWindow

APP=QApplication.instance() or QApplication([])

class MenuPlugin(GenericPlugin):
    id='MenuTest'
    name='Menu Test'
    def __init__(self):self.calls=[]
    def main_menu_actions(self,window):
        return [('Steam Depot Downloader…',lambda:self.calls.append(window))]

class MainMenuTests(unittest.TestCase):
    def test_generic_plugin_main_menu_action_calls_the_plugin(self):
        plugin=MenuPlugin()
        with tempfile.TemporaryDirectory() as directory, patch('playlite.providers.discover_plugins',return_value={'MenuTest':plugin}):
            window=LibraryWindow(Path(directory))
            action=next(a for a in window.logo_menu.actions() if a.text()=='Steam Depot Downloader…')
            action.trigger()
            self.assertEqual(plugin.calls,[window])
            window.game_detection.stop()
            window.close()
