"""Install optional plugins from authenticated GitHub release archives."""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
from zipfile import ZipFile
from .storage import atomic_json
from .plugin_names import plugin_folder
from .ownership import RECEIPT, record_tree, receipt, signature, remove_owned, carry_external, file_inventory, record_added_files, unchanged

CATALOGUE_REPOSITORY = 'swolfgang-dev/Playlite'

def plugin_catalogue():
    import base64
    from urllib.error import HTTPError
    try:
        document = github_request('repos/' + CATALOGUE_REPOSITORY + '/contents/catalogue.json')
        catalogue = json.loads(base64.b64decode(document['content']))
    except HTTPError as error:
        if error.code not in (403, 429):
            raise
        from urllib.request import urlopen
        with urlopen('https://raw.githubusercontent.com/' + CATALOGUE_REPOSITORY + '/main/catalogue.json', timeout=30) as response:
            catalogue = json.loads(response.read())
    if catalogue.get('schema_version') != 1:
        raise ValueError('Unsupported plugin catalogue format.')
    entries = catalogue.get('plugins')
    if not isinstance(entries, list):
        raise ValueError('Invalid plugin catalogue.')
    result = []
    for entry in entries:
        if not isinstance(entry.get('name'), str) or not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', entry.get('repository', '')):
            raise ValueError('Invalid plugin catalogue entry.')
        result.append((entry['name'], entry['repository']))
    return result



def plugin_directory():
    return Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local/share'))) / 'playlite/plugins'


def installed_plugins(directory=None):
    result = []
    for path in sorted((directory or plugin_directory()).glob('*/manifest.json')):
        try:
            manifest = json.loads(path.read_text())
            result.append(dict(manifest, manifest_path=str(path)))
        except (OSError, ValueError):
            continue
    return result


def set_plugin_enabled(identity, enabled, directory=None):
    directory = Path(directory or plugin_directory())
    entry = next((item for item in installed_plugins(directory) if item.get('id') == identity), None)
    if entry is None:
        raise ValueError('Plugin is no longer installed.')
    path = Path(entry['manifest_path'])
    if path.is_symlink() or path.parent.is_symlink() or path.resolve().parent.parent != directory.resolve():
        raise ValueError('Plugin directory is outside the installed plugin folder.')
    manifest = json.loads(path.read_text())
    manifest['enabled'] = bool(enabled)
    atomic_json(path, manifest)
    if (path.parent / RECEIPT).is_file():
        files = receipt(path.parent)
        files['manifest.json'] = signature(path)
        document = json.loads((path.parent / RECEIPT).read_text())
        document['files'] = files
        atomic_json(path.parent / RECEIPT, document)
        (path.parent / RECEIPT).chmod(0o600)
    return manifest


def delete_plugin(identity, directory=None, keep_settings=True):
    directory = Path(directory or plugin_directory())
    entry = next((item for item in installed_plugins(directory) if item.get('id') == identity), None)
    if entry is None:
        raise ValueError('Plugin is no longer installed.')
    target = Path(entry['manifest_path']).parent
    if target.is_symlink() or target.resolve().parent != directory.resolve():
        raise ValueError('Plugin directory is outside the installed plugin folder.')
    if not keep_settings:
        from .plugin_settings import clear_plugin_settings
        clear_plugin_settings(entry)
    if (target / RECEIPT).exists():
        remove_owned(target)
    else:
        # Explicit plugin removal is allowed; global uninstall never adopts it.
        shutil.rmtree(target)
    return entry


def delete_plugins(identities, progress=None, keep_settings=True):
    results = []
    for identity in dict.fromkeys(identities):
        if progress:
            progress('Deleting ' + identity + '…')
        try:
            plugin = delete_plugin(identity, keep_settings=keep_settings)
            results.append((identity, plugin, ''))
        except (ValueError, OSError) as error:
            results.append((identity, None, str(error)))
        if progress:
            _, plugin, error = results[-1]
            progress('Deleted ' + plugin['name'] if plugin else identity + ': ' + error)
    return results


