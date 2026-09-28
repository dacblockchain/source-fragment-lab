"""`fragmentlab` — one command per example. Run `fragmentlab <command> -h` for details."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from fragmentlab import chain, draw, filecrypt, keys, proof, secrets_gen
from fragmentlab.pool import FragmentExhausted, FragmentPool

ZERO_ROOT = "0x" + "00" * 32


def _write_private(path: Path, data: bytes) -> None:
    """Create the file readable by its owner only, refusing to overwrite."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def cmd_verify(args) -> int:
    doc = proof.load(args.proof)
    results = proof.verify_file(args.fragment, doc)
    ok = True
    for r in results:
        line = f"version {r.version}: rebuilt {r.rebuilt} "
        line += "matches the proof" if r.ok else f"DOES NOT match the proof ({r.root})"
        print(line)
        ok = ok and r.ok
        if args.offline or not r.ok:
            continue
        anchored = chain.root_of(r.version, url=args.rpc, anchor=args.anchor)
        if anchored == ZERO_ROOT:
            print(f"  on-chain: nothing anchored for version {r.version} yet")
            ok = False
        elif anchored == r.rebuilt:
            print(f"  on-chain: rootOf({r.version}) = {anchored}  OK")
        else:
            print(f"  on-chain: rootOf({r.version}) = {anchored}  MISMATCH")
            ok = False
    print("AUTHENTIC" if ok else "NOT VERIFIED")
    return 0 if ok else 1


def cmd_status(args) -> int:
    pool = FragmentPool(args.fragment)
    print(f"{pool.path.name}: {pool.size:,} bytes, {pool.consumed:,} used, {pool.remaining:,} left")
    return 0


def cmd_keys(args) -> int:
    pool = FragmentPool(args.fragment)
    if args.kind == "age":
        secret, public = keys.age_identity(pool)
        _write_private(args.out, f"# public key: {public}\n{secret}\n".encode())
        print(public)
        return 0
    private, public = (keys.ed25519_pem if args.kind == "ed25519" else keys.x25519_pem)(pool)
    _write_private(args.out, private)
    Path(str(args.out) + ".pub").write_bytes(public)
    print(public.decode(), end="")
    return 0


def cmd_secret_key(args) -> int:
    _write_private(args.out, FragmentPool(args.fragment).mixed("aes-256-gcm", 32).hex().encode())
    print(f"wrote a 256-bit key to {args.out} (mode 600)")
    return 0


def _read_key(path: Path) -> bytes:
    key = bytes.fromhex(path.read_text().strip())
    if len(key) != filecrypt.KEY_BYTES:
        raise ValueError(f"{path} does not hold a 32-byte hex key")
    return key


def cmd_encrypt(args) -> int:
    filecrypt.encrypt_file(_read_key(args.key), args.input, args.output)
    return 0


def cmd_decrypt(args) -> int:
    filecrypt.decrypt_file(_read_key(args.key), args.input, args.output)
    return 0


def cmd_seed(args) -> int:
    print(secrets_gen.mnemonic(FragmentPool(args.fragment), args.words))
    return 0


def cmd_password(args) -> int:
    pool = FragmentPool(args.fragment)
    if args.words:
        print(secrets_gen.passphrase(pool, args.words))
    else:
        print(secrets_gen.password(pool, args.length))
    return 0


def cmd_draw_commit(args) -> int:
    index, data = FragmentPool(args.fragment).take_chunk(draw.CHUNK_SIZE)
    print(json.dumps({"chunk": index, "commitment": draw.chunk_commitment(data)}, indent=2))
    return 0


