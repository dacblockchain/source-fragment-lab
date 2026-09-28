// A fragment File/Blob as a pool of never-reused bytes (docs/mixing.md).
// The cursor lives in localStorage keyed by SHA-256(first chunk) + size. It is a
// convenience, not a guarantee: clearing site data resets it, and a private
// window may not keep it at all — so every access is wrapped in try/catch and
// the pool still works (in memory) without it.

import { sha256, toHex } from './bytes.js'
import { QUANTUM_BYTES, mix } from './hkdf.js'

const CURSOR_PREFIX = 'source-fragment-lab/cursor/v1:'
const CHUNK_SIZE = 2048

export class FragmentExhausted extends Error {}

export class FragmentPool {
  static async open(blob, name = 'fragment') {
    const head = new Uint8Array(await blob.slice(0, CHUNK_SIZE).arrayBuffer())
    const id = toHex(await sha256(head)) + ':' + blob.size
    return new FragmentPool(blob, name, CURSOR_PREFIX + id)
  }

  constructor(blob, name, key) {
    this.blob = blob
    this.name = name
    this.key = key
    this.size = blob.size
    this.memory = this.#load()
    this.listeners = new Set()
  }

  #load() {
    try {
      const n = Number(localStorage.getItem(this.key) ?? 0)
      return Number.isInteger(n) && n >= 0 && n <= this.size ? n : 0
    } catch {
      return 0
    }
  }

  get consumed() {
    // Take the furthest of memory and storage: another tab may have used bytes too.
    const stored = this.#load()
    return Math.max(stored, this.memory)
  }

  get remaining() {
    return this.size - this.consumed
  }

  onChange(fn) {
    this.listeners.add(fn)
    return () => this.listeners.delete(fn)
  }

  /** The next `n` unused bytes. They are marked used before being returned. */
  async take(n) {
    if (!(n > 0)) throw new Error('take at least one byte')
    const start = this.consumed
    if (start + n > this.size) {
      throw new FragmentExhausted(`${this.name} has ${this.size - start} unused bytes, ${n} needed`)
    }
    this.#commit(start + n)
    return new Uint8Array(await this.blob.slice(start, start + n).arrayBuffer())
  }

  /**
   * The next whole, chunk-aligned unused chunk, as {index, bytes}. For values
   * that will become PUBLIC (a draw's revealed chunk, shared art): taking it
   * through the pool marks it used, so it never also ends up inside a secret.
   */
  async takeChunk(chunkSize = CHUNK_SIZE) {
    const index = Math.ceil(this.consumed / chunkSize)
    const start = index * chunkSize
    if (start + chunkSize > this.size) throw new FragmentExhausted(`${this.name} has no whole unused chunk left`)
    this.#commit(start + chunkSize)
    return { index, bytes: new Uint8Array(await this.blob.slice(start, start + chunkSize).arrayBuffer()) }
  }

  #commit(consumed) {
    this.memory = consumed
    try {
      localStorage.setItem(this.key, String(consumed))
    } catch {
      // Storage unavailable: the in-memory cursor still prevents reuse in this tab.
    }
    for (const fn of this.listeners) fn(this)
  }

  /** Secret material: HKDF(os_random ‖ next 32 fragment bytes). */
  async mixed(purpose, length) {
    return mix(await this.take(QUANTUM_BYTES), purpose, length)
  }

  /** Raw bytes at a fixed offset, WITHOUT consuming them — for public, reproducible uses only. */
  async peek(offset, n) {
    if (offset < 0 || offset + n > this.size) throw new Error('outside the fragment')
    return new Uint8Array(await this.blob.slice(offset, offset + n).arrayBuffer())
  }
}
