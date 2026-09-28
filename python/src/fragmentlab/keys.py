"""Key generation from mixed entropy: Ed25519, X25519 and age identities.

The 32-byte private key comes from `pool.mixed(<purpose>, 32)`, i.e.
HKDF(os_random ‖ fragment), never from the fragment alone.
"""

from __future__ import annotations

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, x25519

from fragmentlab.pool import FragmentPool

_BECH32_ALPHABET = "qpzry9x8gf2tvdw0s3jn54khce6mua7l"
_BECH32_GEN = (0x3B6A57B2, 0x26508E6D, 0x1EA119FA, 0x3D4233DD, 0x2A1462B3)


def _polymod(values: list[int]) -> int:
    chk = 1
    for value in values:
        top = chk >> 25
        chk = (chk & 0x1FFFFFF) << 5 ^ value
        for i, gen in enumerate(_BECH32_GEN):
            chk ^= gen if (top >> i) & 1 else 0
    return chk


def _to_5bit(data: bytes) -> list[int]:
    acc, bits, out = 0, 0, []
    for byte in data:
        acc = (acc << 8) | byte
        bits += 8
        while bits >= 5:
            bits -= 5
            out.append((acc >> bits) & 31)
    if bits:
        out.append((acc << (5 - bits)) & 31)
    return out


def bech32_encode(hrp: str, data: bytes) -> str:
    """Bech32 (BIP-173, not bech32m), which is what age uses for its keys.

    BIP-173 caps strings at 90 characters; age deliberately ignores that cap,
    and so does this encoder.
    """
    hrp = hrp.lower()
    values = _to_5bit(data)
    expanded = [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp]
    polymod = _polymod(expanded + values + [0] * 6) ^ 1
    checksum = [(polymod >> 5 * (5 - i)) & 31 for i in range(6)]
    return hrp + "1" + "".join(_BECH32_ALPHABET[v] for v in values + checksum)


def ed25519_pem(pool: FragmentPool) -> tuple[bytes, bytes]:
    """(private PKCS#8 PEM, public SubjectPublicKeyInfo PEM)."""
    key = ed25519.Ed25519PrivateKey.from_private_bytes(pool.mixed("ed25519", 32))
    return _pem_pair(key)


def x25519_pem(pool: FragmentPool) -> tuple[bytes, bytes]:
    key = x25519.X25519PrivateKey.from_private_bytes(pool.mixed("x25519", 32))
    return _pem_pair(key)


def age_identity(pool: FragmentPool) -> tuple[str, str]:
    """(AGE-SECRET-KEY-1…, age1…) — usable with the `age` / `rage` tools as is."""
    secret = pool.mixed("age-x25519", 32)
    public = x25519.X25519PrivateKey.from_private_bytes(secret).public_key().public_bytes_raw()
    return bech32_encode("age-secret-key-", secret).upper(), bech32_encode("age", public)


def _pem_pair(key) -> tuple[bytes, bytes]:
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return private, public
