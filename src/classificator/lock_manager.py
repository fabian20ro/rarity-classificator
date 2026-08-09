from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def acquire_output_lock(output_csv_path):
    """Acquire an exclusive file lock for atomic CSV writes.

    Creates parent directories for the output path (the lock file is created
    adjacent to it), then uses fcntl.flock for cross-process mutual exclusion.
    Raises RuntimeError if another step2 process holds the lock.
    """
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_csv_path.with_name(f"{output_csv_path.name}.lock")
    handle = lock_path.open("a+b")
    try:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(
                f"Another step2 process is already writing to {output_csv_path}."
            ) from exc
        yield
    finally:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        handle.close()
