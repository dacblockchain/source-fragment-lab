"""BIP-39 mnemonics, passwords and passphrases from mixed entropy."""

from __future__ import annotations

import hashlib
import string
from importlib import resources

from fragmentlab.mix import ByteStream, randbelow
from fragmentlab.pool import FragmentPool

# SHA-256 of the canonical English list from github.com/bitcoin/bips (bip-0039/english.txt).
BIP39_SHA256 = "2f5eed53a4727b4bf8880d8f3f199efc90e58503646d9ff8eff3a2ed3b24dbda"
MNEMONIC_WORDS = {12: 16, 15: 20, 18: 24, 21: 28, 24: 32}  # words → entropy bytes
PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!#$%&*+-=?@^_~"
STREAM_BYTES = 1024  # plenty for any password: rejection sampling needs < 2 tries per symbol


def wordlist() -> list[str]:
    raw = resources.files("fragmentlab").joinpath("bip39_english.txt").read_bytes()
    if hashlib.sha256(raw).hexdigest() != BIP39_SHA256:
        raise RuntimeError("the bundled BIP-39 wordlist is not the canonical one")
    words = raw.decode().split()
    if len(words) != 2048:
        raise RuntimeError("the BIP-39 wordlist must have 2048 words")
    return words


def mnemonic_from_entropy(entropy: bytes) -> str:
    """BIP-39: entropy ‖ first ENT/32 bits of SHA-256(entropy), read in 11-bit words."""
    if len(entropy) not in MNEMONIC_WORDS.values():
        raise ValueError("BIP-39 entropy is 16, 20, 24, 28 or 32 bytes")
    bits = len(entropy) * 8
    checksum_bits = bits // 32
    value = int.from_bytes(entropy, "big") << checksum_bits
    value |= hashlib.sha256(entropy).digest()[0] >> (8 - checksum_bits)
    words = wordlist()
    count = (bits + checksum_bits) // 11
    return " ".join(words[(value >> 11 * (count - 1 - i)) & 2047] for i in range(count))


def mnemonic(pool: FragmentPool, words: int = 24) -> str:
    if words not in MNEMONIC_WORDS:
        raise ValueError(f"a BIP-39 mnemonic has {sorted(MNEMONIC_WORDS)} words")
    return mnemonic_from_entropy(pool.mixed("bip39", MNEMONIC_WORDS[words]))


def password(pool: FragmentPool, length: int = 24, alphabet: str = PASSWORD_ALPHABET) -> str:
    if not 8 <= length <= 256:
        raise ValueError("password length must be 8..256")
    if len(set(alphabet)) != len(alphabet) or len(alphabet) < 2:
        raise ValueError("the alphabet needs at least two distinct characters")
    read = ByteStream(pool.mixed("password", STREAM_BYTES))
    return "".join(alphabet[randbelow(len(alphabet), read)] for _ in range(length))


def passphrase(pool: FragmentPool, words: int = 7, separator: str = "-") -> str:
    """Words from the BIP-39 list: 11 bits each, so 7 words ≈ 77 bits."""
    if not 4 <= words <= 64:
        raise ValueError("a passphrase has 4..64 words")
    read = ByteStream(pool.mixed("passphrase", STREAM_BYTES))
    wl = wordlist()
    return separator.join(wl[randbelow(len(wl), read)] for _ in range(words))
