// Cross-language vectors: the JS must reproduce testdata/vectors.json, which the
// Python implementation generated. Run: node --test web/tests/

import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'

import { fromHex, toHex } from '../lib/bytes.js'
import { runDraw, normaliseEntries } from '../lib/draw.js'
import { hkdf, mix } from '../lib/hkdf.js'
import { ByteStream, randbelow } from '../lib/rng.js'

const root = new URL('../../testdata/', import.meta.url)
const vectors = JSON.parse(readFileSync(new URL('vectors.json', root), 'utf8'))
const fragment = new Uint8Array(readFileSync(new URL('demo-fragment.bin', root)))

test('HKDF-SHA256 matches RFC 5869 test case 1', async () => {
  const ikm = fromHex('0b'.repeat(22))
  const salt = fromHex('000102030405060708090a0b0c')
  const info = fromHex('f0f1f2f3f4f5f6f7f8f9')
  const okm = await hkdf(ikm, salt, info, 42)
  assert.equal(
    toHex(okm),
    '3cb25f25faacd57a90434f64d0362f2a2d2d0a90cf1a5a4c5db02d56ecc4c5bf34007208d5b887185865',
  )
})

test('mix/v1 reproduces the Python vector', async () => {
  const v = vectors.mix
  const out = await mix(fromHex(v.quantum), v.purpose, v.length, fromHex(v.local))
  assert.equal(toHex(out), v.output)
})

test('mix refuses the wrong number of fragment bytes and an empty purpose', async () => {
  await assert.rejects(mix(new Uint8Array(31), 'x', 32))
  await assert.rejects(mix(new Uint8Array(32), '', 32))
})

test('mix without an explicit local value is fresh every call', async () => {
  const q = new Uint8Array(32)
  assert.notEqual(toHex(await mix(q, 'x', 32)), toHex(await mix(q, 'x', 32)))
})

test('randbelow reproduces the Python vector', async () => {
  const v = vectors.randbelow
  const stream = new ByteStream(fromHex(v.stream))
  const outputs = []
  for (const n of v.bounds) outputs.push(await randbelow(n, (k) => stream.read(k)))
  assert.deepEqual(outputs, v.outputs)
})

test('randbelow(1) reads nothing and n < 1 is refused', async () => {
  const stream = new ByteStream(new Uint8Array(0))
  assert.equal(await randbelow(1, (k) => stream.read(k)), 0)
  await assert.rejects(randbelow(0, (k) => stream.read(k)))
})

test('draw/v1 reproduces the Python vector', async () => {
  const v = vectors.draw
  const chunk = fragment.subarray(2048 * v.chunk_index, 2048 * (v.chunk_index + 1))
  const result = await runDraw(chunk, v.block_hash, v.entries, v.winners)
  assert.equal(result.chunkCommitment, v.chunk_commitment)
  assert.equal(result.entriesHash, v.entries_hash)
  assert.deepEqual(result.winners, v.picked)
})

test('draw refuses duplicates, bad k and a partial chunk', async () => {
  assert.throws(() => normaliseEntries('a\nb\n a \n'))
  assert.deepEqual(normaliseEntries(' a \n\n b\r\n'), ['a', 'b'])
  const chunk = fragment.subarray(0, 2048)
  const hash = vectors.draw.block_hash
  await assert.rejects(runDraw(chunk, hash, ['a', 'b'], 3))
  await assert.rejects(runDraw(chunk, hash, ['a', 'b'], 0))
  await assert.rejects(runDraw(chunk.subarray(1), hash, ['a', 'b'], 1))
})
