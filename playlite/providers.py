"""Metadata plugin discovery and the API shared by built-in and user providers."""
import json
import logging
import os
from pathlib import Path


class Plugin:
    def save_action_settings(self, game):
        """Return a context that rolls external action settings back on save failure.

        Called for game and generic plugins under the library transaction lock.
        Validate before changing files; preserve unrelated launcher settings.
        """
        from contextlib import nullcontext
        return nullcontext()

    def create_settings(self, parent=None):
        return None

    def save_settings(self, widget):
        pass

    def validate_settings(self, widget):
        """Validate pending preferences without writing files or changing runtime state."""
        pass

    def create_settings_contribution(self, target, parent=None):
        """Optionally contribute a widget to another installed plugin's section."""
        return None

    def save_settings_contribution(self, target, widget):
        pass

    def validate_settings_contribution(self, target, widget):
        """Validate a contributed preferences section before any section is saved."""
        pass


class ThemePlugin(Plugin):
    """Return a partial or complete palette keyed by playlite.theme.ROLES."""
    def palette(self):
        return {}


class GameProvider(Plugin):
    action_id_field = 'ProviderGameId'

    def create_action_editor(self, action, parent=None):
        from .play_actions import LaunchSettings
        return LaunchSettings(action, parent)

    def validate_action(self, action):
        pass

    def launch_action(self, game, action):
        from .play_actions import action_game
        return self.launch(action_game(game, action, self))

    def add_methods(self, window):
        return [(f'Add from {self.name}', lambda: window.import_provider_games(self))]

    def association_id(self, game):
        return game.get('ProviderGameId')
    def detection_association_id(self, game):
        if 'PlayActions' in game:
            return tuple((str(action.get('GameId') or self.association_id(game) or ''),
                          action.get('Executable'), action.get('Prefix'), action.get('Arguments'),
                          action.get('InstallDirectory') or game.get('InstallDirectory'))
                         for action in game['PlayActions'] or [] if action.get('Integration') == self.id)
        return self.association_id(game)
    def owns(self, game):
        if 'PlayActions' in game:
            return any(action.get('Integration') == self.id for action in game['PlayActions'] or [])
        return game.get('GameProvider') == self.id

    def launch(self, game):
        raise NotImplementedError

    def import_games(self):
        return []


class InstallationPlugin(Plugin):
    """An add method supplies controls and validates a proposed library entry."""
    description = ''
    deferred_integration = ''
    def create_editor(self, editor, game):
        raise NotImplementedError

    def collect(self, widget, game):
        raise NotImplementedError

    def commit(self, widget, game):
        """Perform explicitly requested external changes after all validation."""
        return game

    def commit_transaction(self, widget, game):
        """Override to roll external registration back if library saving fails."""
        from contextlib import nullcontext
        return nullcontext(self.commit(widget, game))

    def cli_commit_transaction(self, args, game, plugins):
        from contextlib import nullcontext
        commit = getattr(self, 'cli_commit', None)
        return nullcontext(commit(args, game, plugins) if commit else game)


class IntegrationPlugin(GameProvider):
    """Own launching, add methods and running-game detection for a launcher."""
    def stop(self, game):
        """Stop matching game processes in a worker; return the number targeted."""
        raise ValueError(f"Stopping games is not supported by {self.name}.")

    def installation_methods(self):
        return []

    def detect_running(self, games):
        """Return IDs of confirmed running Playlite entries; runs in a worker."""
        return set()

    def add_methods(self, window):
        return [(method.name, lambda method=method: window.add_manual_game(method.id))
                for method in self.installation_methods()]


def installation_methods(plugins):
    from .manual_installation import ManualInstallation
    methods = {'Manual': ManualInstallation()}
    methods.update({key: plugin for key, plugin in plugins.items() if isinstance(plugin, InstallationPlugin)})
    for plugin in plugins.values():
        if isinstance(plugin, IntegrationPlugin):
            methods.update((method.id, method) for method in plugin.installation_methods())
    return methods


class ImageProvider(Plugin):
    image_types = frozenset()
    manual = False
    metadata_provider = None

    def query(self, game):
        return game.get('Name', '')

    def search(self, query):
        raise NotImplementedError

    def images(self, game_id, image_type):
        """Return candidates with url, optional thumbnail, and label."""
        raise NotImplementedError

    def image_page(self, game_id, image_type, page=0):
        return (self.images(game_id, image_type), False) if page == 0 else ([], False)

    def recommend(self, game, image_type):
        """Resolve a game and return image candidates in preference order."""
        from difflib import SequenceMatcher
        query = self.query(game)
        results = self.search(query)
        if not results:
            return []
        if str(query).isascii() and str(query).isdigit():
            match = next((item for item in results if str(item['id']) == str(query)), None)
        else:
            name = game.get('Name', '').casefold()
            match = max(results, key=lambda item: SequenceMatcher(None, name, item['name'].casefold()).ratio())
            if SequenceMatcher(None, name, match['name'].casefold()).ratio() < 0.75:
                raise ValueError('No confident game match; use Download images to choose manually.')
        return self.images(match['id'], image_type) if match else []


