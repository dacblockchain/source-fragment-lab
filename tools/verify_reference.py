#!/usr/bin/env python3
# Verbatim copy of dac-interstellar docs/verification/verify_source_fragment.py (the
# verifier Interstellar links to), kept here so CI proves the demo data matches it.
"""Verify a Source Fragment against its proof — standard library only.

    python3 verify_source_fragment.py source-fragment-7.bin source-fragment-7.proof.json

Streams the file (a fragment can be ~4 GB), hashes each 2,048-byte chunk with
SHA-256, and rebuilds every range's Merkle root from those hashes and the
siblings in the proof. Prints each root; compare it with `rootOf(version)` on
the anchor contract, at the transaction the proof names. Trust nothing else.

Tree shape: leaf = SHA-256(chunk); node = SHA-256(left ‖ right); an odd last
node is promoted unchanged.
"""

from __future__ import annotations

import hashlib
import json
import sys


def level_lengths(n: int) -> list[int]:
    out = [n]
    while out[-1] > 1:
        out.append((out[-1] + 1) // 2)
    return out


def rebuild_root(leaves: list[bytes], start: int, leaf_count: int, proof: list[dict]) -> bytes:
    lengths = level_lengths(leaf_count)
    if len(proof) != len(lengths) - 1:
        raise ValueError("proof depth does not match the leaf count")
    nodes, lo = leaves, start
    for step, length in zip(proof, lengths):
        last = lo + len(nodes) - 1
        need_left, need_right = lo % 2 == 1, last % 2 == 0 and last + 1 < length
        if (step["left"] is not None) != need_left or (step["right"] is not None) != need_right:
            raise ValueError("proof siblings do not match the range")
        run = ([bytes.fromhex(step["left"][2:])] if need_left else []) + nodes
        run += [bytes.fromhex(step["right"][2:])] if need_right else []
        nodes = [
            hashlib.sha256(run[i] + run[i + 1]).digest() if i + 1 < len(run) else run[i]
            for i in range(0, len(run), 2)
        ]
        lo = (lo - 1 if need_left else lo) // 2
    if lo != 0 or len(nodes) != 1:
        raise ValueError("the range did not reduce to one root")
    return nodes[0]


def verify(file_path: str, proof: dict) -> list[tuple[int, bool]]:
    size = proof["chunk_size"]
    results = []
    with open(file_path, "rb") as handle:
        for r in sorted(proof["ranges"], key=lambda item: item["file_offset"]):
            handle.seek(r["file_offset"])
            leaves = []
            for _ in range(r["end"] - r["start"]):
                chunk = handle.read(size)
                if len(chunk) != size:
                    raise ValueError("the file is shorter than the proof says")
                leaves.append(hashlib.sha256(chunk).digest())
            root = rebuild_root(leaves, r["start"], r["leaf_count"], r["proof"])
            results.append((r["version"], "0x" + root.hex() == r["root"].lower()))
        handle.seek(0, 2)
        if handle.tell() != proof["file_bytes"]:
            raise ValueError("the file length does not match the proof")
    return results


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    with open(argv[2], encoding="utf-8") as handle:
        proof = json.load(handle)
    ok = True
    for version, matched in verify(argv[1], proof):
        r = next(item for item in proof["ranges"] if item["version"] == version)
        print(f"version {version}: root {r['root']} {'OK' if matched else 'MISMATCH'}")
        print(
            f"  anchored in tx {r['anchor_tx'] or '(not yet)'} — check rootOf({version}) on chain"
        )
        ok = ok and matched
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
