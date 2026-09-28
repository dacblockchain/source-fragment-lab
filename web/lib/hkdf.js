// HKDF-SHA256 (RFC 5869) via WebCrypto, and the `source-fragment-lab/mix/v1`
// construction (docs/mixing.md). Mirrors python/src/fragmentlab/mix.py.

import { concat, enc } from './bytes.js'

export const HASH_LEN = 32
export const MAX_OUTPUT = 255 * HASH_LEN // 8160 bytes
export const MIX_SALT = enc.encode('source-fragment-lab/mix/v1')
export const LOCAL_BYTES = 32
export const QUANTUM_BYTES = 32

export async function hkdf(ikm, salt, info, length) {
  if (!(length > 0 && length <= MAX_OUTPUT)) {
    throw new Error(`HKDF-SHA256 output must be 1..${MAX_OUTPUT} bytes, not ${length}`)
  }
  const key = await crypto.subtle.importKey('raw', ikm, 'HKDF', false, ['deriveBits'])
  const bits = await crypto.subtle.deriveBits(
    { name: 'HKDF', hash: 'SHA-256', salt, info },
    key,
    length * 8,
  )
  return new Uint8Array(bits)
}

export function localRandom(n = LOCAL_BYTES) {
  return crypto.getRandomValues(new Uint8Array(n))
}

/**
 * HKDF(local ‖ quantum) for one purpose. `local` defaults to fresh OS randomness;
 * passing it explicitly exists for tests only.
 */
export async function mix(quantum, purpose, length, local = undefined) {
  if (quantum.length !== QUANTUM_BYTES) {
    throw new Error(`mix takes exactly ${QUANTUM_BYTES} fragment bytes, not ${quantum.length}`)
  }
  if (!purpose) throw new Error('a purpose label is required, so two uses never share a key')
  const own = local ?? localRandom()
  if (own.length !== LOCAL_BYTES) throw new Error(`local randomness must be ${LOCAL_BYTES} bytes`)
  return hkdf(concat(own, quantum), MIX_SALT, enc.encode(purpose), length)
}