def install_plugins(repositories, progress=None):
    results = []
    for repository in dict.fromkeys(repositories):
        if progress:
            progress('Installing ' + repository + '…')
        try:
            manifest = install_github(repository)
            results.append((repository, manifest, ''))
        except Exception as error:
            results.append((repository, None, str(error)))
        if progress:
            _, manifest, error = results[-1]
            progress(f"Installed {manifest['name']} {manifest['version']}" if manifest else f'{repository}: {error}')
    return results


def install_archive(archive, directory=None, repository=''):
    directory = directory or plugin_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.install-', dir=directory) as temporary:
        stage = Path(temporary) / 'plugin'
        stage.mkdir()
        with ZipFile(archive) as bundle:
            entries = bundle.infolist()
            if sum(entry.file_size for entry in entries) > 50 * 1024 * 1024 or len(entries) > 1000:
                raise ValueError('Plugin archive is too large.')
            seen = set()
            for entry in entries:
                path = PurePosixPath(entry.filename)
                mode = entry.external_attr >> 16
                if path.is_absolute() or '..' in path.parts or '\\' in entry.filename or stat.S_ISLNK(mode):
                    raise ValueError('Plugin archive contains unsafe paths.')
                if entry.filename in seen:
                    raise ValueError('Plugin archive contains duplicate paths.')
                seen.add(entry.filename)
                if not entry.is_dir():
                    target = stage.joinpath(*path.parts)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(bundle.read(entry))
        manifest_path = stage / 'manifest.json'
        if not manifest_path.is_file() or not (stage / 'plugin.py').is_file():
            raise ValueError('Plugin release must contain manifest.json and plugin.py at its root.')
        manifest = json.loads(manifest_path.read_text())
        identity = manifest.get('id', '')
        if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', identity) or identity in ('Manual', 'Current'):
            raise ValueError('Invalid or reserved plugin ID.')
        if manifest.get('api_version') != 1:
            raise ValueError('Unsupported plugin API version.')
        if manifest.get('type', 'metadata') not in ('metadata', 'game', 'generic', 'installation', 'integration', 'image', 'theme'):
            raise ValueError('Unsupported plugin type.')
        if not isinstance(manifest.get('name'), str) or not isinstance(manifest.get('version'), str):
            raise ValueError('Plugin name and version are required.')
        hook = manifest.get('uninstall_hook')
        if hook:
            hook_path = PurePosixPath(hook)
            if hook_path.is_absolute() or len(hook_path.parts) != 1 or hook_path.suffix != '.py' or not (stage / hook).is_file():
                raise ValueError('Plugin cleanup must be a standalone file at its root.')
        requirements = manifest.get('requirements') or []
        if requirements:
            import sys
            if not isinstance(requirements, list) or not all(isinstance(value, str) and not value.startswith('-') for value in requirements):
                raise ValueError('Invalid plugin dependency list.')
            from importlib.metadata import version, PackageNotFoundError
            pending = []
            for requirement in requirements:
                match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:>=([0-9.]+))?', requirement)
                if not match:
                    raise ValueError('Use package names with an optional minimum version for plugin dependencies.')
                try:
                    installed = version(match.group(1))
                    if match.group(2) and tuple(map(int, installed.split('.'))) < tuple(map(int, match.group(2).split('.'))):
                        pending.append(requirement)
                except (PackageNotFoundError, ValueError):
                    pending.append(requirement)
            if pending:
                runtime = Path(sys.prefix)
                before = file_inventory(runtime) if (runtime / RECEIPT).is_file() else None
                owned = {name for name, expected in receipt(runtime).items() if unchanged(runtime, name, expected)} if before is not None else set()
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', *pending], check=True, timeout=300)
                finally:
                    if before is not None: record_added_files(runtime, before, owned)
        existing = next((Path(item['manifest_path']).parent for item in installed_plugins(directory)
                         if item['id'] == identity), None)
        if existing and (existing.is_symlink() or existing.resolve().parent != directory.resolve()):
            raise ValueError('Plugin directory is outside the installed plugin folder.')
        if repository:
            manifest['repository'] = repository
        existing_folder = next((Path(entry['manifest_path']).parent for entry in installed_plugins(directory) if entry.get('id') == manifest['id']), None)
        destination = existing_folder or directory / plugin_folder(manifest)
        if destination.exists() and destination != existing:
            raise ValueError('Plugin destination folder is already occupied.')
        if existing:
            previous = json.loads((existing / 'manifest.json').read_text())
            manifest['enabled'] = previous.get('enabled', True)
        if repository:
            manifest['repository'] = repository
        atomic_json(manifest_path, manifest)
        carried = carry_external(existing, stage) if existing else []
        record_tree(stage, carried, destination)
        backup = directory / ('.previous-' + uuid.uuid4().hex)
        if existing:
            existing.rename(backup)
        try:
            stage.rename(destination)
        except Exception:
            if backup.exists():
                backup.rename(existing)
            raise
        if backup.exists():
            shutil.rmtree(backup)
    # Keep declarations and cleanup available after individual plugin removal.
    cleanup = directory.parent / 'plugin-cleanup' / identity
    if cleanup.is_symlink() or cleanup.parent.is_symlink():
        raise ValueError('Plugin cleanup registration cannot be a symlink.')
    cleanup.mkdir(parents=True, exist_ok=True)
    generated = {'manifest.json', hook} - {None}
    external = file_inventory(cleanup) - generated - {RECEIPT}
    if hook:
        if (cleanup / hook).is_symlink():
            raise ValueError('Plugin cleanup script cannot be a symlink.')
        (cleanup / hook).write_bytes((destination / hook).read_bytes())
    atomic_json(cleanup / 'manifest.json', manifest)
    record_tree(cleanup, excluded=external)
    from .image_filters import apply_install_defaults
    apply_install_defaults(manifest, directory.parent)
    return manifest


