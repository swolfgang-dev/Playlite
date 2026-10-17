"""Atomic storage shared by the application and plugins."""
import json
import os
from pathlib import Path
import stat
import tempfile


def atomic_json(path, data, *, mode=None, sort_keys=False):
    """Replace JSON only after serialization and writing succeed.

    Existing permissions are retained unless the caller specifies a mode. New
    files are private by default, including while they are being written.
    """
    content = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=sort_keys).encode('utf-8')
    atomic_bytes(path, content, mode=mode)


def atomic_bytes(path, content, *, mode=None):
    """Atomically replace bytes, retaining existing permissions by default."""
    path = Path(path)
    if mode is None:
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            mode = 0o600
    descriptor, name = tempfile.mkstemp(prefix='.' + path.name + '-', suffix='.tmp', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fchmod(stream.fileno(), mode)
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)

