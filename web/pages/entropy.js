// Sanity statistics over (a prefix of) a fragment. Not a randomness proof.

const SAMPLE_LIMIT = 16 * 1024 * 1024
const BATCH = 1024 * 1024

export async function analyse(blob) {
  const sampled = Math.min(blob.size, SAMPLE_LIMIT)
  const counts = new Array(256).fill(0)
  let ones = 0
  for (let at = 0; at < sampled; at += BATCH) {
    const bytes = new Uint8Array(await blob.slice(at, Math.min(sampled, at + BATCH)).arrayBuffer())
    for (const b of bytes) {
      counts[b]++
    }
  }
  const popcount = (b) => { let n = 0; for (; b; b >>= 1) n += b & 1; return n }
  counts.forEach((c, b) => { ones += c * popcount(b) })

  const expected = sampled / 256
  let entropy = 0
  let chi = 0
  for (const c of counts) {
    if (c) entropy -= (c / sampled) * Math.log2(c / sampled)
    chi += (c - expected) ** 2 / expected
  }
  return { sampled, counts, entropy, chi, p: chiSquareUpperTail(chi, 255), ones: ones / (sampled * 8) }
}

// Wilson–Hilferty approximation: good to a few decimals at 255 degrees of freedom.
function chiSquareUpperTail(x, k) {
  const z = (Math.cbrt(x / k) - (1 - 2 / (9 * k))) / Math.sqrt(2 / (9 * k))
  return 1 - normalCdf(z)
}

function normalCdf(z) {
  // Abramowitz–Stegun 7.1.26 erf approximation.
  const t = 1 / (1 + (0.3275911 * Math.abs(z)) / Math.SQRT2)
  const poly = t * (0.254829592 + t * (-0.284496736 + t * (1.421413741 + t * (-1.453152027 + t * 1.061405429))))
  const erf = 1 - poly * Math.exp(-(z * z) / 2)
  return z >= 0 ? (1 + erf) / 2 : (1 - erf) / 2
}
