import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import copy
from contextlib import closing
from dataclasses import replace
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import vdf
import yaml
from PyQt6.QtWidgets import QApplication
from playlite.lutris_add import ExecutablePlan, register_executable, random_game_id
from playlite.lutris_steam import SteamPlan, register_steam
from playlite.game_storage import save_game
from playlite.editor import MetadataEditor

APP = QApplication.instance() or QApplication([])


class LutrisIdTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / 'playlite'
        self.database = self.root / 'pga.db'
        self.config = self.root / 'config'
        self.folder = self.root / 'Steam/steamapps/common/Game'
        self.folder.mkdir(parents=True)
        self.exe = self.folder / 'game.exe'
        self.exe.write_bytes(b'unchanged')
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY,name,sortname,slug,runner,configpath,executable,directory,installed,service,service_id)')
            db.execute('CREATE TABLE games_categories(game_id INTEGER REFERENCES games(id),category_id INTEGER)')
        installation = {'database': self.database, 'config_directory': self.config, 'flatpak': False}
        for module in ('lutris_add', 'lutris_library'):
            patcher = patch('playlite.'+module+'.installations', return_value=[installation])
            patcher.start(); self.addCleanup(patcher.stop)
        patcher = patch('playlite.providers.discover_plugins', return_value={})
        patcher.start(); self.addCleanup(patcher.stop)
        self.plan = ExecutablePlan('Game',self.exe,self.folder,self.root/'prefixes/game',self.database)
        with register_executable(self.plan) as action:
            self.action = action
        self.old = int(self.action['GameId'])
        self.game = {'Id':'wine','Name':'Game','PlayActions':[dict(self.action)]}
        self.games = save_game(self.data, [], self.game)
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('INSERT INTO games_categories VALUES (?,7)', (self.old,))

    def rows(self):
        with closing(sqlite3.connect(self.database)) as db:
            return db.execute('SELECT id FROM games ORDER BY id').fetchall()

    def config_data(self, identity):
        with closing(sqlite3.connect(self.database)) as db:
            name = db.execute('SELECT configpath FROM games WHERE id=?',(identity,)).fetchone()[0]
        return yaml.safe_load((self.config/'games'/(name+'.yml')).read_text())

    def test_random_ids_are_seven_digits_end_in_zero_and_skip_collisions(self):
        self.assertGreaterEqual(self.old, 1000000)
        self.assertEqual(self.old % 10, 0)
        with closing(sqlite3.connect(':memory:')) as db:
            db.execute('CREATE TABLE games(id INTEGER PRIMARY KEY)')
            db.execute('INSERT INTO games VALUES (1000010)')
            with patch('playlite.lutris_add.secrets.randbelow', side_effect=[1,1,2]):
                self.assertEqual(random_game_id(db),1000020)

    def test_metadata_save_migrates_id_links_config_and_categories(self):
        updated = copy.deepcopy(self.game)
        updated['MetadataIds'] = {'SteamMetadata':'42'}
        result = save_game(self.data,self.games,updated)
        self.assertEqual(result[0]['PlayActions'][0]['GameId'],'4201')
        self.assertEqual(updated['PlayActions'][0]['GameId'],'4201')
        self.assertEqual(self.rows(),[(4201,)])
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT * FROM games_categories').fetchall(),[(4201,7)])
        config=self.config_data(4201)
        self.assertEqual(config['playlite_steam_id'],42)
        self.assertEqual(config['playlite_id_scheme'],'steam')
        self.assertEqual(config['game']['prefix'],str(self.plan.prefix))

    def test_all_saved_links_to_changed_entry_are_updated(self):
        second={'Id':'other','Name':'Other link','PlayActions':[dict(self.action)]}
        games=save_game(self.data,self.games,second)
        updated=copy.deepcopy(self.game);updated['MetadataIds']={'SteamMetadata':'42'}
        games=save_game(self.data,games,updated)
        self.assertEqual({g['PlayActions'][0]['GameId'] for g in games},{'4201'})

    def test_adding_steam_entry_migrates_matching_random_wine_entry(self):
        manifest=self.folder.parent.parent/'appmanifest_42.acf'
        manifest.write_text(vdf.dumps({'AppState':{'appid':'42','name':'Game','installdir':'Game','StateFlags':'4'}}))
        plan=SteamPlan('Game','42',self.folder,manifest,self.database)
        with register_steam(plan) as action:
            steam={'Id':'steam','Name':'Steam game','InstallDirectory':str(self.folder),
                   'MetadataIds':{'SteamMetadata':'42'},'PlayActions':[action]}
            result=save_game(self.data,self.games,steam)
        self.assertEqual(self.rows(),[(4201,),(4202,)])
        wine=next(g for g in result if g['Id']=='wine')
        self.assertEqual(wine['PlayActions'][0]['GameId'],'4202')
        self.assertEqual(steam['PlayActions'][0]['GameId'],'4201')

    def test_adding_steam_action_without_metadata_migrates_existing_random_action(self):
        manifest=self.folder.parent.parent/'appmanifest_42.acf'
        manifest.write_text(vdf.dumps({'AppState':{'appid':'42','name':'Game','installdir':'Game','StateFlags':'4'}}))
        with register_steam(SteamPlan('Game','42',self.folder,manifest,self.database)) as action:
            updated=copy.deepcopy(self.game);updated['PlayActions'].append(action)
            result=save_game(self.data,self.games,updated)
        self.assertEqual([a['GameId'] for a in result[0]['PlayActions']],['4202','4201'])

    def test_unrelated_random_entry_is_not_renumbered(self):
        folder=self.root/'Unrelated';folder.mkdir();exe=folder/'game.exe';exe.touch()
        with register_executable(replace(self.plan,name='Unrelated',executable=exe,directory=folder,prefix=self.root/'prefixes/other')) as action:
            other=action['GameId']
        updated=copy.deepcopy(self.game);updated['MetadataIds']={'SteamMetadata':'42'}
        save_game(self.data,self.games,updated)
        self.assertIn((int(other),),self.rows())

    def test_failed_playlite_save_rolls_back_ids_config_references_and_input(self):
        before=self.config_data(self.old)
        updated=copy.deepcopy(self.game);updated['MetadataIds']={'SteamMetadata':'42'}
        with patch('playlite.game_storage._persist_game',side_effect=OSError('save failed')):
            with self.assertRaises(OSError):save_game(self.data,self.games,updated)
        self.assertEqual(self.rows(),[(self.old,)])
        self.assertEqual(self.config_data(self.old),before)
        self.assertEqual(updated['PlayActions'][0]['GameId'],str(self.old))
        self.assertEqual(json.loads((self.data/'library.json').read_text())[0]['PlayActions'][0]['GameId'],str(self.old))
        with closing(sqlite3.connect(self.database)) as db:
            self.assertEqual(db.execute('SELECT game_id FROM games_categories').fetchone()[0],self.old)

    def test_metadata_id_picker_save_updates_editor_action_ids_immediately(self):
        editor=MetadataEditor(self.game,self.data)
        self.addCleanup(editor.close)
        editor.save_metadata_ids({'SteamMetadata':'42'})
        self.assertEqual(editor.play_actions.cards[0].game_id.text(),'4201')
        self.assertEqual(editor.game['PlayActions'][0]['GameId'],'4201')
        self.assertEqual(self.rows(),[(4201,)])

    def test_new_steam_associated_executable_also_migrates_random_actions(self):
        exe=self.folder/'alternate.exe';exe.touch()
        with register_executable(replace(self.plan,executable=exe,steam_id='42')) as action:
            updated=copy.deepcopy(self.game);updated['PlayActions'].append(action)
            result=save_game(self.data,self.games,updated)
        self.assertEqual([a['GameId'] for a in result[0]['PlayActions']],['4202','4201'])

    def test_exhausted_suffix_range_rolls_back_partial_migration(self):
        exe=self.folder/'alternate.exe';exe.touch()
        with register_executable(replace(self.plan,executable=exe)) as action:
            second=int(action['GameId'])
        updated=copy.deepcopy(self.game)
        updated['PlayActions'].append(action)
        updated['MetadataIds']={'SteamMetadata':'42'}
        with closing(sqlite3.connect(self.database)) as db, db:
            db.executemany('INSERT INTO games(id) VALUES (?)',[(4200+i,) for i in range(1,99)])
        before=[a['GameId'] for a in updated['PlayActions']]
        with self.assertRaisesRegex(ValueError,'in use'):
            save_game(self.data,self.games,updated)
        self.assertEqual([a['GameId'] for a in updated['PlayActions']],before)
        self.assertEqual(self.config_data(self.old)['playlite_id_scheme'],'random')
        self.assertEqual(self.config_data(second)['playlite_id_scheme'],'random')
        self.assertNotIn((4299,),self.rows())

    def test_failed_steam_add_restores_random_id_and_removes_new_steam_entry(self):
        manifest=self.folder.parent.parent/'appmanifest_42.acf'
        manifest.write_text(vdf.dumps({'AppState':{'appid':'42','name':'Game','installdir':'Game','StateFlags':'4'}}))
        plan=SteamPlan('Game','42',self.folder,manifest,self.database)
        with self.assertRaises(OSError):
            with register_steam(plan) as action:
                game={'Id':'steam','Name':'Steam','MetadataIds':{'SteamMetadata':'42'},
                      'InstallDirectory':str(self.folder),'PlayActions':[action]}
                with patch('playlite.game_storage._persist_game',side_effect=OSError('save failed')):
                    save_game(self.data,self.games,game)
        self.assertEqual(self.rows(),[(self.old,)])
        self.assertEqual(len(list((self.config/'games').glob('*.yml'))),1)
        self.assertEqual(self.config_data(self.old)['playlite_id_scheme'],'random')
