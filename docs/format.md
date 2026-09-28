# The Source Fragment format

A Source Fragment prize is delivered as two files:

| File | What it is |
|---|---|
| `source-fragment-<n>.bin` | The raw bytes: whole 2,048-byte chunks cut from Interstellar's quantum reservoir |
| `source-fragment-<n>.proof.json` | Where those chunks came from, and the Merkle proof tying them to a root anchored on DAC mainnet |

The `.bin` file is deleted from Interstellar's storage 7 days after the first download link is issued. The proof stays in your account forever.

## `proof.json` (format `dac-interstellar/source-fragment/v1`)

```json
{
  "format": "dac-interstellar/source-fragment/v1",
  "hash": "sha256",
  "chunk_size": 2048,
  "award_bytes": 23576,
  "file_bytes": 24576,
  "assignment": { "sequence": 7, "leaf": "0x…" },
  "ranges": [
    {
      "version": 1,
      "source": "…",
      "root": "0x…",
      "leaf_count": 4194304,
      "anchor_tx": "0x…",
      "start": 30,
      "end": 37,
      "file_offset": 0,
      "proof": [ { "left": "0x…", "right": null }, … ]
    }
  ]
}
```

- `award_bytes` is the prize as declared, in decimal bytes (1 MB = 1,000,000 B). Delivery rounds it **up** to whole chunks, so `file_bytes >= award_bytes`.
- Each entry in `ranges` is a contiguous run of chunks `[start, end)` from reservoir `version`. The run sits at `file_offset` in the `.bin` file. A fragment spans two versions when the first one ran out.
- `root` is the value anchored on-chain for that version, read back with `rootOf(version)`. `leaf_count` is the version's size in chunks. It shapes the tree walk, and the anchor stores it too, but `rootOf` does not return it. It needs no separate check: a wrong `leaf_count` cannot rebuild the anchored root without breaking SHA-256. `anchor_tx` is the anchoring transaction, or `null` while the anchor is still pending.

## The Merkle tree

- leaf = `SHA-256(chunk)`
- node = `SHA-256(left ‖ right)`
- an odd last node is **promoted** unchanged to the next level (it is never paired with itself)

A range proof carries one step per level below the root. A step holds at most one `left` and one `right` sibling: the hashes the verifier cannot compute from its own bytes. `left` is present when the run's first index at that level is odd. `right` is present when the run's last index is even and is not the last node of the level. The proof therefore stays logarithmic in size, whatever the prize size.

## Checking it against the chain

Each reservoir version's root is anchored on DAC mainnet (chain id `21892`) in an `AdmissionAnchor` contract:

| | |
|---|---|
| Reservoir anchor | `0x1C0e62771179357D30782757a1198BDdeE95cE87` |
| Assignment-window anchor | `0xfAAC2434a79C0DC26D85064644278523D47505f8` |
| Read call | `rootOf(uint64 version) → bytes32` (selector `0x9d7384d9`) |
| Public RPC | `https://rpc.dachain.tech` |

A fragment is authentic when:

1. every range's root, rebuilt from **your own bytes** and the proof siblings, equals the proof's `root`, and
2. `rootOf(version)` on the reservoir anchor returns that same root.

Trust nothing else, including this repository: the check is short enough to read in full (`python/src/fragmentlab/proof.py`, `web/lib/proof.js`).

## What the proof does not tell you

The proof shows that the bytes are the ones Interstellar sealed and anchored **before** it assigned them to you. It does **not** show that nobody else has seen them. The operator stored them, so treat them as public-to-the-operator. See [mixing.md](mixing.md) for how to use them safely anyway.