def cmd_draw_run(args) -> int:
    entries = draw.normalise_entries(Path(args.entries).read_text(encoding="utf-8"))
    if args.chunk_hex:
        chunk = bytes.fromhex(Path(args.chunk_hex).read_text().strip().removeprefix("0x"))
    else:
        chunk = draw.read_chunk(args.fragment, args.chunk)
    block = args.block_hash or chain.block_hash(
        args.block, url=args.rpc, confirmations=args.confirmations
    )
    result = draw.run(chunk, block, entries, args.winners)
    if args.commitment.lower() != result.chunk_commitment:
        print(f"the chunk does NOT match the commitment {args.commitment}", file=sys.stderr)
        return 1
    transcript = {
        "format": "source-fragment-lab/draw/v1",
        "block": args.block,
        "block_hash": result.block_hash,
        "chunk_commitment": result.chunk_commitment,
        "chunk_hex": chunk.hex(),
        "entries_hash": result.entries_hash,
        "entries": len(entries),
        "winners": result.winners,
    }
    print(json.dumps(transcript, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fragmentlab", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    v = sub.add_parser("verify", help="check a fragment against its proof and DAC mainnet")
    v.add_argument("fragment", type=Path)
    v.add_argument("proof", type=Path)
    v.add_argument("--offline", action="store_true", help="skip the on-chain rootOf check")
    v.add_argument("--rpc", default=chain.MAINNET_RPC)
    v.add_argument("--anchor", default=chain.RESERVOIR_ANCHOR)
    v.set_defaults(func=cmd_verify)

    s = sub.add_parser("status", help="bytes used and left in a fragment")
    s.add_argument("fragment", type=Path)
    s.set_defaults(func=cmd_status)

    k = sub.add_parser("keys", help="generate an Ed25519, X25519 or age key pair")
    k.add_argument("kind", choices=["ed25519", "x25519", "age"])
    k.add_argument("--fragment", type=Path, required=True)
    k.add_argument("--out", type=Path, required=True)
    k.set_defaults(func=cmd_keys)

    sk = sub.add_parser("secret-key", help="a 256-bit symmetric key for encrypt/decrypt")
    sk.add_argument("--fragment", type=Path, required=True)
    sk.add_argument("--out", type=Path, required=True)
    sk.set_defaults(func=cmd_secret_key)

    for name, func in (("encrypt", cmd_encrypt), ("decrypt", cmd_decrypt)):
        c = sub.add_parser(name, help=f"{name} a file with AES-256-GCM (STREAM)")
        c.add_argument("input", type=Path)
        c.add_argument("output", type=Path)
        c.add_argument("--key", type=Path, required=True)
        c.set_defaults(func=func)

    sd = sub.add_parser("seed", help="a BIP-39 mnemonic")
    sd.add_argument("--fragment", type=Path, required=True)
    sd.add_argument("--words", type=int, default=24, choices=sorted(secrets_gen.MNEMONIC_WORDS))
    sd.set_defaults(func=cmd_seed)

    pw = sub.add_parser("password", help="a random password, or a passphrase with --words")
    pw.add_argument("--fragment", type=Path, required=True)
    pw.add_argument("--length", type=int, default=24)
    pw.add_argument("--words", type=int)
    pw.set_defaults(func=cmd_password)

    dc = sub.add_parser(
        "draw-commit", help="reserve the next unused chunk and print the commitment to announce"
    )
    dc.add_argument("--fragment", type=Path, required=True)
    dc.set_defaults(func=cmd_draw_commit)

    dr = sub.add_parser("draw", help="run or re-check a verifiable draw")
    src = dr.add_mutually_exclusive_group(required=True)
    src.add_argument("--fragment", type=Path)
    src.add_argument("--chunk-hex", type=Path, help="a file holding the revealed chunk in hex")
    dr.add_argument("--chunk", type=int, default=0)
    dr.add_argument("--entries", type=Path, required=True)
    dr.add_argument("--winners", type=int, required=True)
    blk = dr.add_mutually_exclusive_group(required=True)
    blk.add_argument("--block", type=int, help="block height; its hash is fetched from --rpc")
    blk.add_argument("--block-hash")
    dr.add_argument(
        "--commitment",
        required=True,
        help="the SHA-256 announced before entries closed; without it a draw proves nothing",
    )
    dr.add_argument("--confirmations", type=int, default=chain.DRAW_CONFIRMATIONS)
    dr.add_argument("--rpc", default=chain.MAINNET_RPC)
    dr.set_defaults(func=cmd_draw_run)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (
        ValueError,
        OSError,
        FragmentExhausted,
        chain.ChainError,
        filecrypt.DecryptionError,
    ) as exc:
        print(f"fragmentlab {args.command}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
