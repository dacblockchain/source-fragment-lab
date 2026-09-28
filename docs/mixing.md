# Mixing: the one rule

> **Never use fragment bytes alone as a secret. We saw them.**
> Mix them with your own randomness: `HKDF(os_random ‖ fragment)`.

Interstellar's operator stored every byte it delivered, so the fragment on its own is not a secret. Your operating system's CSPRNG on its own is a secret, but you have to trust one vendor's implementation. Put the two through HKDF and the output is at least as strong as the **better** of the two:

- if the operator leaks or keeps your bytes, your local randomness still protects the key;
- if your local generator is weak, broken or backdoored, the quantum bytes still protect it.

## The construction (`source-fragment-lab/mix/v1`)

Every example in this repository derives secret material the same way:

```
local    = 32 bytes from the OS CSPRNG      (os.urandom / crypto.getRandomValues)
quantum  = the next 32 UNUSED bytes of the fragment
ikm      = local ‖ quantum
salt     = UTF-8 "source-fragment-lab/mix/v1"
info     = UTF-8 purpose label, e.g. "ed25519", "aes-256-gcm", "bip39"
output   = HKDF-SHA256(ikm, salt, info, L)        L ≤ 8160 bytes
```

The purpose label keeps two uses of the same call from ever producing related keys.

## Never reuse a byte

Each draw consumes its 32 quantum bytes. The examples remember how far into the file they have got:

- **Python**: a sidecar file `<fragment>.cursor` next to the fragment, holding
  `{"format": "source-fragment-lab/cursor/v1", "consumed": <bytes>}`. It is rewritten atomically after every draw, under an exclusive lock on `<fragment>.cursor.lock`, so two commands running at once never get the same bytes.
- **Browser**: `localStorage`, keyed by the SHA-256 of the file's first chunk plus its size. It is a convenience, not a guarantee: clearing site data resets it.

When the fragment runs out, the examples stop. They do not wrap around.

## Uniform numbers without bias

Dice, cards, passwords and draws need an integer in `[0, n)`. Taking `byte % n` is biased whenever `n` does not divide 256. The examples use rejection sampling instead, defined exactly so that Python and JavaScript agree byte for byte:

```
randbelow(n):                       n ≥ 1
    if n == 1: return 0             (reads nothing)
    bits  = bit_length(n - 1)
    size  = ceil(bits / 8)
    loop:
        x = next `size` bytes, read as a big-endian unsigned integer
        x = x AND (2^bits - 1)      (keep the low `bits` bits)
        if x < n: return x
```

Each attempt succeeds with probability above ½, so a draw reads on average fewer than two attempts.

## When mixing is the wrong tool

Mixing is for **secrets**. Some uses need the opposite: a value anyone can recompute, such as a public draw or seed-reproducible art. Those examples use the raw bytes on purpose and say so. [draw.md](draw.md) explains how a public draw stays fair even though you, the fragment holder, can see the bytes.
