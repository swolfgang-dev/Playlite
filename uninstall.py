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

LABEL='io.playlite.steam-downloader'
OWNER_LABEL='io.playlite.steam.owner'
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
    parser.add_argument('--steam-only',action='store_true',help='Remove only the isolated Steam/VPN environment.')
    parser.add_argument('--purge-data',action='store_true',help='Also delete scoped user data, including private Steam games and logins. External game folders remain untouched.')
    parser.add_argument('--purge-secrets',action='store_true',help='Also remove the Playlite Steam Downloader folder from KWallet (may ask to unlock the wallet).')
    parser.add_argument('--remove-steam-image',action='store_true',help='Also remove the dedicated Steam runtime image; shared Docker images remain.')
    preferences=parser.add_mutually_exclusive_group()
    preferences.add_argument('--keep-settings',action='store_true',help='Retain user and plugin settings for reinstalling (default).')
    preferences.add_argument('--remove-settings',action='store_true',help='Remove known Playlite and plugin preferences; keep library data and external games.')
    args=parser.parse_args(argv)
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
    cache=base('XDG_CACHE_HOME',home/'.cache')
    state=base('XDG_STATE_HOME',home/'.local/state')
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
    def owned_resource(kind,name):
        response=run(['docker',kind,'inspect',name])
        if response.returncode:return False
        entry=json.loads(response.stdout)[0]
        labels=(entry.get('Config',{}).get('Labels') if kind=='image' else entry.get('Labels')) or {}
        if labels.get(OWNER_LABEL)!=str(os.getuid()):
            print('Retain resource without ownership label:',name);return False
        return True
    gateway=f'playlite-steam-downloader-vpn-{os.getuid()}'
    volume=f'playlite-steam-home-{os.getuid()}'
    if shutil.which('docker'):
        response=run(['docker','ps','-aq','--filter','label='+LABEL+'='+str(os.getuid())])
        # The gateway carries the user label; workers carry its separate gateway label.
        workers=run(['docker','ps','-aq','--filter','label='+LABEL+'.gateway'])
        if response.returncode or workers.returncode:
            failures.append('Docker is unavailable; isolated container cleanup was not completed.')
        else:
            owned_gateways={gateway}
            for identifier in response.stdout.split():
                inspected=run(['docker','inspect',identifier])
                if inspected.returncode:continue
                entry=json.loads(inspected.stdout)[0]
                if (entry['Config'].get('Labels') or {}).get(LABEL)==str(os.getuid()):
                    owned_gateways.add(identifier)
                    owned_gateways.add(entry.get('Id',identifier))
            for identifier in dict.fromkeys(workers.stdout.split()+response.stdout.split()):
                inspected=run(['docker','inspect',identifier])
                if inspected.returncode:failures.append('Could not inspect container '+identifier);continue
                entry=json.loads(inspected.stdout)[0];labels=entry['Config'].get('Labels') or {}
                owned=(labels.get(LABEL)==str(os.getuid()) or labels.get(LABEL+'.gateway') in owned_gateways)
                if not owned:
                    if identifier in response.stdout.split():failures.append('Refusing unowned container '+identifier)
                    else:print('Retain another installation’s worker:',identifier)
                    continue
                docker_action(['rm','-f',identifier])
        if args.purge_data and owned_resource('volume',volume):
            docker_action(['volume','rm',volume])
    else:print('Docker not installed; no container cleanup performed.')
    if args.purge_data:
        root=data/'steam-runtime'
        marker=root/'environment-owner.json'
        if root.is_symlink():
            print('Retain external Steam directory link:',root)
        elif marker.is_file() and not marker.is_symlink():
            document=json.loads(marker.read_text())
            names=document.get('directories',[])
            if document.get('owner')!=str(os.getuid()) or any(name not in ('control','library') for name in names):
                failures.append('Invalid Steam data ownership receipt.')
            else:
                for name in names:
                    path=root/name
                    if args.dry_run:
                        print('Remove owned private Steam directory:',path)
                    elif path.is_symlink():
                        print('Retain externally replaced Steam directory link:',path)
                    elif path.exists():
                        try:shutil.rmtree(path)
                        except PermissionError:
                            if shutil.which('docker') and owned_resource('image','playlite-steam-runtime:test'):
                                docker_action(['run','--rm','--network','none','--read-only','--user','0:0',
                                    '--mount',f'type=bind,src={path},dst=/cleanup','--entrypoint','python3','playlite-steam-runtime:test',
                                    '-B','-c',"import pathlib,shutil; root=pathlib.Path('/cleanup'); [p.unlink() if p.is_symlink() or p.is_file() else shutil.rmtree(p) for p in root.iterdir()]"])
                                try:path.rmdir()
                                except OSError as error:failures.append(str(error))
                            else:failures.append('Private Steam data needs permission cleanup: '+str(path))
                remove(marker)
                if not args.dry_run:
                    try:root.rmdir()
                    except OSError:pass
        elif root.exists():print('Retain private Steam data without ownership receipt:',root)
    if args.remove_steam_image and shutil.which('docker') and owned_resource('image','playlite-steam-runtime:test'):
        docker_action(['image','rm','playlite-steam-runtime:test'])
    if args.purge_secrets:
        print('Remove KWallet folder: Playlite Steam Downloader')
        if not args.dry_run:
            code='''from PyQt6.QtCore import QCoreApplication,QVariant,QMetaType
from PyQt6.QtDBus import QDBusConnection,QDBusInterface
app=QCoreApplication([])
for name in ('org.kde.kwalletd6','org.kde.kwalletd5'):
 interface=QDBusInterface(name,'/modules/kwalletd'+name[-1],'org.kde.KWallet',QDBusConnection.sessionBus())
 if interface.isValid():break
else:raise SystemExit('KWallet is unavailable; credentials were not removed.')
def call(method,*args):
 reply=interface.call(method,*args)
 if reply.errorName():raise SystemExit('KWallet request failed.')
 return reply.arguments()[0] if reply.arguments() else None
window=QVariant(0);window.convert(QMetaType(QMetaType.Type.LongLong.value))
handle=call('open',call('networkWallet'),window,'Playlite Uninstaller')
if handle is None or handle<0:raise SystemExit('KWallet unlock cancelled; credentials were not removed.')
try:
 if call('hasFolder',handle,'Playlite Steam Downloader','Playlite Uninstaller'):
  if not call('removeFolder',handle,'Playlite Steam Downloader','Playlite Uninstaller'):raise SystemExit('Could not remove wallet folder.')
finally:call('close',handle,False,'Playlite Uninstaller')
'''
            python=data/'runtime/bin/python'
            if not python.exists():python=Path('/usr/bin/python3')
            response=run([str(python),'-c',code])
            if response.returncode:failures.append('KWallet cleanup failed: '+response.stderr.strip())
    if args.steam_only:
        if args.purge_data:
            remove(config/'Playlite/SteamDownloader.conf')
    else:
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
        for plugin in (data/'plugins').glob('*'):
            if plugin.is_dir():remove_owned(plugin)
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
        if not args.steam_only:
            remove(data/'ui.ini')
            for name in ('Lutris','Steam','SteamDownloader','SteamAutoCrack','Archiver'):
                path=config/'Playlite'/(name+'.conf')
                if path.is_file() or path.is_symlink():remove(path)
            credential=home/'.config/playlite/igdb.json'
            if credential.is_file() or credential.is_symlink():remove(credential)
        else:
            remove(config/'Playlite/SteamDownloader.conf')
    else:print('User and plugin settings retained for reinstalling.')
    print('External game folders, Wine prefixes outside Playlite data, repositories, Docker, and shared system packages are retained.')
    if not args.purge_data:print('User data and private Steam volume retained. Use --purge-data to reset known application data and owned private Steam data.')
    if not args.purge_secrets:print('KWallet credentials retained. Use --purge-secrets to remove downloader credentials.')
    if failures:
        for failure in failures:print('Incomplete:',failure,file=sys.stderr)
        return 1
    print('Dry run complete.' if args.dry_run else 'Uninstall complete.')
    return 0


if __name__=='__main__':sys.exit(main())
