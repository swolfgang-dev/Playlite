#!/usr/bin/env python3
"""Remove this user's Playlite installation; user data is opt-in."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys

RECEIPT='.playlite-owned.json'


def run(arguments):
    return subprocess.run(arguments,capture_output=True,text=True)


def running_playlite():
    for process in Path('/proc').iterdir():
        if not process.name.isdecimal() or int(process.name)==os.getpid():continue
        try:
            if process.stat().st_uid!=os.getuid():continue
            arguments=(process/'cmdline').read_bytes().split(b'\0')
            environment=(process/'environ').read_bytes().split(b'\0')
            if b'PLAYLITE_PROFILE=repo' in environment:continue
            if any(arguments[i:i+2]==[b'-m',b'playlite'] for i in range(len(arguments)-1)):
                # Source runs are independent of the release runtime.
                if b'/playlite/runtime/bin/' in arguments[0]:return True
                continue
            if any(argument.endswith(b'/bin/playlite') for argument in arguments):return True
        except (OSError,ProcessLookupError):pass
    return False


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run',action='store_true',help='Print the exact removal plan without changing anything.')
    parser.add_argument('--resources-only','--steam-only',dest='resources_only',action='store_true',help='Run plugin resource cleanup without removing the application.')
    parser.add_argument('--purge-data',action='store_true',help='Also delete scoped user data, including plugin-owned private content and logins. External game folders remain untouched.')
    parser.add_argument('--purge-secrets',action='store_true',help='Also remove plugin-owned saved credentials (may ask to unlock the wallet).')
    parser.add_argument('--remove-resource-images','--remove-steam-image',dest='remove_resource_images',action='store_true',help='Ask plugin cleanup hooks to remove their owned runtime images.')
    preferences=parser.add_mutually_exclusive_group()
    preferences.add_argument('--keep-settings',action='store_true',help='Retain user and plugin settings for reinstalling (default).')
    preferences.add_argument('--remove-settings',action='store_true',help='Remove known Playlite and plugin preferences; keep library data and external games.')
    plugins=parser.add_mutually_exclusive_group()
    plugins.add_argument('--keep-plugins',action='store_true',help='Retain installed plugins for reinstalling.')
    plugins.add_argument('--remove-plugins',action='store_true',help='Remove managed plugins (default).')
    args=parser.parse_args(argv)
    if args.keep_plugins and args.purge_data:parser.error('--keep-plugins cannot be combined with --purge-data.')
    if args.keep_settings and args.purge_data:parser.error('--keep-settings cannot be combined with --purge-data.')
    if os.environ.get('PLAYLITE_PROFILE')=='repo':
        parser.error('Run this release uninstaller from a normal terminal, outside the repo profile.')
    if os.getuid()==0:parser.error('Run as the user who installed Playlite, without sudo.')
    if not args.dry_run and running_playlite():parser.error('Close Playlite before uninstalling, so it cannot recreate its files or containers.')
    home=Path.home()
    def base(variable,fallback):
        value=Path(os.environ.get(variable,str(fallback))).expanduser()
        if not value.is_absolute():parser.error(variable+' must be an absolute path.')
        return value
    data=base('XDG_DATA_HOME',home/'.local/share')/'playlite'
    if data.is_symlink():parser.error('Refusing to uninstall through a symlinked data directory.')
    config=base('XDG_CONFIG_HOME',home/'.config')
    base('XDG_CACHE_HOME',home/'.cache')
    base('XDG_STATE_HOME',home/'.local/state')
    binary=base('PLAYLITE_BIN_DIR',home/'.local/bin')
    failures=[]
    def remove(path):
        if not path.exists() and not path.is_symlink():return
        print('Remove:',path)
        if args.dry_run:return
        try:
            if path.is_symlink() or path.is_file():path.unlink()
            elif path.is_dir():shutil.rmtree(path)
        except OSError as error:failures.append(str(error))
    def docker_action(arguments):
        print('Run:',' '.join(['docker',*arguments]))
        if not args.dry_run:
            response=run(['docker',*arguments])
            if response.returncode:failures.append(response.stderr.strip())
    def remove_owned(root):
        marker=root/RECEIPT
        if root.is_symlink() or not marker.is_file() or marker.is_symlink():
            print('Retain directory without an ownership receipt:',root)
            return
        try:
            document=json.loads(marker.read_text())
            if document.get('schema')!=1 or not isinstance(document.get('files'),dict):raise ValueError('Invalid installation receipt.')
            if document.get('root')!=str(root.resolve()):
                print('Retain files copied from another installation:',root);return
            for name in [*document['files'],*document.get('directories',[])]:
                parts=PurePosixPath(name)
                if parts.is_absolute() or '..' in parts.parts or '\\' in name or not parts.parts:raise ValueError('Unsafe installation receipt.')
            for name,expected in document['files'].items():
                path=root/name
                if any(parent.is_symlink() for parent in path.parents if parent!=root and root in parent.parents):continue
                if not path.is_file() and not path.is_symlink():continue
                if path.is_symlink():actual={'link':os.readlink(path)}
                else:
                    digest=hashlib.sha256()
                    with path.open('rb') as stream:
                        for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
                    actual={'sha256':digest.hexdigest()}
                if actual==expected:remove(path)
                else:print('Retain modified file:',path)
            remove(marker)
            if not args.dry_run:
                for name in sorted(document.get('directories',[]),key=lambda name:len(PurePosixPath(name).parts),reverse=True):
                    path=root/name
                    if any(parent.is_symlink() for parent in path.parents if parent!=root and root in parent.parents):continue
                    try:path.rmdir()
                    except OSError:pass
                try:root.rmdir()
                except OSError:pass
        except (OSError,ValueError) as error:failures.append(str(error))
    import runpy
    manifests = []
    seen_plugins = set()
    paths = sorted((data/'plugins').glob('*/manifest.json')) + sorted((data/'plugin-cleanup').glob('*/manifest.json'))
    for path in paths:
        try:
            document=json.loads(path.read_text())
            identity=document.get('id')
            if identity in seen_plugins:continue
            seen_plugins.add(identity)
            manifests.append(document)
            script=document.get('uninstall_hook')
            if not script:continue
            relative=PurePosixPath(script)
            if relative.is_absolute() or '..' in relative.parts:
                raise ValueError('Invalid plugin uninstall hook path.')
            target=path.parent.joinpath(*relative.parts)
            if target.is_symlink() or target.resolve().parent != path.parent.resolve():
                raise ValueError('Uninstall hook is outside the plugin folder.')
            hook=runpy.run_path(str(target))
            hook['cleanup'](data, config, args, remove, run, docker_action, failures)
        except Exception as error:
            failures.append('Plugin cleanup failed: '+str(error))
    if not args.resources_only:
        for command in ('playlite','playlite-cli','playlite-plugins','playlite-installer'):
            path=binary/command
            if path.is_symlink():
                target=path.resolve()
                if target==data/'runtime/bin'/command:remove(path)
                else:print('Retain non-release launcher:',path)
            elif path.is_file():
                if str(data/'runtime/bin'/command) in path.read_text(errors='replace'):remove(path)
                else:print('Retain non-release launcher:',path)
        desktop=data.parent/'applications/playlite.desktop'
        if desktop.is_file() and str(data/'runtime/bin/playlite') in desktop.read_text(errors='replace'):
            remove(desktop)
        if args.keep_plugins:
            print('Installed plugins retained for reinstalling.')
        else:
            for plugin in (data/'plugins').glob('*'):
                if plugin.is_dir():remove_owned(plugin)
            for registration in (data/'plugin-cleanup').glob('*'):
                if registration.is_dir():remove_owned(registration)
        if (data/'runtime').exists():remove_owned(data/'runtime')
        scripts=data/'.playlite-install-scripts.json'
        if scripts.is_file() and not scripts.is_symlink():
            document=json.loads(scripts.read_text())
            if document.get('root')==str(data.resolve()):
                for name,digest in document.get('files',{}).items():
                    if name not in ('uninstall.sh','uninstall.py'):continue
                    path=data/name
                    if path.is_file() and not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==digest:remove(path)
                remove(scripts)
        if args.purge_data:
            # Never recursively delete the data root: it may hold manual plugins
            # or externally added files. Only explicit application data is reset.
            for name in ('library.json','library.json.bak','ui.ini','downloads.json','library.lock'):
                path=data/name
                if path.is_file() or path.is_symlink():remove(path)
                elif path.exists():print('Retain externally replaced application-data directory:',path)
            print('Untracked files, artwork and plugin-created data retained; inspect them before deleting manually.')
        if not args.dry_run:
            for path in (data/'plugins',data):
                try:path.rmdir()
                except OSError:pass
    if args.remove_settings or args.purge_data:
        if not args.resources_only:remove(data/'ui.ini')
        for manifest in manifests:
            for name in manifest.get('settings_groups', []):
                if not isinstance(name,str) or not name or '/' in name or '\\' in name:
                    failures.append('Invalid plugin settings group.');continue
                path=config/'Playlite'/(name+'.conf')
                if path.is_file() or path.is_symlink():remove(path)
            for name in manifest.get('settings_files', []):
                relative=PurePosixPath(name)
                if relative.is_absolute() or '..' in relative.parts or relative.parent != PurePosixPath('playlite'):
                    failures.append('Invalid plugin settings file.');continue
                path=config.joinpath(*relative.parts)
                if path.parent.resolve()!=config.resolve()/'playlite':
                    failures.append('Settings file escaped the config folder.');continue
                if path.is_file() or path.is_symlink():remove(path)
    else:print('User and plugin settings retained for reinstalling.')
    print('External game folders, Wine prefixes outside Playlite data, repositories, Docker, and shared system packages are retained.')
    if not args.purge_data:print('User data retained. Use --purge-data to reset known application data and plugin-owned private data.')
    if not args.purge_secrets:print('Plugin credentials retained. Use --purge-secrets to invoke plugin credential cleanup.')
    if failures:
        for failure in failures:print('Incomplete:',failure,file=sys.stderr)
        return 1
    print('Dry run complete.' if args.dry_run else 'Uninstall complete.')
    return 0


if __name__=='__main__':sys.exit(main())
