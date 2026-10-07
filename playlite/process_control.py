"""Terminate identified game processes without signalling reused process IDs."""
import os
import signal
import time
from pathlib import Path


def alive(record):
    try:
        path = Path('/proc') / str(record['pid'])
        fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
        return (record['pid'] != os.getpid() and path.stat().st_uid == os.getuid()
                and fields[0] != 'Z' and fields[19] == record['start'])
    except (OSError, IndexError):
        return False


def terminate_processes(records, grace=3):
    records = list({record['pid']: record for record in records}.values())
    targets = [record for record in records if alive(record)]
    if not targets:
        return 0
    def send(record, sig):
        if alive(record):
            try:
                os.kill(record['pid'], sig)
            except ProcessLookupError:
                pass
    for record in targets:
        send(record, signal.SIGTERM)
    deadline = time.monotonic() + grace
    while any(alive(record) for record in targets) and time.monotonic() < deadline:
        time.sleep(0.1)
    for record in targets:
        send(record, signal.SIGKILL)
    return len(targets)
