"""Command-line installation methods, supplied by installed plugins."""
import argparse
import json
import os
import sys
import uuid
from pathlib import Path
from .providers import discover_plugins, InstallationPlugin, installation_methods


def main(argv=None):
    parser = argparse.ArgumentParser(prog='playlite-cli')
    parser.add_argument('--data', type=Path, default=Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite')
    commands = parser.add_subparsers(dest='command', required=True)
    plugins = discover_plugins()
    for plugin in installation_methods(plugins).values():
        if isinstance(plugin, InstallationPlugin) and hasattr(plugin, 'configure_cli'):
            command = commands.add_parser(plugin.cli_name, help=plugin.description)
            plugin.configure_cli(command)
            command.add_argument('--dry-run', action='store_true', help='Validate and print without saving or changing external applications')
            command.set_defaults(plugin=plugin)
    args = parser.parse_args(argv)
    try:
        game = args.plugin.cli_game(args, plugins)
        game.setdefault('Id', str(uuid.uuid4()))
        if args.dry_run:
            print(json.dumps(game, indent=2))
            return 0
        from PyQt6.QtCore import QLockFile, QStandardPaths
        runtime = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.RuntimeLocation))
        runtime.mkdir(parents=True, exist_ok=True)
        suffix = '-repo' if os.environ.get('PLAYLITE_PROFILE') == 'repo' else ''
        lock = QLockFile(str(runtime / f'playlite-{os.getuid()}{suffix}.lock'))
        if not lock.tryLock(0):
            raise ValueError('Close Playlite before adding games from the CLI.')
        try:
            args.data.mkdir(parents=True, exist_ok=True)
            path = args.data / 'library.json'
            games = json.loads(path.read_text()) if path.exists() else []
            validate = getattr(args.plugin, 'validate_cli_library', None)
            if validate:
                validate(game, games)
            if hasattr(args.plugin, 'cli_commit'):
                game = args.plugin.cli_commit(args, game, plugins)
            from .editor import save_game
            save_game(args.data, games, game)
        finally:
            lock.unlock()
        print(json.dumps(game, indent=2))
        return 0
    except Exception as error:
        print(f'Error: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
