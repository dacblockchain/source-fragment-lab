"""Verify a Source Fragment file against its proof.json — standard library only.

Streams the file (a fragment can be ~4 GB): each range's leaves are hashed
chunk by chunk and folded level by level, so memory holds one level of the
range, never the bytes. Tree shape and proof layout: docs/format.md.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

PROOF_FORMAT = "dac-interstellar/source-fragment/v1"


class ProofError(ValueError):
    """The proof is malformed or does not fit the file."""


@dataclass(frozen=True)
class RangeResult:
    version: int
    root: str
    rebuilt: str
    anchor_tx: str | None

    @property
    def ok(self) -> bool:
        return self.rebuilt == self.root.lower()


def load(path: str | Path) -> dict:
    try:
        proof = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProofError(f"cannot read proof {path}: {exc}") from exc
    if proof.get("format") != PROOF_FORMAT:
        raise ProofError(f"unsupported proof format {proof.get('format')!r}")
    if proof.get("hash") != "sha256":
        raise ProofError(f"unsupported hash {proof.get('hash')!r}")
    validate(proof)
    return proof


def _int(value: object, name: str, minimum: int = 0) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ProofError(f"{name} must be an integer >= {minimum}, not {value!r}")
    return value


def validate(proof: object) -> None:
    """Structure and types only; whether the bytes fit is verify_file's job."""
    if not isinstance(proof, dict):
        raise ProofError("a proof is a JSON object")
    _int(proof.get("chunk_size"), "chunk_size", 1)
    _int(proof.get("file_bytes"), "file_bytes", 1)
    ranges = proof.get("ranges")
    if not isinstance(ranges, list) or not ranges:
        raise ProofError("ranges must be a non-empty list")
    for i, r in enumerate(ranges):
        if not isinstance(r, dict):
            raise ProofError(f"ranges[{i}] is not an object")
        for name, minimum in (("version", 0), ("start", 0), ("end", 1), ("leaf_count", 1), ("file_offset", 0)):
            _int(r.get(name), f"ranges[{i}].{name}", minimum)
        _node(r.get("root"))
        if r.get("anchor_tx") is not None and not isinstance(r["anchor_tx"], str):
            raise ProofError(f"ranges[{i}].anchor_tx must be a string or null")
        steps = r.get("proof")
        if not isinstance(steps, list) or not all(isinstance(s, dict) for s in steps):
            raise ProofError(f"ranges[{i}].proof must be a list of objects")
        for s in steps:
            for side in ("left", "right"):
                if s.get(side) is not None:
                    _node(s[side])


def level_lengths(leaf_count: int) -> list[int]:
    if leaf_count <= 0:
        raise ProofError("a tree has at least one leaf")
    out = [leaf_count]
    while out[-1] > 1:
        out.append((out[-1] + 1) // 2)
    return out


def _node(hex_value: str) -> bytes:
    if not (isinstance(hex_value, str) and hex_value.startswith("0x") and len(hex_value) == 66):
        raise ProofError(f"not a 32-byte hex node: {hex_value!r}")
    return bytes.fromhex(hex_value[2:])


def _parents(run: list[bytes]) -> list[bytes]:
    return [
        hashlib.sha256(run[i] + run[i + 1]).digest() if i + 1 < len(run) else run[i]
        for i in range(0, len(run), 2)
    ]


def rebuild_root(leaves: list[bytes], start: int, leaf_count: int, steps: list[dict]) -> bytes:
    """The root implied by `leaves` at [start, start+len) and the proof siblings."""
    if not leaves or start < 0 or start + len(leaves) > leaf_count:
        raise ProofError("the range does not fit inside the tree")
    lengths = level_lengths(leaf_count)
    if len(steps) != len(lengths) - 1:
        raise ProofError("proof depth does not match the leaf count")
    nodes, lo = leaves, start
    for step, length in zip(steps, lengths):
        last = lo + len(nodes) - 1
        need_left = lo % 2 == 1
        need_right = last % 2 == 0 and last + 1 < length
        if (step.get("left") is not None) != need_left or (step.get("right") is not None) != need_right:
            raise ProofError("proof siblings do not match the range")
        run = ([_node(step["left"])] if need_left else []) + nodes
        run += [_node(step["right"])] if need_right else []
        nodes = _parents(run)
        lo = (lo - 1 if need_left else lo) // 2
    if lo != 0 or len(nodes) != 1:
        raise ProofError("the range did not reduce to one root")
    return nodes[0]


def verify_file(path: str | Path, proof: dict) -> list[RangeResult]:
    size = proof["chunk_size"]
    results = []
    with Path(path).open("rb") as handle:
        handle.seek(0, 2)
        if handle.tell() != proof["file_bytes"]:
            raise ProofError(
                f"the file is {handle.tell()} bytes, the proof says {proof['file_bytes']}"
            )
        expected_offset = 0
        for r in sorted(proof["ranges"], key=lambda item: item["file_offset"]):
            if r["file_offset"] != expected_offset or not 0 <= r["start"] < r["end"]:
                raise ProofError("the ranges do not tile the file")
            handle.seek(r["file_offset"])
            leaves = []
            for _ in range(r["end"] - r["start"]):
                chunk = handle.read(size)
                if len(chunk) != size:
                    raise ProofError("the file is shorter than the proof says")
                leaves.append(hashlib.sha256(chunk).digest())
            rebuilt = rebuild_root(leaves, r["start"], r["leaf_count"], r["proof"])
            results.append(RangeResult(r["version"], r["root"], "0x" + rebuilt.hex(), r["anchor_tx"]))
            expected_offset += (r["end"] - r["start"]) * size
    if expected_offset != proof["file_bytes"]:
        raise ProofError("the ranges do not cover the whole file")
    return results
