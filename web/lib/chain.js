// Read-only DAC mainnet calls over JSON-RPC. Mirrors python/src/fragmentlab/chain.py.
// Nothing here signs or sends a transaction.

export const MAINNET_CHAIN_ID = 21892
export const MAINNET_RPC = 'https://rpc.dachain.tech'
export const RESERVOIR_ANCHOR = '0x1C0e62771179357D30782757a1198BDdeE95cE87'
export const ROOT_OF_SELECTOR = '9d7384d9' // keccak256("rootOf(uint64)")[:4]
export const ZERO_ROOT = '0x' + '0'.repeat(64)
const TIMEOUT_MS = 15000
const WORD = /^0x[0-9a-fA-F]{64}$/

export class ChainError extends Error {}

export async function rpc(method, params, url = MAINNET_RPC) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS)
  let reply
  try {
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method, params }),
      signal: controller.signal,
    })
    reply = await res.json()
  } catch (err) {
    throw new ChainError(`${method} on ${url} failed: ${err.message}`)
  } finally {
    clearTimeout(timer)
  }
  if (reply.error) throw new ChainError(`${method} on ${url}: ${JSON.stringify(reply.error)}`)
  return reply.result
}

/** The root anchored for `version`, or ZERO_ROOT when nothing is anchored yet. */
export async function rootOf(version, { url = MAINNET_RPC, anchor = RESERVOIR_ANCHOR } = {}) {
  if (!/^0x[0-9a-fA-F]{40}$/.test(anchor)) throw new Error(`not an address: ${anchor}`)
  const v = BigInt(version)
  if (v < 0n || v >= 1n << 64n) throw new Error(`version must fit in uint64, not ${version}`)
  const data = '0x' + ROOT_OF_SELECTOR + v.toString(16).padStart(64, '0')
  const result = await rpc('eth_call', [{ to: anchor, data }, 'latest'], url)
  if (typeof result !== 'string' || !WORD.test(result)) throw new ChainError(`rootOf(${version}) returned ${result}`)
  return result.toLowerCase()
}

/** Blocks that must follow `height` before its hash is final enough for a draw (docs/draw.md). */
export const DRAW_CONFIRMATIONS = 12

/** The hash of the block at `height`; throws until it has `confirmations` blocks on top. */
export async function blockHash(height, { url = MAINNET_RPC, confirmations = DRAW_CONFIRMATIONS } = {}) {
  const latest = await latestBlock({ url })
  if (latest - height < confirmations) {
    const have = Math.max(0, latest - height)
    throw new ChainError(`block ${height} has ${have} of ${confirmations} confirmations; wait and try again`)
  }
  const block = await rpc('eth_getBlockByNumber', ['0x' + BigInt(height).toString(16), false], url)
  if (!block || !WORD.test(String(block.hash))) throw new ChainError(`block ${height} is not available yet`)
  return block.hash.toLowerCase()
}

export async function latestBlock({ url = MAINNET_RPC } = {}) {
  return Number(BigInt(await rpc('eth_blockNumber', [], url)))
}
