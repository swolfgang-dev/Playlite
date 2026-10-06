"""File receipts: cleanup removes only unchanged files installed by Playlite."""
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
from .storage import atomic_json

RECEIPT = '.playlite-owned.json'


def signature(path):
    if path.is_symlink():
        return {'link': os.readlink(path)}
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return {'sha256': digest.hexdigest()}


def receipt(root):
    path = Path(root) / RECEIPT
    if path.is_symlink():
        raise ValueError('Refusing a symlinked installation receipt.')
    document = json.loads(path.read_text())
    if document.get('schema') != 1 or not isinstance(document.get('files'), dict):
        raise ValueError('Invalid installation receipt.')
    if document.get('root') != str(Path(root).resolve()):
        raise ValueError('Installation receipt belongs to another directory; preserved.')
    for name in [*document['files'], *document.get('directories', [])]:
        parts = PurePosixPath(name)
        if parts.is_absolute() or '..' in parts.parts or '\\' in name or not parts.parts:
            raise ValueError('Unsafe installation receipt path.')
    return document['files']


def record_tree(root, excluded=(), installation_root=None):
    root = Path(root)
    excluded = set(excluded) | {RECEIPT}
    files = {}
    directories = []
    for directory, folders, names in os.walk(root, followlinks=False):
        for name in folders:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if not path.is_symlink() and relative not in excluded:
                directories.append(relative)
        for name in names + [name for name in folders if (Path(directory) / name).is_symlink()]:
            path = Path(directory) / name
            relative = path.relative_to(root).as_posix()
            if relative not in excluded:
                files[relative] = signature(path)
    atomic_json(root / RECEIPT, {'schema': 1, 'root': str(Path(installation_root or root).resolve()), 'files': files, 'directories': directories})
    (root / RECEIPT).chmod(0o600)


def file_inventory(root):
    root = Path(root)
    result = set()
    for directory, folders, names in os.walk(root, followlinks=False):
        for name in folders:
            if not (Path(directory) / name).is_symlink():
                result.add((Path(directory) / name).relative_to(root).as_posix())
        for name in names + [name for name in folders if (Path(directory) / name).is_symlink()]:
            result.add((Path(directory) / name).relative_to(root).as_posix())
    return result


def record_added_files(root, before, previously_owned=()):
    """Include dependency files installed by this operation, without adopting extras."""
    root = Path(root)
    files = receipt(root)
    for name in (file_inventory(root) - before) | set(previously_owned):
        path = root / name
        if name != RECEIPT and (path.is_file() or path.is_symlink()):
            files[name] = signature(path)
    document = json.loads((root / RECEIPT).read_text())
    document['files'] = files
    # New dependency directories are parents of files created by this operation.
    directories = set(document.get('directories', []))
    for name in file_inventory(root) - before:
        if (root / name).is_dir() and not (root / name).is_symlink(): directories.add(name)
        directories.update(parent.as_posix() for parent in PurePosixPath(name).parents if parent.parts and parent.as_posix() not in before)
    document['directories'] = sorted(directories)
    atomic_json(root / RECEIPT, document)
    (root / RECEIPT).chmod(0o600)


def unchanged(root, name, expected):
    root = Path(root)
    path = root / name
    if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents):
        return False
    return (path.is_file() or path.is_symlink()) and signature(path) == expected


def remove_owned(root, progress=None):
    root = Path(root)
    if root.is_symlink():
        raise ValueError('Refusing a symlinked installation directory.')
    files = receipt(root)
    document = json.loads((root / RECEIPT).read_text())
    for name, expected in files.items():
        path = root / name
        if unchanged(root, name, expected):
            path.unlink()
        elif path.exists() or path.is_symlink():
            if progress: progress('Preserved modified or external file: ' + str(path))
    (root / RECEIPT).unlink()
    for name in sorted(document.get('directories', []), key=lambda name: len(PurePosixPath(name).parts), reverse=True):
        path = root / name
        if any(parent.is_symlink() for parent in path.parents if parent != root and root in parent.parents): continue
        try: path.rmdir()
        except OSError: pass
    try: root.rmdir()
    except OSError: pass


def carry_external(previous, stage):
    """Retain user additions during plugin updates; refuse overlapping changes."""
    previous, stage = Path(previous), Path(stage)
    files = receipt(previous)
    owned_directories = set(json.loads((previous / RECEIPT).read_text()).get('directories', []))
    carried = []
    for directory, folders, names in os.walk(previous, followlinks=False):
        for name in folders:
            source = Path(directory) / name
            relative = source.relative_to(previous).as_posix()
            if source.is_symlink() or relative in owned_directories: continue
            target = stage / relative
            if target.is_symlink() or target.is_file():
                raise ValueError('Update conflicts with an external directory: ' + relative)
            target.mkdir(parents=True, exist_ok=True)
            carried.append(relative)
        for name in names + [name for name in folders if (Path(directory) / name).is_symlink()]:
            source = Path(directory) / name
            relative = source.relative_to(previous).as_posix()
            if relative == RECEIPT or (relative in files and unchanged(previous, relative, files[relative])):
                continue
            target = stage / relative
            if target.exists() or target.is_symlink():
                raise ValueError('Update would overwrite an externally added or modified file: ' + relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_symlink(): target.symlink_to(os.readlink(source))
            else: shutil.copy2(source, target)
            carried.append(relative)
    return carried
