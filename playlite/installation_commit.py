"""Keep external registration pending until its library entry is saved."""
import copy
from contextlib import contextmanager


def set_play_actions(game, providers):
    from .play_actions import actions_for
    actions = actions_for(game, providers)
    if actions:
        game['PlayActions'] = actions
        from .plugin_fields import legacy_action_fields
        for key in legacy_action_fields(providers):
            game.pop(key, None)
    return game


class PendingInstallation:
    def __init__(self, method, widget, game):
        self.method = method
        self.widget = widget
        self.game = copy.deepcopy(game)

    @contextmanager
    def commit(self, action=None):
        game = copy.deepcopy(self.game)
        if action is not None:
            for field, target in (('Executable', 'Executable'), ('Prefix', 'Prefix'),
                                  ('Arguments', 'LaunchArguments'), ('InstallDirectory', 'InstallDirectory')):
                if field in action:
                    if field == 'InstallDirectory' and not action[field]:
                        continue
                    game[target] = action[field]
        with self.method.commit_transaction(self.widget, game) as result:
            yield result

    @contextmanager
    def commit_action(self, action, providers):
        from .play_actions import actions_for
        provider = next((item for item in providers if item.id == action['Integration']), None)
        if provider is None:
            raise ValueError('The launching integration is no longer available.')
        with self.commit(action) as game:
            registered = actions_for(game, providers)
            if not registered:
                raise ValueError('This installation method did not supply a launching integration.')
            result = dict(action, GameId=registered[0]['GameId'], Prefix=registered[0].get('Prefix', action.get('Prefix', '')))
            provider.validate_action(result)
            yield result
