from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from playlite.lutris_names import save_name, refresh_names


class LutrisNameTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.database=self.root/'pga.db'
        self.data=self.root/'playlite';self.data.mkdir()
        with closing(sqlite3.connect(self.database)) as db,db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY,name,sortname,slug,configpath)')
            db.execute("INSERT INTO games VALUES(1,'Original','Original','stable-slug','stable-config')")
            db.execute("INSERT INTO games VALUES(2,'Other','Custom sort','other','other')")
        self.game={'Id':'game','Name':'Library title','PlayActions':[{'Name':'Original','Integration':'LutrisIntegration','GameId':'1','LutrisDatabase':str(self.database)}]}
        patcher=patch('playlite.lutris_library.installations',return_value=[{'database':self.database}])
        patcher.start();self.addCleanup(patcher.stop)

    def renamed(self,name):
        game=copy.deepcopy(self.game)
        game['PlayActions'][0]['Name']=name
        return game

    def row(self,identity=1):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT name,sortname,slug,configpath FROM games WHERE id=?',(identity,)).fetchone()

    def rename(self,name):
        with closing(sqlite3.connect(self.database)) as db,db:
            db.execute('UPDATE games SET name=? WHERE id=1',(name,))

    def test_playlite_rename_updates_linked_name_and_default_sort_only(self):
        updated=copy.deepcopy(self.game);updated['PlayActions'][0]['Name']='Renamed'
        with save_name(updated,self.game) as result:
            self.assertEqual(result['PlayActions'][0]['Name'],'Renamed')
            self.assertEqual(result['Name'],'Library title')
            self.assertEqual(result['PlayActions'][0]['LutrisName'],'Renamed')
        self.assertEqual(self.row(),('Renamed','Renamed','stable-slug','stable-config'))
        self.assertEqual(self.row(2)[0],'Other')
        self.assertNotIn('LutrisName',updated)

    def test_failed_playlite_save_restores_lutris_title(self):
        updated=self.renamed('Renamed')
        with self.assertRaises(OSError):
            with save_name(updated,self.game):raise OSError('Library write failed')
        self.assertEqual(self.row()[:2],('Original','Original'))

    def test_storage_transaction_rolls_back_a_rename_when_persistence_fails(self):
        from playlite.game_storage import _save_game
        with patch('playlite.providers.discover_plugins',return_value={}),patch('playlite.game_storage._persist_game',side_effect=OSError('Disk full')):
            with self.assertRaises(OSError):_save_game(self.data,[self.game],self.renamed('Renamed'))
        self.assertEqual(self.row()[0],'Original')

    def test_custom_lutris_sort_title_is_preserved(self):
        game=copy.deepcopy(self.game);game['PlayActions'][0]['Name']='Other'
        game['PlayActions'][0]['GameId']='2'
        updated=copy.deepcopy(game);updated['PlayActions'][0]['Name']='New title'
        with save_name(updated,game):pass
        self.assertEqual(self.row(2)[:2],('New title','Custom sort'))

    def test_rollback_preserves_a_concurrent_external_rename(self):
        with self.assertRaises(OSError):
            with save_name(self.renamed('Renamed'),self.game):
                self.rename('External change')
                raise OSError('Library write failed')
        self.assertEqual(self.row()[0],'External change')

    def test_lutris_rename_updates_saved_playlite_name_and_keeps_other_fields(self):
        self.game['Favorite']=True
        self.game['PlayActions'][0]['LutrisName']='Original'
        path=self.data/'library.json';path.write_text(json.dumps([self.game]))
        self.rename('From Lutris')
        result=refresh_names(self.data,[self.game])
        self.assertEqual(result[0]['PlayActions'][0]['Name'],'From Lutris')
        self.assertTrue(result[0]['Favorite'])
        self.assertEqual(json.loads(path.read_text()),result)
        before=path.stat().st_mtime_ns
        self.assertEqual(refresh_names(self.data,result),result)
        self.assertEqual(path.stat().st_mtime_ns,before)

    def test_untouched_editor_cannot_overwrite_newer_lutris_title(self):
        editor=copy.deepcopy(self.game);editor['PlayActions'][0]['LutrisName']='Original'
        self.rename('From Lutris')
        with save_name(editor,self.game) as result:
            self.assertEqual(result['PlayActions'][0]['Name'],'From Lutris')
        self.assertEqual(self.row()[0],'From Lutris')

    def test_deleted_entry_is_not_recreated_and_unlinked_games_are_unchanged(self):
        with closing(sqlite3.connect(self.database)) as db,db:db.execute('DELETE FROM games WHERE id=1')
        self.assertEqual(refresh_names(self.data,[self.game]),[self.game])
        with self.assertRaisesRegex(ValueError,'no longer exists'):
            with save_name(self.game,self.game):pass
        with save_name({'Id':'unlinked','Name':'Local'}, {}) as result:
            self.assertEqual(result,{'Id':'unlinked','Name':'Local'})

    def test_multiple_actions_update_their_own_lutris_entries(self):
        updated=self.renamed('Direct launch')
        updated['PlayActions'].append(dict(updated['PlayActions'][0],GameId='2',Name='Steam launch'))
        with save_name(updated,self.game) as result:
            self.assertEqual(result['Name'],'Library title')
        self.assertEqual(self.row(1)[0],'Direct launch')
        self.assertEqual(self.row(2)[0],'Steam launch')

    def test_existing_custom_action_labels_survive_refresh_until_save(self):
        game=self.renamed('My direct launch')
        refreshed=refresh_names(self.data,[game])
        self.assertEqual(refreshed[0]['PlayActions'][0]['Name'],'My direct launch')
        with save_name(refreshed[0],game):pass
        self.assertEqual(self.row()[0],'My direct launch')
