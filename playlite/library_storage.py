"""Serialize library read/modify/write transactions across workers and processes."""
from contextlib import contextmanager
import fcntl
import threading
from pathlib import Path

_LOCK = threading.RLock()


@contextmanager
def library_lock(data):
    data = Path(data)
    data.mkdir(parents=True, exist_ok=True)
    with _LOCK, (data / 'library.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
