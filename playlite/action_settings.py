"""Coordinate plugin-owned launcher file updates with a library save."""
from contextlib import contextmanager
from PyQt6.QtCore import QIODevice, QSaveFile


@contextmanager
def update_action_files(changes, update):
    """Apply validated changes and restore our writes if the save fails.

    The caller holds the library lock. External launchers do not share that
    lock, so rollback checks the bytes we wrote and preserves newer edits.
    Each update callback must replace its file atomically or leave it intact.
    """
    originals = {}
    try:
        for path, value in changes.items():
            original = path.read_bytes()
            update(path, value)
            written = path.read_bytes()
            if written != original:
                originals[path] = (original, written)
        yield
    except BaseException:
        problems = []
        for path, (original, written) in reversed(list(originals.items())):
            try:
                if path.read_bytes() != written:
                    raise ValueError('Launcher configuration changed during save; the newer changes were preserved.')
                output = QSaveFile(str(path))
                if not output.open(QIODevice.OpenModeFlag.WriteOnly):
                    raise OSError(output.errorString())
                if output.write(original) != len(original):
                    output.cancelWriting()
                    raise OSError(output.errorString())
                if not output.commit():
                    raise OSError(output.errorString())
            except (OSError, ValueError) as error:
                # One conflicting file must not prevent the other rollbacks.
                problems.append(f'{path}: {error}')
        if problems:
            raise ValueError('\n'.join(problems))
        raise
