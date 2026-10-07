import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from PyQt6.QtWidgets import QApplication,QDialog,QWidget,QLineEdit
from playlite.providers import IntegrationPlugin,InstallationPlugin
from playlite.manual_installation import ManualInstallation
from playlite.action_setup import ActionSetupDialog
from playlite.play_actions import PlayActionsEditor


class Integration(IntegrationPlugin):
    id='Example';name='Example launcher';action_id_field='ExampleId'
    def validate_action(self,action):
        if not action.get('GameId'):raise ValueError('Select a game ID.')
    def installation_methods(self):return [ImportMethod()]


class ImportMethod(InstallationPlugin):
    id='ImportExample';name='Import from Example'
    def create_editor(self,editor,game):return ManualInstallation().create_editor(editor,game)
    def collect(self,widget,game):
        game=ManualInstallation().collect(widget,game)
        game.update(GameProvider='Example',ExampleId='84',Name='Imported title')
        return game


class ActionSetupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.data=Path(temporary.name);self.provider=Integration()
        self.game=dict(Id='existing',Name='Original title',InstallDirectory='',PlayActions=[dict(Name='Original',Integration='Example',GameId='42')])
        patcher=patch('playlite.providers.discover_plugins',return_value={'Example':self.provider})
        patcher.start();self.addCleanup(patcher.stop)

    def test_dropdown_uses_installation_methods(self):
        editor=PlayActionsEditor(self.game,[self.provider])
        self.assertEqual([a.text() for a in editor.add_button.menu().actions()],['Manual','Import from Example'])
        editor.close()

    def test_manual_validation_and_independent_action(self):
        dialog=ActionSetupDialog(self.game,self.data,[self.provider],'Manual')
        self.assertEqual(dialog.findChild(__import__('PyQt6.QtWidgets',fromlist=['QTabWidget']).QTabWidget).count(),1)
        dialog.save();self.assertNotEqual(dialog.result(),QDialog.DialogCode.Accepted)
        dialog.manual_game_id.setText('84');dialog.save()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.result_action['GameId'],'84')
        self.assertEqual(self.game['PlayActions'][0]['GameId'],'42')
        self.assertEqual(self.game['Name'],'Original title')
        dialog.close()

    def test_import_returns_action_without_replacing_library_metadata(self):
        dialog=ActionSetupDialog(self.game,self.data,[self.provider],'ImportExample')
        dialog.save()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.result_action['Integration'],'Example')
        self.assertEqual(dialog.result_action['GameId'],'84')
        self.assertEqual(dialog.result_action['Name'],'Play Imported title')
        self.assertEqual(self.game['Name'],'Original title')
        dialog.close()

    def test_cancel_does_not_commit_integration_changes(self):
        with patch.object(ImportMethod,'commit',side_effect=lambda widget,game:game) as commit:
            dialog=ActionSetupDialog(self.game,self.data,[self.provider],'ImportExample')
            dialog.reject();commit.assert_not_called()
            dialog=ActionSetupDialog(self.game,self.data,[self.provider],'ImportExample')
            dialog.save();commit.assert_called_once()
            self.assertEqual(dialog.result_action['GameId'],'84')
            dialog.close()

    def test_add_action_retains_game_editor_after_layout_reparenting(self):
        owner=QWidget();owner.data=self.data
        folder=QLineEdit('/games/Example');owner.fields={'InstallDirectory':folder}
        with patch('playlite.providers.discover_plugins',return_value={}):
            actions=PlayActionsEditor(self.game,[self.provider],owner)
        container=QWidget(owner);actions.setParent(container)
        with patch('playlite.action_setup.ActionSetupDialog') as dialog,patch('playlite.lifecycle.run_dialog',return_value=QDialog.DialogCode.Rejected):
            actions.setup_action('Manual')
        args=dialog.call_args.args
        self.assertEqual(args[0]['InstallDirectory'],'/games/Example')
        self.assertEqual(args[1],self.data)
        owner.close()
