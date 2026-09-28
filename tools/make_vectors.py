#!/usr/bin/env python3
"""Write testdata/vectors.json: fixed inputs → expected outputs of mix, randbelow and draw.

    cd python && uv run python ../tools/make_vectors.py

Both the Python and the JavaScript test suites check these, so the two
implementations cannot drift apart without a test failing.
"""

import json
from pathlib import Path

from fragmentlab import draw
from fragmentlab.mix import ByteStream, mix, randbelow

ROOT = Path(__file__).resolve().parent.parent
fragment = (ROOT / "testdata" / "demo-fragment.bin").read_bytes()

local = bytes(range(32))
quantum = fragment[:32]
mix_vector = {
    "local": local.hex(),
    "quantum": quantum.hex(),
    "purpose": "ed25519",
    "length": 64,
    "output": mix(quantum, "ed25519", 64, local=local).hex(),
}

stream_bytes = fragment[32:32 + 256]
read = ByteStream(stream_bytes)
bounds = [1, 2, 6, 7, 20, 52, 256, 257, 1000, 65537]
randbelow_vector = {
    "stream": stream_bytes.hex(),
    "bounds": bounds,
    "outputs": [randbelow(n, read) for n in bounds],
}

chunk = fragment[2048 * 3:2048 * 4]
entries = [f"participant-{i:03d}" for i in range(1, 101)]
block = "0x7cc1a0052e40866f8c4b2c6326081f6d4f08d22dcd0a0d96994fff58378f5e6a"
result = draw.run(chunk, block, entries, 5)
draw_vector = {
    "chunk_index": 3,
    "chunk_commitment": result.chunk_commitment,
    "block_hash": block,
    "entries": entries,
    "winners": 5,
    "entries_hash": result.entries_hash,
    "picked": result.winners,
}

out = {"mix": mix_vector, "randbelow": randbelow_vector, "draw": draw_vector}
(ROOT / "testdata" / "vectors.json").write_text(json.dumps(out, indent=2) + "\n")
print(json.dumps({"picked": result.winners, "randbelow": randbelow_vector["outputs"]}))
