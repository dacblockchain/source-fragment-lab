# Source Fragment Lab

Examples and games for the **Source Fragment**: real quantum entropy that you can win in a crate on [DAC Interstellar](https://interstellar.dachain.io) and download to your own machine.

A Source Fragment is a file of raw bytes from a quantum random number generator, cut from a reservoir whose Merkle root is anchored on DAC mainnet **before** any byte is assigned to anyone. This repository shows what you can do with those bytes, and how to do it safely.

> ### The one rule
> **Never use these bytes alone as a key — we saw them.**
> Mix them with your own randomness: `HKDF(os_random ‖ fragment)`.
>
> Every example here does this for you. [Why, and how →](docs/mixing.md)

## What's inside

| | What | Where |
|---|---|---|
| **Verify** | Check that your file is exactly the bytes anchored on-chain | `fragmentlab verify` · [web lab](web/index.html) |
| **Keys** | Ed25519, X25519 and [age](https://age-encryption.org) key pairs | `fragmentlab keys` |
| **Encrypt** | Encrypt a file of any size (AES-256-GCM, STREAM) | `fragmentlab encrypt` / `decrypt` |
| **Wallet seed** | A BIP-39 mnemonic (12–24 words) | `fragmentlab seed` |
| **Passwords** | Passwords and passphrases, without modulo bias | `fragmentlab password` |
| **Fair draw** | A giveaway anyone can re-check: a committed chunk plus a future block hash | `fragmentlab draw` · [web](web/draw.html) · [spec](docs/draw.md) |
| **Games** | Quantum dice, a generative star map, a maze | [web/](web/README.md) |

The browser pages run entirely on your machine. Your fragment is read with the File API and **never uploaded anywhere**. The only network call is the optional read of the anchored root from the public DAC RPC.

## Quick start

No prize yet? `testdata/demo-fragment.bin` is a small **PRNG** file in the real format. It is not quantum, and it is not anchored on-chain, so use `--offline` when you verify it.

### Python (3.10+)

```bash
cd python
uv sync                       # or: pip install -e .
F=../testdata/demo-fragment.bin

uv run fragmentlab verify $F ../testdata/demo-fragment.proof.json --offline
uv run fragmentlab keys age --fragment $F --out my.agekey     # prints the age1… recipient
uv run fragmentlab seed --fragment $F --words 24
uv run fragmentlab password --fragment $F --words 7
uv run fragmentlab status $F                                  # bytes used / left
```

With a real prize, drop `--offline`: the verifier then also calls `rootOf(version)` on the reservoir anchor on DAC mainnet and compares the result.

```text
version 1: rebuilt 0x5223…526c matches the proof
  on-chain: rootOf(1) = 0x5223…526c  OK
AUTHENTIC
```

### Browser

```bash
python3 -m http.server 8000     # from the repository root
# open http://localhost:8000/web/
```

## How the examples use your bytes

- **Secrets** (keys, seeds, passwords, encryption keys) take the next 32 **unused** bytes of the fragment and put them through HKDF together with 32 bytes from your OS. The fragment's `.cursor` sidecar file records how far you have got, so no byte is ever used twice. [docs/mixing.md](docs/mixing.md)
- **Public values** (a fair draw, seed-reproducible art) use raw bytes on purpose, because anyone must be able to recompute them. A chunk that will be revealed is reserved through the same cursor, so it can never also end up in a secret. [docs/draw.md](docs/draw.md)

## Verifying a fragment yourself

The format, the tree shape and the on-chain anchor are documented in [docs/format.md](docs/format.md). The checks are short on purpose: read `python/src/fragmentlab/proof.py` or `web/lib/proof.js` rather than trusting this README.

| | |
|---|---|
| Chain | DAC mainnet, chain id `21892`, RPC `https://rpc.dachain.tech` |
| Reservoir anchor | `0x1C0e62771179357D30782757a1198BDdeE95cE87` · `rootOf(uint64)` |

## Repository layout

```
docs/       format, mixing and draw specifications
python/     the fragmentlab package and CLI (tests in python/tests)
web/        browser lab and games, plain ES modules, no build step (tests in web/tests)
testdata/   the demo fragment and the vectors both implementations must match
tools/      regenerate testdata/ from Interstellar's reference Merkle code
```

## Development

```bash
cd python && uv run pytest --cov=fragmentlab     # Python
node --test 'web/tests/*.test.mjs'                # JavaScript (Node 22+)
```

`testdata/vectors.json` holds fixed inputs with their expected outputs for mixing, rejection sampling and the draw. Both suites check them, so the two implementations cannot drift apart silently.

## Security

These are examples, written to be read. See [SECURITY.md](SECURITY.md) for the threat model and how to report a problem.

## License

[MIT](LICENSE)
