"""Read-only DAC mainnet calls over JSON-RPC — standard library only.

Two reads are all the examples need: `rootOf(version)` on the reservoir anchor,
and a block hash for the verifiable draw. Nothing here signs or sends a
transaction.
"""

from __future__ import annotations

import json
import re
import urllib.request

MAINNET_CHAIN_ID = 21892
MAINNET_RPC = "https://rpc.dachain.tech"
RESERVOIR_ANCHOR = "0x1C0e62771179357D30782757a1198BDdeE95cE87"
ROOT_OF_SELECTOR = "9d7384d9"  # keccak256("rootOf(uint64)")[:4]
TIMEOUT_SECONDS = 15
# Blocks that must follow a draw's block before its hash is used: a hash that a
# reorg can still replace is a hash somebody could grind (docs/draw.md).
DRAW_CONFIRMATIONS = 12
_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_WORD = re.compile(r"^0x[0-9a-fA-F]{64}$")


class ChainError(RuntimeError):
    """The RPC endpoint failed or answered something unexpected."""


def rpc(url: str, method: str, params: list) -> object:
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    request = urllib.request.Request(url, body, {"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            reply = json.load(response)
    except (OSError, json.JSONDecodeError) as exc:
        raise ChainError(f"{method} on {url} failed: {exc}") from exc
    if "error" in reply:
        raise ChainError(f"{method} on {url}: {reply['error']}")
    return reply.get("result")


def chain_id(url: str = MAINNET_RPC) -> int:
    return int(str(rpc(url, "eth_chainId", [])), 16)


def root_of(version: int, *, url: str = MAINNET_RPC, anchor: str = RESERVOIR_ANCHOR) -> str:
    """The root anchored for `version`, or 0x00…00 when nothing is anchored yet."""
    if not _ADDRESS.match(anchor):
        raise ValueError(f"not an address: {anchor!r}")
    if not 0 <= version < 2**64:
        raise ValueError(f"version must fit in uint64, not {version}")
    data = "0x" + ROOT_OF_SELECTOR + version.to_bytes(32, "big").hex()
    result = rpc(url, "eth_call", [{"to": anchor, "data": data}, "latest"])
    if not isinstance(result, str) or not _WORD.match(result):
        raise ChainError(f"rootOf({version}) returned {result!r}")
    return result.lower()


def latest_block(url: str = MAINNET_RPC) -> int:
    return int(str(rpc(url, "eth_blockNumber", [])), 16)


def block_hash(height: int, *, url: str = MAINNET_RPC, confirmations: int = DRAW_CONFIRMATIONS) -> str:
    """The hash of the block at `height`; raises until it has `confirmations` blocks on top."""
    latest = latest_block(url)
    if latest - height < confirmations:
        have = max(0, latest - height)
        raise ChainError(f"block {height} has {have} of {confirmations} confirmations; wait and retry")
    block = rpc(url, "eth_getBlockByNumber", [hex(height), False])
    if not isinstance(block, dict) or not _WORD.match(str(block.get("hash"))):
        raise ChainError(f"block {height} is not available yet")
    return block["hash"].lower()
