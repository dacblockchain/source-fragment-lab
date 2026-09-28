"""A Source Fragment as a pool of never-reused bytes.

The cursor lives in a sidecar `<fragment>.cursor` file (docs/mixing.md). It is
rewritten atomically — write a unique temp file, then rename — so a crash can
lose at most the draw in progress, never rewind the cursor onto bytes already
used. Every read-modify-write of the cursor holds an exclusive lock on
`<fragment>.cursor.lock`, so two processes drawing from the same fragment at
once can never be handed the same bytes.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:  # POSIX
    import fcntl

    def _lock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_EX)

except ImportError:  # Windows
    import msvcrt

    def _lock(fd: int) -> None:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1)

from fragmentlab.mix import QUANTUM_BYTES, mix

CURSOR_FORMAT = "source-fragment-lab/cursor/v1"


class FragmentExhausted(Exception):
    """The fragment has fewer unused bytes than the draw needs."""


class FragmentPool:
    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise FileNotFoundError(f"no fragment at {self.path}")
        self.size = self.path.stat().st_size
        self.cursor_path = self.path.with_name(self.path.name + ".cursor")
        self.lock_path = self.path.with_name(self.path.name + ".cursor.lock")

    @contextmanager
    def _locked(self) -> Iterator[None]:
        """Exclusive across processes; released when the descriptor closes."""
        fd = os.open(self.lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _lock(fd)
            yield
        finally:
            os.close(fd)

    @property
    def consumed(self) -> int:
        if not self.cursor_path.exists():
            return 0
        try:
            data = json.loads(self.cursor_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unreadable cursor {self.cursor_path}: {exc}") from exc
        if data.get("format") != CURSOR_FORMAT or not isinstance(data.get("consumed"), int):
            raise ValueError(f"{self.cursor_path} is not a {CURSOR_FORMAT} cursor")
        if not 0 <= data["consumed"] <= self.size:
            raise ValueError(f"{self.cursor_path} points outside the fragment")
        return data["consumed"]

    @property
    def remaining(self) -> int:
        return self.size - self.consumed

    def take(self, n: int) -> bytes:
        """The next `n` unused bytes. They are marked used before being returned."""
        if n <= 0:
            raise ValueError("take at least one byte")
        with self._locked():
            start = self.consumed
            if start + n > self.size:
                raise FragmentExhausted(
                    f"{self.path.name} has {self.size - start} unused bytes, {n} needed"
                )
            data = self._read(start, n)
            self._save(start + n)
        return data

    def take_chunk(self, chunk_size: int = 2048) -> tuple[int, bytes]:
        """The next whole, chunk-aligned unused chunk, as (index, bytes).

        For values that will become PUBLIC, such as a draw's revealed chunk: taking
        it through the pool marks it used, so it can never also end up inside a
        secret. The unused tail of a partly used chunk is skipped.
        """
        with self._locked():
            index = -(-self.consumed // chunk_size)
            start = index * chunk_size
            if start + chunk_size > self.size:
                raise FragmentExhausted(f"{self.path.name} has no whole unused chunk left")
            data = self._read(start, chunk_size)
            self._save(start + chunk_size)
        return index, data

    def mixed(self, purpose: str, length: int) -> bytes:
        """Secret material: HKDF(os_random ‖ next 32 fragment bytes)."""
        return mix(self.take(QUANTUM_BYTES), purpose, length)

    def _read(self, start: int, n: int) -> bytes:
        with self.path.open("rb") as handle:
            handle.seek(start)
            data = handle.read(n)
        if len(data) != n:
            raise FragmentExhausted(f"{self.path.name} changed size while being read")
        return data

    def _save(self, consumed: int) -> None:
        tmp = self.cursor_path.with_name(f"{self.cursor_path.name}.{uuid.uuid4().hex}.tmp")
        try:
            tmp.write_text(json.dumps({"format": CURSOR_FORMAT, "consumed": consumed}) + "\n")
            os.replace(tmp, self.cursor_path)
        finally:
            tmp.unlink(missing_ok=True)
