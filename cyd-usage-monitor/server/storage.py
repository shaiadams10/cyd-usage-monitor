"""Atomic, process-safe storage helpers for monitor runtime JSON files."""
from __future__ import annotations

import json
import os
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, TypeVar

if os.name == "nt":
    import msvcrt
else:
    import fcntl


T = TypeVar("T")
_THREAD_LOCK = threading.RLock()
_LOCAL = threading.local()


@contextmanager
def data_lock(directory: Path):
    """Serialize read/modify/write transactions across threads and containers."""
    directory.mkdir(parents=True, exist_ok=True)
    with _THREAD_LOCK:
        depth = getattr(_LOCAL, "depth", 0)
        if depth:
            _LOCAL.depth = depth + 1
            try:
                yield
            finally:
                _LOCAL.depth -= 1
            return

        lock_path = directory / ".monitor-data.lock"
        with lock_path.open("a+b") as handle:
            try:
                os.chmod(lock_path, 0o600)
            except OSError:
                pass
            if os.name == "nt":
                if handle.seek(0, os.SEEK_END) == 0:
                    handle.write(b"0")
                    handle.flush()
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            _LOCAL.depth = 1
            try:
                yield
            finally:
                _LOCAL.depth = 0
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def read_json_unlocked(path: Path, default: T) -> T:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json_unlocked(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def read_json(path: Path, default: T) -> T:
    with data_lock(path.parent):
        return read_json_unlocked(path, default)


def write_json(path: Path, payload) -> None:
    with data_lock(path.parent):
        write_json_unlocked(path, payload)


def update_json(path: Path, default: T, mutate: Callable[[T], T | None]) -> T:
    """Update one JSON document without losing a concurrent writer's changes."""
    with data_lock(path.parent):
        payload = read_json_unlocked(path, default)
        replacement = mutate(payload)
        if replacement is not None:
            payload = replacement
        write_json_unlocked(path, payload)
        return payload
