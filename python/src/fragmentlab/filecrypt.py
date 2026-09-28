"""Encrypt a file of any size with a key made from mixed entropy.

This is an EXAMPLE of how to use the key, built on AES-256-GCM in the STREAM
construction (Hoang, Reyhanitabar, Rogaway, Vizár 2015 — the one age and Tink
use): the file is cut into 64 KiB segments, each sealed with a nonce made of a
random 7-byte prefix, a 4-byte segment counter and a 1-byte "last segment" flag.
Reordering, dropping or truncating segments therefore fails authentication.

The key file is never used to encrypt directly: every file gets a fresh
32-byte random salt, and the AES key is HKDF(key file, salt). One key file can
therefore protect any number of files without the 56-bit nonce prefix ever
being the only thing standing between two files and a GCM nonce collision.

For real-world use, prefer an audited tool: `fragmentlab keys age` gives you an
age identity made from the same mixed entropy, and `age` does the rest.

File layout:  magic "SFL-AEAD-1" (10 B) ‖ salt (32 B) ‖ nonce prefix (7 B) ‖ sealed segments
Segment:      ciphertext ‖ 16-byte tag, 64 KiB of plaintext except the last
Decrypted output is created owner-only (0600): it is whatever you chose to protect.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from fragmentlab.mix import hkdf

MAGIC = b"SFL-AEAD-1"
SALT_BYTES = 32
PREFIX_BYTES = 7
HEADER_BYTES = len(MAGIC) + SALT_BYTES + PREFIX_BYTES
SEGMENT = 64 * 1024
TAG = 16
KEY_BYTES = 32
MAX_SEGMENTS = 2**32


class DecryptionError(Exception):
    """Wrong key, or the file was modified, reordered or truncated."""


def _nonce(prefix: bytes, counter: int, last: bool) -> bytes:
    if counter >= MAX_SEGMENTS:
        raise ValueError("file too large: at most 2^32 segments")
    return prefix + counter.to_bytes(4, "big") + (b"\x01" if last else b"\x00")


def _file_key(key: bytes, salt: bytes) -> AESGCM:
    if len(key) != KEY_BYTES:
        raise ValueError("AES-256 needs a 32-byte key")
    return AESGCM(hkdf(key, salt, MAGIC, KEY_BYTES))


def _create_private(path: Path):
    path.unlink(missing_ok=True)  # a leftover file would keep its old, wider mode
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(fd, "wb")


def encrypt_file(key: bytes, source: Path, target: Path) -> None:
    salt, prefix = os.urandom(SALT_BYTES), os.urandom(PREFIX_BYTES)
    aead = _file_key(key, salt)
    with source.open("rb") as src, target.open("wb") as dst:
        dst.write(MAGIC + salt + prefix)
        counter, segment = 0, src.read(SEGMENT)
        while True:
            following = src.read(SEGMENT)
            last = not following
            dst.write(aead.encrypt(_nonce(prefix, counter, last), segment, MAGIC))
            if last:
                return
            counter, segment = counter + 1, following


def decrypt_file(key: bytes, source: Path, target: Path) -> None:
    """Writes to a temp file and renames only once the LAST segment authenticates."""
    tmp = target.with_name(target.name + ".partial")
    try:
        with source.open("rb") as src, _create_private(tmp) as dst:
            header = src.read(HEADER_BYTES)
            if header[: len(MAGIC)] != MAGIC or len(header) != HEADER_BYTES:
                raise DecryptionError("not a fragmentlab encrypted file")
            salt = header[len(MAGIC) : len(MAGIC) + SALT_BYTES]
            aead, prefix, counter = _file_key(key, salt), header[len(MAGIC) + SALT_BYTES :], 0
            sealed = src.read(SEGMENT + TAG)
            while True:
                following = src.read(SEGMENT + TAG)
                last = not following
                try:
                    dst.write(aead.decrypt(_nonce(prefix, counter, last), sealed, MAGIC))
                except InvalidTag as exc:
                    raise DecryptionError("wrong key, or the file was modified") from exc
                if last:
                    break
                counter, sealed = counter + 1, following
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
