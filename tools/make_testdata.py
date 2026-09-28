#!/usr/bin/env python3
"""Regenerate testdata/ from Interstellar's own Merkle module.

    python3 tools/make_testdata.py /path/to/dac-interstellar

The vectors are built by the REFERENCE implementation (the module that seals
the real reservoir versions), not by this repository's code, so the tests here
prove that the lab's verifiers agree with what Interstellar actually ships.

The bytes are PRNG output, NOT quantum entropy: they exist so anyone can try
the examples without having won a Source Fragment.
"""

from __future__ import annotations

import importlib.util
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "testdata"
PROOF_FORMAT = "dac-interstellar/source-fragment/v1"
SEED = 21892  # DAC mainnet chain id: fixed so the vectors are reproducible

# Two demo reservoir versions with odd leaf counts (exercises the promoted node)
# and a fragment that spills from the tail of v1 into the head of v2, exactly as
# a real assignment does when a version runs out.
VERSIONS = {1: 37, 2: 21}
RANGES = [(1, 30, 37), (2, 0, 5)]


def load_reference(interstellar: Path):
    path = interstellar / "backend" / "apps" / "crate" / "fragment_merkle.py"
    spec = importlib.util.spec_from_file_location("fragment_merkle", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hex0x(node: bytes | None) -> str | None:
    return None if node is None else "0x" + node.hex()


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    fm = load_reference(Path(argv[1]))
    rng = random.Random(SEED)
    size = fm.CHUNK_SIZE

    versions = {}
    for number, count in VERSIONS.items():
        chunks = [rng.randbytes(size) for _ in range(count)]
        levels = fm.build_levels([fm.leaf_hash(c) for c in chunks])
        versions[number] = (chunks, levels)

    body, ranges, file_offset = b"", [], 0
    for number, start, end in RANGES:
        chunks, levels = versions[number]
        steps = fm.range_proof(fm.level_reader(levels), len(chunks), start, end)
        assert fm.verify_range(
            fm.root_of(levels), len(chunks), start, [fm.leaf_hash(c) for c in chunks[start:end]], steps
        )
        ranges.append(
            {
                "version": number,
                "source": "demo-prng",
                "root": hex0x(fm.root_of(levels)),
                "leaf_count": len(chunks),
                "anchor_tx": None,
                "start": start,
                "end": end,
                "file_offset": file_offset,
                "proof": [{"left": hex0x(s["left"]), "right": hex0x(s["right"])} for s in steps],
            }
        )
        body += b"".join(chunks[start:end])
        file_offset += (end - start) * size

    proof = {
        "format": PROOF_FORMAT,
        "hash": "sha256",
        "chunk_size": size,
        "award_bytes": len(body) - 1000,  # awards are decimal bytes, delivery rounds up to chunks
        "file_bytes": len(body),
        "assignment": {"sequence": 0, "leaf": None},
        "ranges": ranges,
    }
    OUT.mkdir(exist_ok=True)
    (OUT / "demo-fragment.bin").write_bytes(body)
    (OUT / "demo-fragment.proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(f"wrote {len(body)} bytes and a proof over {len(ranges)} ranges to {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
