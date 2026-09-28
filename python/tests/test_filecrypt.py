import os

import pytest

from fragmentlab.filecrypt import HEADER_BYTES, SEGMENT, DecryptionError, decrypt_file, encrypt_file

KEY = bytes(range(32))


@pytest.mark.parametrize("size", [0, 1, SEGMENT - 1, SEGMENT, SEGMENT + 1, 3 * SEGMENT + 7])
def test_round_trip(tmp_path, size):
    plain, sealed, back = tmp_path / "p", tmp_path / "s", tmp_path / "b"
    plain.write_bytes(os.urandom(size))
    encrypt_file(KEY, plain, sealed)
    decrypt_file(KEY, sealed, back)
    assert back.read_bytes() == plain.read_bytes()


def _sealed(tmp_path, size=2 * SEGMENT + 10):
    plain, sealed = tmp_path / "p", tmp_path / "s"
    plain.write_bytes(os.urandom(size))
    encrypt_file(KEY, plain, sealed)
    return sealed


def test_wrong_key_fails_and_leaves_no_output(tmp_path):
    back = tmp_path / "b"
    with pytest.raises(DecryptionError):
        decrypt_file(bytes(32), _sealed(tmp_path), back)
    assert not back.exists() and not (tmp_path / "b.partial").exists()


def test_a_flipped_bit_fails(tmp_path):
    sealed = _sealed(tmp_path)
    data = bytearray(sealed.read_bytes())
    data[100] ^= 1
    sealed.write_bytes(bytes(data))
    with pytest.raises(DecryptionError):
        decrypt_file(KEY, sealed, tmp_path / "b")


def test_dropping_the_last_segment_fails(tmp_path):
    sealed = _sealed(tmp_path)
    data = sealed.read_bytes()
    sealed.write_bytes(data[: HEADER_BYTES + 2 * (SEGMENT + 16)])
    with pytest.raises(DecryptionError):
        decrypt_file(KEY, sealed, tmp_path / "b")


def test_not_our_format(tmp_path):
    junk = tmp_path / "j"
    junk.write_bytes(b"hello world, not encrypted")
    with pytest.raises(DecryptionError):
        decrypt_file(KEY, junk, tmp_path / "b")


def test_decrypted_output_is_owner_only(tmp_path):
    back = tmp_path / "b"
    decrypt_file(KEY, _sealed(tmp_path), back)
    assert back.stat().st_mode & 0o777 == 0o600


def test_same_key_same_plaintext_gives_different_files(tmp_path):
    plain = tmp_path / "p"
    plain.write_bytes(b"x" * 100)
    encrypt_file(KEY, plain, tmp_path / "s1")
    encrypt_file(KEY, plain, tmp_path / "s2")
    s1, s2 = (tmp_path / "s1").read_bytes(), (tmp_path / "s2").read_bytes()
    assert s1[10:42] != s2[10:42] and s1[HEADER_BYTES:] != s2[HEADER_BYTES:]


def test_a_short_key_is_refused(tmp_path):
    plain = tmp_path / "p"
    plain.write_bytes(b"x")
    with pytest.raises(ValueError):
        encrypt_file(bytes(16), plain, tmp_path / "s")
