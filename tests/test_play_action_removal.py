import unittest
from types import SimpleNamespace
from unittest.mock import Mock
from playlite.play_actions import PlayActionsEditor


class RemovalTests(unittest.TestCase):
    def editor(self):
        provider = SimpleNamespace(id='Launcher', delete_entry=Mock(return_value='backup'), restore_deleted_entry=Mock())
        action = dict(Integration=provider.id, GameId='12')
        editor = SimpleNamespace(cards=[], game=dict(Id='game', Name='Example'), pending_removals=[(provider, action)])
        return editor, provider

    def test_deletes_only_selected_action_when_saving(self):
        editor, provider = self.editor()
        save = Mock(return_value='saved')
        self.assertEqual(PlayActionsEditor.save_with_removals(editor, save), 'saved')
        provider.delete_entry.assert_called_once_with(dict(Id='game', Name='Example', PlayActions=[dict(Integration='Launcher', GameId='12')]))
        self.assertEqual(editor.pending_removals, [])
        provider.restore_deleted_entry.assert_not_called()

    def test_failed_save_restores_entry_and_keeps_pending_choice(self):
        editor, provider = self.editor()
        with self.assertRaises(OSError):
            PlayActionsEditor.save_with_removals(editor, Mock(side_effect=OSError('save failed')))
        provider.restore_deleted_entry.assert_called_once_with('backup')
        self.assertEqual(len(editor.pending_removals), 1)

    def test_entry_shared_by_remaining_action_is_kept(self):
        editor, provider = self.editor()
        editor.cards = [SimpleNamespace(integration=SimpleNamespace(currentData=lambda: 'Launcher'), game_id=SimpleNamespace(text=lambda: '12'))]
        PlayActionsEditor.save_with_removals(editor, Mock())
        provider.delete_entry.assert_not_called()
