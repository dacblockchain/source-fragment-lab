import json

import pytest

from fragmentlab import proof


def test_the_demo_fragment_verifies(demo):
    fragment, proof_path = demo
    results = proof.verify_file(fragment, proof.load(proof_path))
    assert [r.version for r in results] == [1, 2]
    assert all(r.ok for r in results)


def test_one_flipped_bit_breaks_its_range(demo):
    fragment, proof_path = demo
    data = bytearray(fragment.read_bytes())
    data[2048 * 8] ^= 1  # inside the second range
    fragment.write_bytes(bytes(data))
    results = proof.verify_file(fragment, proof.load(proof_path))
    assert [r.ok for r in results] == [True, False]


def test_a_truncated_file_is_refused(demo):
    fragment, proof_path = demo
    fragment.write_bytes(fragment.read_bytes()[:-1])
    with pytest.raises(proof.ProofError):
        proof.verify_file(fragment, proof.load(proof_path))


def test_a_missing_sibling_is_refused(demo):
    fragment, proof_path = demo
    doc = proof.load(proof_path)
    step = next(s for s in doc["ranges"][0]["proof"] if s["left"] or s["right"])
    step["left"] = step["right"] = None
    with pytest.raises(proof.ProofError):
        proof.verify_file(fragment, doc)


def test_ranges_must_tile_the_file(demo):
    fragment, proof_path = demo
    doc = proof.load(proof_path)
    doc["ranges"][1]["file_offset"] += 2048
    with pytest.raises(proof.ProofError):
        proof.verify_file(fragment, doc)


def test_unknown_formats_are_refused(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"format": "something/else", "hash": "sha256"}))
    with pytest.raises(proof.ProofError):
        proof.load(path)


def test_single_leaf_tree_has_an_empty_proof():
    leaf = b"\x11" * 32
    assert proof.rebuild_root([leaf], 0, 1, []) == leaf


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d.update(chunk_size="2048"),
        lambda d: d.update(ranges=[]),
        lambda d: d["ranges"][0].update(start="0"),
        lambda d: d["ranges"][0].update(root="0x1234"),
        lambda d: d["ranges"][0].pop("leaf_count"),
        lambda d: d["ranges"][0]["proof"].append("not an object"),
        lambda d: d["ranges"][0]["proof"][0].update(left="zz"),
    ],
)
def test_malformed_proofs_raise_proof_error(demo, tmp_path, mutate):
    _, proof_path = demo
    doc = json.loads(proof_path.read_text())
    mutate(doc)
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(doc))
    with pytest.raises(proof.ProofError):
        proof.load(bad)