def github_environment():
    """Never inherit credentials from the user's CLI or another installation."""
    env = os.environ.copy()
    for key in ('GH_TOKEN', 'GITHUB_TOKEN', 'GH_ENTERPRISE_TOKEN', 'GITHUB_ENTERPRISE_TOKEN'):
        env.pop(key, None)
    env['GH_CONFIG_DIR'] = str(plugin_directory().parent / 'github')
    return env


def development_checkout():
    return (Path(__file__).resolve().parent.parent / '.git').exists()


def github_token():
    if os.environ.get('PLAYLITE_INSTALLER') == '1':
        return os.environ.get('PLAYLITE_GITHUB_TOKEN', '')
    if not development_checkout() or shutil.which('gh') is None:
        return ''
    result = subprocess.run(['gh', 'auth', 'token', '--hostname', 'github.com'],
                            env=github_environment(), capture_output=True, text=True, timeout=15)
    return result.stdout.strip() if result.returncode == 0 else ''


def github_browser_command():
    if not development_checkout():
        raise ValueError('GitHub authentication is available only in the repository version.')
    if shutil.which('gh') is None:
        raise ValueError('Install GitHub CLI to sign in through your browser.')
    folder = Path(github_environment()['GH_CONFIG_DIR'])
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return ['gh', 'auth', 'login', '--hostname', 'github.com', '--git-protocol', 'https',
            '--web', '--insecure-storage']


