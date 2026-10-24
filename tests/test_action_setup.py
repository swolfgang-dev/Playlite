import os
import tempfile
import unittest
from contextlib import contextmanager
import copy
from pathlib import Path
from unittest.mock import patch,Mock
from PyQt6.QtWidgets import QApplication,QDialog,QWidget,QLineEdit
from playlite.providers import IntegrationPlugin,InstallationPlugin
from playlite.installation_fields import InstallationFields as ManualInstallation
from playlite.action_setup import ActionSetupDialog
from playlite.play_actions import PlayActionsEditor


class Integration(IntegrationPlugin):
    id='LutrisIntegration';name='Example launcher';action_id_field='LutrisId'
    def validate_action(self,action):
        if not action.get('GameId'):raise ValueError('Select a game ID.')
    def installation_methods(self):return [ImportMethod()]


class ImportMethod(InstallationPlugin):
    id='ImportExample';name='Import from Example'
    def create_editor(self,editor,game):return ManualInstallation().create_editor(editor,game)
    def collect(self,widget,game):
        game=ManualInstallation().collect(widget,game)
        game.update(GameProvider='LutrisIntegration',LutrisId='84',Name='Imported title')
        return game


class DeferredMethod(ImportMethod):
    deferred_integration = 'LutrisIntegration'
    def __init__(self, calls):
        self.calls = calls
    def collect(self, widget, game):
        game = super().collect(widget, game)
        game['LutrisId'] = ''
        return game
    @contextmanager
    def commit_transaction(self, widget, game):
        self.calls.append('register')
        game['LutrisId'] = '84'
        try:
            yield game
        except Exception:
            self.calls.append('rollback')
            raise


class ActionSetupTests(unittest.TestCase):
    def test_external_registration_waits_for_library_save_and_rolls_back_for_retry(self):
        calls = []
        method = DeferredMethod(calls)
        self.provider.installation_methods = lambda: [method]
        dialog = ActionSetupDialog(self.game, self.data, [self.provider], method.id)
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(calls, [])
        editor = PlayActionsEditor(self.game, [self.provider])
        dialog.pending_installation.details = lambda: [('Entry', 'Pending example')]
        card = editor.add(dialog.result_action, dialog.pending_installation)
        updated = dict(self.game, PlayActions=editor.collect())
        save = Mock(side_effect=OSError('library failed'))
        with self.assertRaisesRegex(OSError, 'library failed'):
            editor.save_with_removals(save, updated)
        self.assertEqual(calls, ['register', 'rollback'])
        self.assertEqual(updated['PlayActions'][-1]['GameId'], '')
        self.assertIsNotNone(card.pending_installation)
        saved = editor.save_with_removals(lambda: copy.deepcopy(updated), updated)
        self.assertEqual(saved['PlayActions'][-1]['GameId'], '84')
        self.assertEqual(card.game_id.text(), '84')
        self.assertIsNone(card.pending_installation)
        self.assertEqual(calls, ['register', 'rollback', 'register'])
        editor.close()
        dialog.close()

    def test_add_game_persistence_can_retry_without_committing_a_draft(self):
        from playlite.add_game import AddGameEditor
        calls = []
        method = DeferredMethod(calls)
        self.provider.installation_methods = lambda: [method]
        dialog = AddGameEditor(None, self.data, installation_method=method.id)
        dialog.fields['Name'].setText('Example')
        dialog.save()
        draft = copy.deepcopy(dialog.result_game)
        self.assertEqual(calls, [])
        with self.assertRaisesRegex(OSError, 'library failed'):
            dialog.persist(Mock(side_effect=OSError('library failed')))
        self.assertEqual(calls, ['register', 'rollback'])
        self.assertEqual(dialog.result_game, draft)
        self.assertIsNotNone(dialog.pending_installation)
        saved = dialog.persist(copy.deepcopy)
        self.assertEqual(saved['PlayActions'][0]['GameId'], '84')
        self.assertEqual(dialog.result_game, saved)
        self.assertIsNone(dialog.pending_installation)
        self.assertEqual(calls, ['register', 'rollback', 'register'])
        dialog.close()

    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.data=Path(temporary.name);self.provider=Integration()
        self.game=dict(Id='existing',Name='Original title',InstallDirectory='',PlayActions=[dict(Name='Original',Integration='LutrisIntegration',GameId='42')])
        patcher=patch('playlite.providers.discover_plugins',return_value={'Example':self.provider})
        patcher.start();self.addCleanup(patcher.stop)

    def test_dropdown_uses_installation_methods(self):
        editor=PlayActionsEditor(self.game,[self.provider])
        self.assertEqual([a.text() for a in editor.add_button.menu().actions()],['Select existing Lutris entry…', 'Add from executable…', 'Add Steam game…'])
        editor.close()

    def test_removed_manual_method_is_unavailable(self):
        with self.assertRaisesRegex(ValueError, 'unavailable'):
            ActionSetupDialog(self.game,self.data,[self.provider],'Manual')

    def test_import_returns_action_without_replacing_library_metadata(self):
        dialog=ActionSetupDialog(self.game,self.data,[self.provider],'ImportExample')
        dialog.save()
        self.assertEqual(dialog.result(),QDialog.DialogCode.Accepted)
        self.assertEqual(dialog.result_action['Integration'],'LutrisIntegration')
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
        with patch('playlite.lutris_add_dialog.choose_executable_entry', return_value=None) as choose:
            actions.choose_executable()
        self.assertEqual(choose.call_args.args[1], self.data)
        owner.close()
