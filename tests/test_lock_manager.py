import fcntl
from pathlib import Path

import pytest

from src.classificator.lock_manager import acquire_output_lock


def test_lock_acquires_and_releases_for_next_writer(tmp_path):
    destination = tmp_path / "nested" / "run.csv"
    with acquire_output_lock(destination):
        assert destination.with_name("run.csv.lock").exists()
        assert not destination.exists()
    with acquire_output_lock(destination):
        pass


@pytest.mark.parametrize("body_error", [None, ValueError("scoring failed"), KeyboardInterrupt()])
def test_lock_closes_handle_even_when_body_raises(tmp_path, monkeypatch, body_error):
    opened = []
    real_open = Path.open

    def track_open(path, *args, **kwargs):
        handle = real_open(path, *args, **kwargs)
        opened.append(handle)
        return handle

    monkeypatch.setattr(Path, "open", track_open)
    destination = tmp_path / "run.csv"

    def use_lock():
        with acquire_output_lock(destination):
            if body_error is not None:
                raise body_error

    if body_error is None:
        use_lock()
    else:
        with pytest.raises(type(body_error)):
            use_lock()
    assert opened[0].closed
    with acquire_output_lock(destination):
        pass


def test_contended_lock_reports_writer_and_closes_rejected_handle(tmp_path, monkeypatch):
    destination = tmp_path / "run.csv"
    with destination.with_name("run.csv.lock").open("a+b") as held:
        fcntl.flock(held, fcntl.LOCK_EX | fcntl.LOCK_NB)
        opened = []
        real_open = Path.open

        def track_open(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            opened.append(handle)
            return handle

        monkeypatch.setattr(Path, "open", track_open)
        with pytest.raises(RuntimeError, match="Another step2 process"):
            with acquire_output_lock(destination):
                pytest.fail("A contending writer acquired an exclusive lock")
        assert opened[0].closed

    with acquire_output_lock(destination):
        pass