def authenticate_github(token):
    if not development_checkout():
        raise ValueError('GitHub authentication is available only in the repository version.')
    if not token.strip():
        raise ValueError('Enter a GitHub token.')
    folder = Path(github_environment()['GH_CONFIG_DIR'])
    folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    result = subprocess.run(['gh', 'auth', 'login', '--hostname', 'github.com', '--with-token', '--insecure-storage'],
                            input=token.strip(), env=github_environment(), capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise ValueError('GitHub authentication failed. Check the token and repository permissions.')
    for path in folder.glob('*'):
        if path.is_file():
            path.chmod(0o600)


def github_request(path, binary=False):
    from urllib.request import Request, build_opener, HTTPRedirectHandler
    from urllib.parse import urlparse
    class AssetRedirect(HTTPRedirectHandler):
        def redirect_request(self, request, response, code, message, headers, target):
            redirected = super().redirect_request(request, response, code, message, headers, target)
            if redirected is not None and urlparse(target).hostname != "api.github.com":
                redirected.remove_header("Authorization")
            return redirected
    headers = {'Accept': 'application/octet-stream' if binary else 'application/vnd.github+json',
               'User-Agent': 'Playlite', 'X-GitHub-Api-Version': '2022-11-28'}
    token = github_token()
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with build_opener(AssetRedirect()).open(Request('https://api.github.com/' + path, headers=headers), timeout=30) as response:
        data = response.read()
    return data if binary else json.loads(data)


def available_plugins():
    from urllib.error import HTTPError
    result = []
    for name, repository in plugin_catalogue():
        try:
            info = github_request('repos/' + repository)
            release = github_request('repos/' + repository + '/releases/latest')
        except HTTPError as error:
            if error.code == 404:
                continue
            if error.code in (403, 429):
                from urllib.request import Request, urlopen
                from urllib.parse import unquote
                try:
                    with urlopen(Request('https://github.com/' + repository + '/releases/latest', headers={'User-Agent': 'Playlite'}), timeout=30) as response:
                        tag = unquote(response.geturl().rsplit('/', 1)[-1])
                    result.append(dict(name=name, repository=repository, description='', version=tag, private=False))
                    continue
                except HTTPError as public_error:
                    if public_error.code == 404:
                        continue
                    raise ValueError('Could not load public plugin releases. Try again later.') from None
            raise ValueError('GitHub could not list plugins (access denied or rate limit).') from None
        result.append(dict(name=name, repository=info.get('full_name') or repository, description=info.get('description') or '',
                           version=release['tag_name'], private=info['private']))
    return result


def install_github(repository, version='latest', directory=None):
    repository = repository.strip().removeprefix('https://github.com/').removesuffix('.git').rstrip('/')
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository):
        raise ValueError('Enter a GitHub repository as owner/repository.')
    release_path = 'latest' if version == 'latest' else 'tags/' + version
    authenticated = bool(github_token())
    if authenticated:
        release = github_request('repos/' + repository + '/releases/' + release_path)
        assets = {asset['name']: asset for asset in release['assets']}
    with tempfile.TemporaryDirectory(prefix='playlite-plugin-download-') as temporary:
        for name in ('plugin.zip', 'SHA256SUMS'):
            if authenticated:
                asset = assets[name]
                data = github_request('repos/' + repository + '/releases/assets/' + str(asset['id']), binary=True)
            else:
                from urllib.request import Request, urlopen
                from urllib.parse import quote
                path = 'latest/download/' if version == 'latest' else 'download/' + quote(version, safe='') + '/'
                url = 'https://github.com/' + repository + '/releases/' + path + name
                with urlopen(Request(url, headers={'User-Agent': 'Playlite'}), timeout=30) as response:
                    data = response.read()
            (Path(temporary) / name).write_bytes(data)
        import hashlib
        archive = Path(temporary) / 'plugin.zip'
        expected = next(line.split()[0] for line in (Path(temporary) / 'SHA256SUMS').read_text().splitlines()
                        if line.split()[-1].lstrip('*') == 'plugin.zip')
        if hashlib.sha256(archive.read_bytes()).hexdigest() != expected:
            raise ValueError('Plugin download checksum does not match.')
        return install_archive(archive, directory, repository)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='playlite-plugins')
    commands = parser.add_subparsers(dest='command', required=True)
    install = commands.add_parser('install', help='Install/update a plugin from its GitHub release')
    install.add_argument('repository')
    install.add_argument('--version', default='latest')
    commands.add_parser('list', help='List installed plugins')
    args = parser.parse_args(argv)
    try:
        if args.command == 'list':
            print(json.dumps(installed_plugins(), indent=2))
        else:
            result = install_github(args.repository, args.version)
            print(f"Installed {result['name']} {result['version']}. Restart Playlite to load it.")
        return 0
    except Exception as error:
        print(f'Could not install plugin: {error}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
