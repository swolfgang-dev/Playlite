"""Fail if optional plugin implementations are bundled in the base wheel."""
import sys
from zipfile import ZipFile

for path in sys.argv[1:]:
    with ZipFile(path) as wheel:
        entries = wheel.namelist()
    forbidden = ('playlite/plugins/', 'playlite/igdb.py', 'playlite/registration.py',
                 'playlite/archive_transfer.py', 'playlite/steam_artwork.py', 'playlite/steam_runner.py')
    assert not any(entry.startswith(forbidden) for entry in entries), entries
    assert 'playlite/manual_installation.py' in entries
    assert 'playlite/plugin_manager.py' in entries
    print(f'{path}: core only; Manual is built in.')
