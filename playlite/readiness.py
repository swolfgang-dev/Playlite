"""Combine installation and optional plugin checks with direct repair actions."""
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QLabel,QPlainTextEdit,QDialogButtonBox,QPushButton
from .installation_health import inspect_games
from .lifecycle import run_dialog


def show_readiness(window, games):
    rows=inspect_games(games,window.game_providers,getattr(window,'download_queue',None))
    for game in games:
        for plugin in window.generic_plugins:
            check=getattr(plugin,'readiness_checks',None)
            if check:
                try: result=check(window,game)
                except Exception as error: result={'issues':[str(error)],'checked':[]}
                rows.append({'game':game['Name'],'action':getattr(plugin,'action_group',plugin.name),**result})
    count=sum(bool(r['issues']) for r in rows)
    dialog=QDialog(window);dialog.setWindowTitle('Ready to play');dialog.resize(800,560)
    layout=QVBoxLayout(dialog);layout.addWidget(QLabel('Needs attention' if count else 'Launch configuration is ready. Game-file integrity and save restoration have not been tested.'))
    text='\n\n'.join(r['game']+' — '+r['action']+'\n'+'\n'.join(['Issue: '+p for p in r['issues']]+r['checked']) for r in rows)
    report=QPlainTextEdit(text);report.setReadOnly(True);layout.addWidget(report)
    if len(games)==1:
        from .ui_layout import action_row
        edit=QPushButton('Edit game…');edit.clicked.connect(lambda:(dialog.accept(),window.edit_game()));layout.addLayout(action_row(edit))
        for plugin in window.generic_plugins:
            if getattr(plugin,'action_group',None)=='Saves':
                button=QPushButton('Manage saves…')
                callback=next((callback for label,callback in plugin.game_actions(window,games[0]) if label=='Manage saves…'),None)
                if callback:button.clicked.connect(lambda _,callback=callback:(dialog.accept(),callback()));layout.addLayout(action_row(button))
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Close);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    if hasattr(window,'background_tasks'):window.background_tasks.update(title='Ready to play',kind='Readiness check',state='Needs attention' if count else 'Complete',summary=f'{len(games)} games checked; {count} checks need attention.',details=text)
    run_dialog(dialog)


def grouped_actions(plugins, window, games):
    groups={'Installation':[],'Saves':[],'Tools':[]}
    for plugin in plugins:
        actions=plugin.game_actions(window,games[0]) if len(games)==1 else plugin.batch_game_actions(window,games)
        if not actions:continue
        group=getattr(plugin,'action_group','Tools')
        if group not in groups:group='Tools'
        if group=='Saves':groups[group].extend(actions)
        else:groups[group].append((plugin.name,actions))
    return [(name,actions) for name,actions in groups.items() if actions]
