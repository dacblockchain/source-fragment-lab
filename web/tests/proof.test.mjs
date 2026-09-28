// The browser proof verifier against the demo fragment built by Interstellar's
// own Merkle module (tools/make_testdata.py). Run: node --test web/tests/

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

import { ProofError, parseProof, verifyBlob } from '../lib/proof.js'

const root = new URL('../../testdata/', import.meta.url)
const bytes = new Uint8Array(readFileSync(new URL('demo-fragment.bin', root)))
const proofText = readFileSync(new URL('demo-fragment.proof.json', root), 'utf8')

test('the demo fragment verifies against both ranges', async () => {
  const proof = parseProof(proofText)
  const seen = []
  const results = await verifyBlob(new Blob([bytes]), proof, (done, total) => seen.push([done, total]))
  assert.deepEqual(results.map((r) => [r.version, r.ok]), [[1, true], [2, true]])
  assert.equal(seen.at(-1)[0], bytes.length)
})

test('one flipped byte breaks exactly the range it sits in', async () => {
  const tampered = bytes.slice()
  tampered[2048 * 8 + 5] ^= 0x01 // chunk 8 of the file = version 2's second chunk
  const results = await verifyBlob(new Blob([tampered]), parseProof(proofText))
  assert.deepEqual(results.map((r) => [r.version, r.ok]), [[1, true], [2, false]])
})

test('a truncated file is refused', async () => {
  await assert.rejects(verifyBlob(new Blob([bytes.subarray(0, bytes.length - 1)]), parseProof(proofText)), ProofError)
})

test('a tampered sibling is refused or fails', async () => {
  const proof = parseProof(proofText)
  const step = proof.ranges[0].proof.find((s) => s.left || s.right)
  const key = step.left ? 'left' : 'right'
  step[key] = '0x' + (step[key][2] === '0' ? '1' : '0') + step[key].slice(3)
  const results = await verifyBlob(new Blob([bytes]), proof)
  assert.equal(results[0].ok, false)
})

test('an unknown proof format is refused', () => {
  assert.throws(() => parseProof(JSON.stringify({ format: 'other', hash: 'sha256' })), ProofError)
})
