from __future__ import annotations

import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def acquire_output_lock(output_csv_path: Path):
    """Acquire an exclusive file lock for atomic CSV writes.

    Creates parent directories for the output path (the lock file is created
    adjacent to it), then uses fcntl.flock for cross-process mutual exclusion.
    Raises RuntimeError if another step2 process holds the lock.
    """
    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = output_csv_path.with_name(f"{output_csv_path.name}.lock")
    with lock_path.open("a+b") as handle:
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RuntimeError(f"Another step2 process is already writing to {output_csv_path}.") from exc
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
