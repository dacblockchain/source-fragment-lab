"""The verifiable draw, `source-fragment-lab/draw/v1` (docs/draw.md).

Deliberately NOT mixed with local randomness: the point is that anyone can
recompute it. Fairness comes from the commit (chunk hash published before the
entries close) plus a future block hash the organizer cannot predict.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fragmentlab.mix import MAX_OUTPUT, hkdf, randbelow

DRAW_DOMAIN = b"source-fragment-lab/draw/v1"
CHUNK_SIZE = 2048


def normalise_entries(text: str) -> list[str]:
    """One entry per line, trimmed, empty lines dropped, order kept; duplicates refused."""
    entries = [line.strip() for line in text.splitlines() if line.strip()]
    seen: set[str] = set()
    for entry in entries:
        if entry in seen:
            raise ValueError(f"duplicate entry {entry!r}: make every line unique first")
        seen.add(entry)
    return entries


def entries_hash(entries: list[str]) -> bytes:
    return hashlib.sha256("\n".join(entries).encode()).digest()


def read_chunk(path, index: int) -> bytes:
    """Chunk `index` of a fragment file, read with one seek (files can be ~4 GB)."""
    if index < 0:
        raise ValueError("chunk index must be >= 0")
    with open(path, "rb") as handle:
        handle.seek(index * CHUNK_SIZE)
        chunk = handle.read(CHUNK_SIZE)
    if len(chunk) != CHUNK_SIZE:
        raise ValueError(f"chunk {index} is not inside {path}")
    return chunk


def chunk_commitment(chunk: bytes) -> str:
    return "0x" + hashlib.sha256(chunk).hexdigest()


class _SeedStream:
    def __init__(self, chunk: bytes, salt: bytes, info: bytes) -> None:
        self._chunk, self._salt, self._info = chunk, salt, info
        self._buffer, self._block = b"", 0

    def __call__(self, n: int) -> bytes:
        while len(self._buffer) < n:
            info = self._info + self._block.to_bytes(4, "big")
            self._buffer += hkdf(self._chunk, self._salt, info, MAX_OUTPUT)
            self._block += 1
        out, self._buffer = self._buffer[:n], self._buffer[n:]
        return out


@dataclass(frozen=True)
class DrawResult:
    winners: list[str]
    entries_hash: str
    chunk_commitment: str
    block_hash: str


def run(chunk: bytes, block_hash_hex: str, entries: list[str], winners: int) -> DrawResult:
    if len(chunk) != CHUNK_SIZE:
        raise ValueError(f"a draw uses one whole {CHUNK_SIZE}-byte chunk, not {len(chunk)} bytes")
    salt = bytes.fromhex(block_hash_hex.removeprefix("0x"))
    if len(salt) != 32:
        raise ValueError("the block hash must be 32 bytes")
    if len(set(entries)) != len(entries):
        raise ValueError("entries must be unique")
    if not 1 <= winners <= len(entries):
        raise ValueError(f"winners must be 1..{len(entries)}, not {winners}")
    digest = entries_hash(entries)
    read = _SeedStream(chunk, salt, DRAW_DOMAIN + digest)
    pool, picked = list(entries), []
    for step in range(winners):
        j = len(pool) - 1 - step
        r = randbelow(j + 1, read)
        pool[j], pool[r] = pool[r], pool[j]
        picked.append(pool[j])
    return DrawResult(picked, "0x" + digest.hex(), chunk_commitment(chunk), "0x" + salt.hex())
