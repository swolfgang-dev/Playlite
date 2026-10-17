"""Serialize library read/modify/write transactions across workers and processes."""
from contextlib import contextmanager
import fcntl
import threading
from pathlib import Path

_LOCK = threading.RLock()
_HELD = threading.local()


@contextmanager
def library_lock(data):
    data = Path(data).resolve()
    data.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        held = getattr(_HELD, 'paths', set())
        if data in held:
            yield
            return
        with (data / 'library.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            _HELD.paths = held
            held.add(data)
            try:
                yield
            finally:
                held.remove(data)
                fcntl.flock(lock, fcntl.LOCK_UN)
