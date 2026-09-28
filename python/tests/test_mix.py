import pytest

from fragmentlab.mix import ByteStream, hkdf, mix, randbelow


def test_hkdf_rfc5869_case_1():
    okm = hkdf(
        bytes.fromhex("0b" * 22),
        bytes.fromhex("000102030405060708090a0b0c"),
        bytes.fromhex("f0f1f2f3f4f5f6f7f8f9"),
        42,
    )
    assert okm.hex() == (
        "3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865"
    )


def test_hkdf_rfc5869_case_3_empty_salt_and_info():
    okm = hkdf(bytes.fromhex("0b" * 22), b"", b"", 42)
    assert okm.hex() == (
        "8da4e775a563c18f715f802a063c5a31b8a11f5c5ee1879ec3454e5f3c738d2d9d201395faa4b61a96c8"
    )


def test_hkdf_refuses_oversized_output():
    with pytest.raises(ValueError):
        hkdf(b"k", b"s", b"i", 8161)


def test_mix_matches_the_shared_vector(vectors):
    v = vectors["mix"]
    out = mix(bytes.fromhex(v["quantum"]), v["purpose"], v["length"], local=bytes.fromhex(v["local"]))
    assert out.hex() == v["output"]


def test_mix_uses_fresh_local_randomness_by_default():
    quantum = bytes(32)
    assert mix(quantum, "x", 32) != mix(quantum, "x", 32)


def test_mix_separates_purposes():
    local, quantum = bytes(32), bytes(range(32))
    assert mix(quantum, "a", 32, local=local) != mix(quantum, "b", 32, local=local)


@pytest.mark.parametrize("quantum,purpose", [(bytes(31), "x"), (bytes(32), "")])
def test_mix_rejects_bad_input(quantum, purpose):
    with pytest.raises(ValueError):
        mix(quantum, purpose, 32)


def test_randbelow_matches_the_shared_vector(vectors):
    v = vectors["randbelow"]
    read = ByteStream(bytes.fromhex(v["stream"]))
    assert [randbelow(n, read) for n in v["bounds"]] == v["outputs"]


def test_randbelow_is_unbiased_on_the_edge_case():
    # 0x80 masked to 7 bits = 0 < 100 → 0; 0x7f → 127 ≥ 100 rejected, then 0x05 → 5
    assert randbelow(100, ByteStream(bytes([0x80]))) == 0
    assert randbelow(100, ByteStream(bytes([0x7F, 0x05]))) == 5


def test_randbelow_one_reads_nothing():
    assert randbelow(1, ByteStream(b"")) == 0


def test_stream_runs_out_loudly():
    with pytest.raises(ValueError):
        ByteStream(b"\x00")(2)
    with pytest.raises(ValueError):
        randbelow(0, ByteStream(b"\x00"))