class GenericPlugin(Plugin):
    def create_action_settings(self, action, parent=None):
        """Optional Advanced launch widget; collect() returns plugin-owned action fields."""
        return None

    def batch_game_actions(self, window, games):
        """Actions applying to a snapshot of the selected library entries."""
        return []

    def game_actions(self, window, game):
        return []

    def before_launch(self, window, game):
        return True

    def before_action_launch(self, window, game, action):
        """Validate the chosen action on the UI thread; False cancels launch."""
        return True

    def after_launch(self, window, game, action):
        """Observe a successfully launched action; must not block the UI."""
        pass

    def after_game_stopped(self, window, game, action):
        """A detected game session ended; action is None for external launches."""
        pass

    def augment_editor(self, editor):
        """Contribute controls to both Edit and Add game windows."""
        pass

    def collect_editor(self, editor, game):
        """Validate and collect plugin controls into the edited game."""
        pass

    def prepare_edit_save(self, previous, game):
        """Merge plugin-owned state against the latest library entry."""
        pass

    def augment_game_view(self, window, game, heading, installation_form):
        """Contribute game details to the installation panel."""
        pass

    def augment_add_editor(self, editor):
        pass

    def prepare_add(self, editor, game, registration):
        pass

    def library_ready(self, window):
        """The library window is ready for asynchronous initialization."""
        pass

    def after_game_removed(self, window, game):
        """Observe a successfully removed library entry."""
        pass

    def after_game_updated(self, window, game):
        """Apply plugin changes after a game edit has been saved."""
        pass

    def after_game_added(self, window, game, editor):
        pass


class MetadataProvider(Plugin):
    """Plugins export a Provider subclass from plugin.py (API version 1)."""
    image_types = frozenset()

    def query(self, game):
        return str((game.get('MetadataIds') or {}).get(self.id) or
                   self.linked_query(game) or game.get('Name', ''))

    def images(self, game_id, image_type):
        """Return selectable artwork candidates with url and label."""
        return []

    def image_page(self, game_id, image_type, page=0):
        """Return (candidates, has_more); existing providers have one page."""
        return (self.images(game_id, image_type), False) if page == 0 else ([], False)

    def search(self, query):
        raise NotImplementedError

    def fetch(self, game_id, fields):
        raise NotImplementedError

    def linked_query(self, game):
        return None

    def is_exact_query(self, query, result_id=None):
        return False

    def create_settings(self, parent=None):
        """Return an optional QWidget; leave persistent state unchanged here."""
        return None

    def save_settings(self, widget):
        """Validate and save the settings widget; raise ValueError on failure."""
        pass

    @property
    def query_hint(self):
        return f'Game name or {self.name} game ID'


def discover_plugins(directory=None, *, include_disabled=False):
    roots = [Path(directory) if directory is not None else
             Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite/plugins']
    from .manual_launch import ManualLaunch
    providers = {'Manual': ManualLaunch()}
    for root in roots:
        from .plugin_manager import installed_plugins
        installed = installed_plugins(root)
        for manifest_path in sorted(root.glob('*/manifest.json')):
            try:
                manifest = json.loads(manifest_path.read_text())
                from .plugin_manifest import validate_manifest
                validate_manifest(manifest)
                if manifest.get('enabled', True) is False and not include_disabled:
                    continue
                plugin_id = manifest['id']
                if plugin_id.casefold() in {key.casefold() for key in providers}:
                    raise ValueError('Plugin ID must be unique and cannot be Current.')
                from .plugin_dependencies import missing_dependencies
                if missing_dependencies(manifest, installed):
                    raise ValueError('Required plugin dependencies are missing or outdated.')
                plugin_type = manifest.get('type', 'metadata')
                base = {'metadata': MetadataProvider, 'game': GameProvider, 'generic': GenericPlugin,
                        'installation': InstallationPlugin, 'integration': IntegrationPlugin,
                        'image': ImageProvider, 'theme': ThemePlugin}.get(plugin_type)
                fields = manifest.get('fields', [])
                from .plugin_modules import load_module
                module = load_module(plugin_id, manifest_path.parent)
                provider = (module.Provider if plugin_type == 'metadata' else module.Plugin)()
                if not isinstance(provider, base):
                    raise ValueError(f'Plugin must inherit {base.__name__}.')
                provider.id = plugin_id
                provider.name = manifest['name']
                provider.version = manifest['version']
                provider.fields = frozenset(fields)
                provider.type = plugin_type
                provider.enabled = manifest.get('enabled', True)
                provider.manifest_path = manifest_path
                from .plugin_fields import validate_declarations
                provider.game_fields = validate_declarations(manifest.get('game_fields', []))
                provider.image_defaults = manifest.get('image_defaults', {})
                provider.description = manifest.get('description', getattr(provider, 'description', ''))
                providers[plugin_id] = provider
            except Exception:
                logging.exception('Could not load metadata plugin %s', manifest_path)
    return providers


def discover_providers(directory=None, *, include_disabled=False):
    return {key: plugin for key, plugin in discover_plugins(directory, include_disabled=include_disabled).items() if isinstance(plugin, MetadataProvider)}
