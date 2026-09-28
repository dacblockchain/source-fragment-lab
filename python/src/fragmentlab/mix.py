"""HKDF-SHA256 (RFC 5869) and the `source-fragment-lab/mix/v1` construction.

Standard library only: `hmac` + `hashlib`. See docs/mixing.md.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from collections.abc import Callable

HASH_LEN = 32
MAX_OUTPUT = 255 * HASH_LEN  # 8160 bytes, the RFC 5869 ceiling
MIX_SALT = b"source-fragment-lab/mix/v1"
LOCAL_BYTES = 32
QUANTUM_BYTES = 32


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac.new(salt or bytes(HASH_LEN), ikm, hashlib.sha256).digest()


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    if not 0 < length <= MAX_OUTPUT:
        raise ValueError(f"HKDF-SHA256 output must be 1..{MAX_OUTPUT} bytes, not {length}")
    out, block = b"", b""
    counter = 1
    while len(out) < length:
        block = hmac.new(prk, block + info + bytes([counter]), hashlib.sha256).digest()
        out += block
        counter += 1
    return out[:length]


def hkdf(ikm: bytes, salt: bytes, info: bytes, length: int) -> bytes:
    return hkdf_expand(hkdf_extract(salt, ikm), info, length)


def mix(quantum: bytes, purpose: str, length: int, *, local: bytes | None = None) -> bytes:
    """HKDF(local ‖ quantum) for one purpose. `local` defaults to fresh OS randomness.

    Passing `local` explicitly exists for tests only: a caller that supplies a
    fixed value throws away the half of the guarantee that protects against
    the operator.
    """
    if len(quantum) != QUANTUM_BYTES:
        raise ValueError(f"mix takes exactly {QUANTUM_BYTES} fragment bytes, not {len(quantum)}")
    if not purpose:
        raise ValueError("a purpose label is required, so two uses never share a key")
    local = os.urandom(LOCAL_BYTES) if local is None else local
    if len(local) != LOCAL_BYTES:
        raise ValueError(f"local randomness must be {LOCAL_BYTES} bytes")
    return hkdf(local + quantum, MIX_SALT, purpose.encode(), length)


ByteSource = Callable[[int], bytes]


def randbelow(n: int, read: ByteSource) -> int:
    """A uniform integer in [0, n) by rejection sampling (docs/mixing.md)."""
    if n < 1:
        raise ValueError(f"randbelow needs n >= 1, not {n}")
    if n == 1:
        return 0
    bits = (n - 1).bit_length()
    size = (bits + 7) // 8
    mask = (1 << bits) - 1
    while True:
        x = int.from_bytes(read(size), "big") & mask
        if x < n:
            return x


class ByteStream:
    """Serve a fixed byte string sequentially; raise when it runs out."""

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._pos = 0

    def __call__(self, n: int) -> bytes:
        if self._pos + n > len(self._data):
            raise ValueError("the random stream ran out")
        out = self._data[self._pos : self._pos + n]
        self._pos += n
        return out
