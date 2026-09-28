// Uniform integers by rejection sampling, exactly as docs/mixing.md defines them.
// Integers use BigInt so bounds above 2^32 stay exact, like Python's int.

/** Serve a fixed byte array sequentially; throw when it runs out. */
export class ByteStream {
  constructor(data) {
    this.data = data
    this.pos = 0
  }

  read(n) {
    if (this.pos + n > this.data.length) throw new Error('the random stream ran out')
    const out = this.data.subarray(this.pos, this.pos + n)
    this.pos += n
    return out
  }
}

function bitLength(n) {
  return n === 0n ? 0 : n.toString(2).length
}

/**
 * A uniform integer in [0, n). `read(size)` returns `size` bytes (sync or async).
 * Returns a Number when n is a Number, a BigInt when n is a BigInt.
 */
export async function randbelow(n, read) {
  const big = BigInt(n)
  if (big < 1n) throw new Error(`randbelow needs n >= 1, not ${n}`)
  if (big === 1n) return typeof n === 'bigint' ? 0n : 0
  const bits = bitLength(big - 1n)
  const size = Math.ceil(bits / 8)
  const mask = (1n << BigInt(bits)) - 1n
  for (;;) {
    const bytes = await read(size)
    let x = 0n
    for (const b of bytes) x = (x << 8n) | BigInt(b)
    x &= mask
    if (x < big) return typeof n === 'bigint' ? x : Number(x)
  }
}

/**
 * A reader that refills itself from an async `refill()` returning fresh bytes —
 * used by games that draw mixed randomness in blocks.
 */
export function refillingReader(refill) {
  let buffer = new Uint8Array(0)
  return async (n) => {
    while (buffer.length < n) {
      const more = await refill()
      const next = new Uint8Array(buffer.length + more.length)
      next.set(buffer)
      next.set(more, buffer.length)
      buffer = next
    }
    const out = buffer.slice(0, n)
    buffer = buffer.slice(n)
    return out
  }
}
