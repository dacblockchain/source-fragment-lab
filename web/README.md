# Source Fragment Lab — browser

Static pages that work with your Source Fragment entirely in the browser. They use no build step and no dependencies, and your file is never uploaded.

## Run locally

Modules must be served over HTTP (not `file://`):

```sh
python3 -m http.server 8000        # from the repo root → http://localhost:8000/web/
# or, from web/                      → http://localhost:8000/
```

The pages use only relative paths, so they also work from GitHub Pages at a sub-path. The demo fragment is copied into `web/demo/` so the site can be published from `web/` alone. It is regenerated with `tools/make_testdata.py`; copy it again after regenerating.

## Pages

| Page | What it does |
|---|---|
| `index.html` — Lab | Load a `.bin` (+ `.proof.json`). Shows bytes used/left, verifies the Merkle proof from your own bytes, compares each root with `rootOf(version)` on DAC mainnet, and shows an entropy inspector (histogram, Shannon entropy, chi-square, monobit). |
| `dice.html` | Dice (d4–d100) and coins. Every roll = HKDF(device randomness ‖ 32 fresh fragment bytes) → rejection sampling. |
| `starmap.html` | Generative star map, **deterministic** from one chunk (raw bytes, expanded with HKDF). New maps consume the chunk, and only used chunks can be re-drawn. Export PNG. |
| `maze.html` | Playable maze carved from mixed entropy. Arrow keys / WASD / swipe / on-screen pad. |
| `draw.html` | The verifiable draw of `docs/draw.md`: check someone's draw (paste or load a transcript), or run your own. Reserving marks the chunk used, and the transcript uses the same keys as `fragmentlab draw run`. |

The cursor of used bytes lives in `localStorage`, keyed by the SHA-256 of the first chunk plus the file size. It is a convenience: clearing site data resets it (see `docs/mixing.md`).

## Library (`lib/`)

`hkdf.js` (HKDF + mix/v1), `rng.js` (randbelow), `proof.js` (streaming proof verification), `chain.js` (read-only JSON-RPC), `pool.js` (never-reused bytes), `draw.js` (draw/v1). Each mirrors its Python counterpart in `python/src/fragmentlab/`.

## Tests

```sh
node --test 'web/tests/*.test.mjs'   # Node 22+, from the repo root
```

The tests check the shared vectors in `testdata/vectors.json`, which the Python implementation generated, and the demo fragment's proof, which Interstellar's own Merkle module built.
