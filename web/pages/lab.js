import { formatBytes } from '../lib/bytes.js'
import { ChainError, RESERVOIR_ANCHOR, ZERO_ROOT, rootOf } from '../lib/chain.js'
import { ProofError, parseProof, verifyBlob } from '../lib/proof.js'
import { $, RULE_TEXT, el, header, mountLoader, mountPoolStatus } from '../lib/ui.js'
import { analyse } from './entropy.js'

document.body.prepend(header('index.html'))
$('#rule').textContent = RULE_TEXT
$('#anchor').textContent = RESERVOIR_ANCHOR

let current = null

mountLoader(
  $('#loader'),
  async (loaded) => {
    current = loaded
    mountPoolStatus($('#status'), loaded.pool)
    $('#verify-out').replaceChildren()
    $('#verify-bar').style.width = '0'
    const ready = Boolean(loaded.proofText)
    $('#verify').disabled = !ready
    $('#verify-note').textContent = ready ? 'Ready.' : 'Add the matching .proof.json (drop both files together).'
    await renderStats(loaded.blob)
  },
  { withProof: true },
)

function line(cls, ...parts) {
  return el('li', { class: cls }, ...parts)
}

async function chainVerdict(range) {
  if (range.anchorTx == null) {
    return line('warn', `Version ${range.version}: anchoring still pending in the proof — check again later.`)
  }
  try {
    const onChain = await rootOf(range.version)
    if (onChain === ZERO_ROOT) return line('warn', `Version ${range.version}: nothing anchored on-chain for this version yet.`)
    if (onChain === range.root.toLowerCase()) {
      return line('ok', `Version ${range.version}: on-chain root matches ✓ `, el('span', { class: 'small muted mono' }, `tx ${range.anchorTx}`))
    }
    return line('bad', `Version ${range.version}: on-chain root ${onChain} does NOT match the proof.`)
  } catch (err) {
    if (err instanceof ChainError) return line('warn', `Version ${range.version}: RPC unreachable (${err.message}). Your local check still stands.`)
    throw err
  }
}

$('#verify').addEventListener('click', async () => {
  if (!current?.proofText) return
  const out = $('#verify-out')
  const button = $('#verify')
  button.disabled = true
  out.replaceChildren(line('muted', 'Hashing your bytes…'))
  try {
    const proof = parseProof(current.proofText)
    const results = await verifyBlob(current.blob, proof, (done, total) => {
      $('#verify-bar').style.width = `${((100 * done) / total).toFixed(1)}%`
    })
    out.replaceChildren()
    for (const r of results) {
      out.append(
        r.ok
          ? line('ok', `Version ${r.version}: your bytes rebuild the proof's root ✓ `, el('span', { class: 'small muted mono' }, r.rebuilt))
          : line('bad', `Version ${r.version}: your bytes rebuild ${r.rebuilt}, the proof says ${r.root}.`),
      )
    }
    if (current.demo) {
      out.append(line('warn', 'Demo fragment: its roots were never anchored on-chain, so the chain check is skipped.'))
    } else {
      for (const r of results.filter((x) => x.ok)) out.append(await chainVerdict(r))
    }
  } catch (err) {
    out.replaceChildren(line('bad', err instanceof ProofError ? `Proof problem: ${err.message}` : err.message))
  } finally {
    button.disabled = false
  }
})

async function renderStats(blob) {
  const s = await analyse(blob)
  drawHistogram($('#histogram'), s.counts)
  const tile = (label, value, hint) =>
    el('div', {}, el('div', { class: 'small muted' }, label), el('div', { class: 'stat' }, value), el('div', { class: 'small muted' }, hint))
  $('#stats').replaceChildren(
    tile('Sampled', formatBytes(s.sampled), s.sampled < blob.size ? `first ${formatBytes(s.sampled)} of ${formatBytes(blob.size)}` : 'the whole file'),
    tile('Shannon entropy', `${s.entropy.toFixed(4)} bits/byte`, 'ideal: 8 (short samples read a bit lower)'),
    tile('Chi-square (255 df)', s.chi.toFixed(1), `ideal ≈ 255 · p ≈ ${s.p.toFixed(3)}`),
    tile('Monobit', `${(100 * s.ones).toFixed(3)}% ones`, 'ideal: 50%'),
  )
}

function drawHistogram(canvas, counts) {
  const ctx = canvas.getContext('2d')
  const styles = getComputedStyle(document.documentElement)
  const { width, height } = canvas
  const max = Math.max(...counts)
  const mean = counts.reduce((a, b) => a + b, 0) / 256
  ctx.clearRect(0, 0, width, height)
  ctx.fillStyle = styles.getPropertyValue('--accent').trim()
  const w = width / 256
  counts.forEach((c, i) => {
    const h = (c / max) * (height - 10)
    ctx.fillRect(i * w, height - h, Math.max(1, w - 0.5), h)
  })
  ctx.strokeStyle = styles.getPropertyValue('--text').trim()
  ctx.setLineDash([4, 4])
  const y = height - (mean / max) * (height - 10)
  ctx.beginPath()
  ctx.moveTo(0, y)
  ctx.lineTo(width, y)
  ctx.stroke()
}
