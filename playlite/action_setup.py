"""Reuse installation plugins to configure one action on an existing game."""
import copy
import sqlite3
from PyQt6.QtWidgets import QComboBox,QLineEdit,QTabWidget
from .add_game import AddGameEditor
from .play_actions import actions_for


class ActionSetupDialog(AddGameEditor):
    editor_purpose = 'play_action'
    def __init__(self,game,data,providers,method,parent=None):
        seed=copy.deepcopy(game)
        seed.pop('PlayActions',None)
        seed['GameProvider']=None
        for provider in providers:seed.pop(provider.action_id_field,None)
        super().__init__('',data,parent,game=seed,installation_method=method)
        self.action_providers=providers
        self.generic_plugins=[]
        tabs=self.findChild(QTabWidget)
        for index in reversed(range(1,tabs.count())):tabs.removeTab(index)
        self.previous_tab.hide();self.next_tab.hide()
        self.manual_integration=QComboBox()
        for provider in providers:self.manual_integration.addItem(provider.name,provider.id)
        self.manual_game_id=QLineEdit()
        self.installation_form.addRow('Integration',self.manual_integration)
        self.installation_form.addRow('Game ID',self.manual_game_id)
        self.installation_method.currentIndexChanged.connect(self.update_manual_fields)
        self.update_manual_fields()
        self.setWindowTitle('Add play action — '+self.installation_plugin.name)
        self.installation_method.currentIndexChanged.connect(lambda:self.setWindowTitle('Add play action — '+self.installation_plugin.name))

    def update_manual_fields(self):
        manual=self.installation_plugin.id=='Manual'
        self.installation_form.setRowVisible(self.manual_integration,manual)
        self.installation_form.setRowVisible(self.manual_game_id,manual)

    def save(self):
        try:
            game=self.collect()
            game=self.installation_plugin.collect(self.installation_widget,game)
            if self.installation_plugin.id=='Manual':
                provider=next((p for p in self.action_providers if p.id==self.manual_integration.currentData()),None)
                if provider is None:raise ValueError('Install a launching integration to create a play action.')
                game['GameProvider']=provider.id
                game[provider.action_id_field]=self.manual_game_id.text().strip()
            # Collection must validate before a plugin creates an external entry.
            game=self.installation_plugin.commit(self.installation_widget,game)
            actions=actions_for(game,self.action_providers)
            if not actions:raise ValueError('This installation method did not supply a launching integration.')
            action=actions[0]
            action['Name']=game.get('Name') or 'Play'
            action['InstallDirectory']=game.get('InstallDirectory') or ''
            provider=next((p for p in self.action_providers if p.id==action['Integration']),None)
            if provider:provider.validate_action(action)
            self.result_action=action
        except (ValueError,OSError,sqlite3.Error) as error:
            self.error.setText(str(error));return
        self.accept()
