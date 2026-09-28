import pytest
from cryptography.hazmat.primitives import serialization

from fragmentlab import keys
from fragmentlab.pool import FragmentPool


def test_bech32_matches_bip173():
    # BIP-173 valid test string "a12uel5l": hrp "a", empty data
    assert keys.bech32_encode("a", b"") == "a12uel5l"


def test_ed25519_pair_signs_and_verifies(demo):
    fragment, _ = demo
    private_pem, public_pem = keys.ed25519_pem(FragmentPool(fragment))
    private = serialization.load_pem_private_key(private_pem, None)
    public = serialization.load_pem_public_key(public_pem)
    public.verify(private.sign(b"hello"), b"hello")


def test_x25519_pair_loads(demo):
    fragment, _ = demo
    private_pem, _ = keys.x25519_pem(FragmentPool(fragment))
    assert serialization.load_pem_private_key(private_pem, None)


def test_age_identity_round_trips_through_rage(demo):
    pyrage = pytest.importorskip("pyrage")
    fragment, _ = demo
    secret, public = keys.age_identity(FragmentPool(fragment))
    assert secret.startswith("AGE-SECRET-KEY-1") and public.startswith("age1")
    identity = pyrage.x25519.Identity.from_str(secret)
    assert str(identity.to_public()) == public
    sealed = pyrage.encrypt(b"quantum", [pyrage.x25519.Recipient.from_str(public)])
    assert pyrage.decrypt(sealed, [identity]) == b"quantum"


def test_every_key_is_different(demo):
    fragment, _ = demo
    pool = FragmentPool(fragment)
    assert keys.age_identity(pool) != keys.age_identity(pool)
