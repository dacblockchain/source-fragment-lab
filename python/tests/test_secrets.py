import pytest

from fragmentlab import secrets_gen
from fragmentlab.pool import FragmentPool


def test_bip39_reference_vectors():
    words = secrets_gen.mnemonic_from_entropy(bytes(16)).split()
    assert words == ["abandon"] * 11 + ["about"]
    words = secrets_gen.mnemonic_from_entropy(b"\xff" * 32).split()
    assert words == ["zoo"] * 23 + ["vote"]
    # Trezor vector: 7f7f… (16 bytes)
    assert secrets_gen.mnemonic_from_entropy(b"\x7f" * 16) == (
        "legal winner thank year wave sausage worth useful legal winner thank yellow"
    )


@pytest.mark.parametrize("words", [12, 24])
def test_mnemonic_length(demo, words):
    fragment, _ = demo
    assert len(secrets_gen.mnemonic(FragmentPool(fragment), words).split()) == words


def test_password_uses_only_the_alphabet(demo):
    fragment, _ = demo
    pw = secrets_gen.password(FragmentPool(fragment), 64)
    assert len(pw) == 64 and set(pw) <= set(secrets_gen.PASSWORD_ALPHABET)


def test_passphrase_words_come_from_the_list(demo):
    fragment, _ = demo
    phrase = secrets_gen.passphrase(FragmentPool(fragment), 7)
    assert all(w in secrets_gen.wordlist() for w in phrase.split("-"))


def test_bad_parameters(demo):
    fragment, _ = demo
    pool = FragmentPool(fragment)
    with pytest.raises(ValueError):
        secrets_gen.mnemonic(pool, 13)
    with pytest.raises(ValueError):
        secrets_gen.password(pool, 4)
    with pytest.raises(ValueError):
        secrets_gen.password(pool, 12, "aa")
