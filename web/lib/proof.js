// Verify a Source Fragment Blob/File against its proof.json, in the browser.
// Mirrors python/src/fragmentlab/proof.py. Streams: each range is read in
// batches of chunks with blob.slice, so a ~4 GB file never sits in memory —
// only the 32-byte leaf hashes of the range do.

import { fromHex, toHex } from './bytes.js'

export const PROOF_FORMAT = 'dac-interstellar/source-fragment/v1'
const BATCH_CHUNKS = 512 // 1 MiB per read at 2,048-byte chunks

export class ProofError extends Error {}

export function parseProof(text) {
  let proof
  try {
    proof = typeof text === 'string' ? JSON.parse(text) : text
  } catch (err) {
    throw new ProofError(`cannot read proof: ${err.message}`)
  }
  if (proof?.format !== PROOF_FORMAT) throw new ProofError(`unsupported proof format ${JSON.stringify(proof?.format)}`)
  if (proof.hash !== 'sha256') throw new ProofError(`unsupported hash ${JSON.stringify(proof.hash)}`)
  return proof
}

export function levelLengths(leafCount) {
  if (!(leafCount > 0)) throw new ProofError('a tree has at least one leaf')
  const out = [leafCount]
  while (out[out.length - 1] > 1) out.push(Math.ceil(out[out.length - 1] / 2))
  return out
}

function node(hex) {
  if (typeof hex !== 'string' || !/^0x[0-9a-fA-F]{64}$/.test(hex)) {
    throw new ProofError(`not a 32-byte hex node: ${JSON.stringify(hex)}`)
  }
  return fromHex(hex)
}

async function hashPair(left, right) {
  const both = new Uint8Array(64)
  both.set(left)
  both.set(right, 32)
  return new Uint8Array(await crypto.subtle.digest('SHA-256', both))
}

async function parents(run) {
  const out = []
  for (let i = 0; i < run.length; i += 2) {
    out.push(i + 1 < run.length ? await hashPair(run[i], run[i + 1]) : run[i])
  }
  return out
}

/** The root implied by `leaves` at [start, start+len) and the proof siblings. */
export async function rebuildRoot(leaves, start, leafCount, steps) {
  if (!leaves.length || start < 0 || start + leaves.length > leafCount) {
    throw new ProofError('the range does not fit inside the tree')
  }
  const lengths = levelLengths(leafCount)
  if (steps.length !== lengths.length - 1) throw new ProofError('proof depth does not match the leaf count')
  let nodes = leaves
  let lo = start
  for (let level = 0; level < steps.length; level++) {
    const step = steps[level]
    const last = lo + nodes.length - 1
    const needLeft = lo % 2 === 1
    const needRight = last % 2 === 0 && last + 1 < lengths[level]
    if ((step.left != null) !== needLeft || (step.right != null) !== needRight) {
      throw new ProofError('proof siblings do not match the range')
    }
    const run = [...(needLeft ? [node(step.left)] : []), ...nodes, ...(needRight ? [node(step.right)] : [])]
    nodes = await parents(run)
    lo = Math.floor((needLeft ? lo - 1 : lo) / 2)
  }
  if (lo !== 0 || nodes.length !== 1) throw new ProofError('the range did not reduce to one root')
  return nodes[0]
}

/**
 * Verify every range. `onProgress(doneBytes, totalBytes)` is called per batch.
 * Returns [{version, root, rebuilt, anchorTx, ok}].
 */
export async function verifyBlob(blob, proof, onProgress = () => {}) {
  const size = proof.chunk_size
  if (blob.size !== proof.file_bytes) {
    throw new ProofError(`the file is ${blob.size} bytes, the proof says ${proof.file_bytes}`)
  }
  const ranges = [...proof.ranges].sort((a, b) => a.file_offset - b.file_offset)
  const results = []
  let expected = 0
  for (const r of ranges) {
    if (r.file_offset !== expected || !(r.start >= 0 && r.start < r.end)) {
      throw new ProofError('the ranges do not tile the file')
    }
    const count = r.end - r.start
    const leaves = []
    for (let done = 0; done < count; done += BATCH_CHUNKS) {
      const n = Math.min(BATCH_CHUNKS, count - done)
      const from = r.file_offset + done * size
      const bytes = new Uint8Array(await blob.slice(from, from + n * size).arrayBuffer())
      if (bytes.length !== n * size) throw new ProofError('the file is shorter than the proof says')
      for (let i = 0; i < n; i++) {
        const digest = await crypto.subtle.digest('SHA-256', bytes.subarray(i * size, (i + 1) * size))
        leaves.push(new Uint8Array(digest))
      }
      onProgress(from + n * size, blob.size)
    }
    const rebuilt = '0x' + toHex(await rebuildRoot(leaves, r.start, r.leaf_count, r.proof))
    results.push({ version: r.version, root: r.root, rebuilt, anchorTx: r.anchor_tx, ok: rebuilt === r.root.toLowerCase() })
    expected += count * size
  }
  if (expected !== proof.file_bytes) throw new ProofError('the ranges do not cover the whole file')
  return results
}
