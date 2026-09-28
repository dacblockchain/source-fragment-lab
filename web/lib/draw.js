// The verifiable draw, `source-fragment-lab/draw/v1` (docs/draw.md).
// Mirrors python/src/fragmentlab/draw.py. Deliberately NOT mixed with local
// randomness: anyone must be able to recompute it.

import { concat, enc, fromHex, sha256, toHex } from './bytes.js'
import { MAX_OUTPUT, hkdf } from './hkdf.js'
import { randbelow } from './rng.js'

export const DRAW_DOMAIN = enc.encode('source-fragment-lab/draw/v1')
export const CHUNK_SIZE = 2048

/** One entry per line, trimmed, empty lines dropped, order kept; duplicates refused. */
export function normaliseEntries(text) {
  const entries = text.split(/\r\n|\r|\n/).map((l) => l.trim()).filter(Boolean)
  const seen = new Set()
  for (const e of entries) {
    if (seen.has(e)) throw new Error(`duplicate entry ${JSON.stringify(e)}: make every line unique first`)
    seen.add(e)
  }
  return entries
}

export async function entriesHash(entries) {
  return sha256(enc.encode(entries.join('\n')))
}

export async function chunkCommitment(chunk) {
  return '0x' + toHex(await sha256(chunk))
}

function seedStream(chunk, salt, info) {
  let buffer = new Uint8Array(0)
  let block = 0
  return async (n) => {
    while (buffer.length < n) {
      const counter = new Uint8Array(4)
      new DataView(counter.buffer).setUint32(0, block)
      buffer = concat(buffer, await hkdf(chunk, salt, concat(info, counter), MAX_OUTPUT))
      block += 1
    }
    const out = buffer.slice(0, n)
    buffer = buffer.slice(n)
    return out
  }
}

export async function runDraw(chunk, blockHashHex, entries, winners) {
  if (chunk.length !== CHUNK_SIZE) {
    throw new Error(`a draw uses one whole ${CHUNK_SIZE}-byte chunk, not ${chunk.length} bytes`)
  }
  const salt = fromHex(blockHashHex)
  if (salt.length !== 32) throw new Error('the block hash must be 32 bytes')
  if (new Set(entries).size !== entries.length) throw new Error('entries must be unique')
  if (!(Number.isInteger(winners) && winners >= 1 && winners <= entries.length)) {
    throw new Error(`winners must be 1..${entries.length}, not ${winners}`)
  }
  const digest = await entriesHash(entries)
  const read = seedStream(chunk, salt, concat(DRAW_DOMAIN, digest))
  const pool = [...entries]
  const picked = []
  for (let step = 0; step < winners; step++) {
    const j = pool.length - 1 - step
    const r = await randbelow(j + 1, read)
    ;[pool[j], pool[r]] = [pool[r], pool[j]]
    picked.push(pool[j])
  }
  return {
    winners: picked,
    entriesHash: '0x' + toHex(digest),
    chunkCommitment: await chunkCommitment(chunk),
    blockHash: '0x' + toHex(salt),
  }
}
