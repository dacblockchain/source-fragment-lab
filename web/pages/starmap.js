import { enc, sha256, toHex } from '../lib/bytes.js'
import { MAX_OUTPUT, hkdf } from '../lib/hkdf.js'
import { ByteStream } from '../lib/rng.js'
import { $, header, mountLoader, mountPoolStatus } from '../lib/ui.js'

document.body.prepend(header('starmap.html'))

const CHUNK = 2048
const SALT = enc.encode('source-fragment-lab/starmap/v1')
const STARS = 520
const CONSTELLATIONS = 5
let pool = null

mountLoader($('#loader'), async ({ pool: loaded }) => {
  pool = loaded
  mountPoolStatus($('#status'), pool)
  $('#next').disabled = false
  $('#redraw').disabled = false
  $('#index').max = String(Math.floor(pool.size / CHUNK) - 1)
  // Show the last FULLY used chunk, if any: re-drawing never exposes unused bytes.
  const last = Math.floor(pool.consumed / CHUNK) - 1
  if (last >= 0) {
    $('#index').value = String(last)
    await render(last, await pool.peek(last * CHUNK, CHUNK))
  } else {
    blank('Press “Draw a new sky” to spend your first chunk on a map.')
  }
})

function blank(message) {
  const canvas = $('#sky')
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = '#03060d'
  ctx.fillRect(0, 0, canvas.width, canvas.height)
  $('#caption').textContent = message
}

$('#next').addEventListener('click', async () => {
  try {
    const { index, bytes } = await pool.takeChunk(CHUNK)
    $('#index').value = String(index)
    await render(index, bytes)
  } catch (err) {
    $('#caption').textContent = err.message
  }
})

$('#redraw').addEventListener('click', async () => {
  const index = Number($('#index').value)
  if (!Number.isInteger(index) || index < 0 || (index + 1) * CHUNK > pool.size) {
    $('#caption').textContent = 'That chunk is not inside the fragment.'
    return
  }
  if ((index + 1) * CHUNK > pool.consumed) {
    $('#caption').textContent = `Chunk #${index} is not used yet — only used chunks can be re-drawn, so a shared map never exposes bytes a future key could draw from.`
    return
  }
  await render(index, await pool.peek(index * CHUNK, CHUNK))
})

async function render(index, chunk) {
  // Deterministic expansion: 2,048 bytes is not enough for 500 stars, so stretch it.
  const s = new ByteStream(await hkdf(chunk, SALT, new Uint8Array(0), MAX_OUTPUT))
  const u8 = () => s.read(1)[0]
  const unit = () => { const b = s.read(2); return ((b[0] << 8) | b[1]) / 65536 }
  const canvas = $('#sky')
  const ctx = canvas.getContext('2d')
  const size = canvas.width

  ctx.fillStyle = '#03060d'
  ctx.fillRect(0, 0, size, size)
  const baseHue = u8() * (360 / 256)
  for (let i = 0; i < 4; i++) {
    const x = unit() * size
    const y = unit() * size
    const r = size * (0.25 + unit() * 0.45)
    const hue = (baseHue + (u8() - 128) * 0.6 + 360) % 360
    const g = ctx.createRadialGradient(x, y, 0, x, y, r)
    g.addColorStop(0, `hsla(${hue}, 70%, 45%, 0.28)`)
    g.addColorStop(0.5, `hsla(${(hue + 30) % 360}, 60%, 30%, 0.10)`)
    g.addColorStop(1, 'hsla(0, 0%, 0%, 0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
  }

  const stars = []
  for (let i = 0; i < STARS; i++) {
    const mag = unit() ** 3 // most stars faint, a few bright
    stars.push({ x: unit() * size, y: unit() * size, r: 0.8 + mag * 4.2, mag, hue: 190 + u8() * 0.3 - (u8() > 200 ? 170 : 0) })
  }
  for (const st of stars) {
    ctx.fillStyle = `hsla(${st.hue}, 60%, ${80 + st.mag * 20}%, ${0.45 + st.mag * 0.55})`
    ctx.beginPath()
    ctx.arc(st.x, st.y, st.r, 0, Math.PI * 2)
    ctx.fill()
    if (st.mag > 0.5) {
      const glow = ctx.createRadialGradient(st.x, st.y, 0, st.x, st.y, st.r * 7)
      glow.addColorStop(0, `hsla(${st.hue}, 80%, 85%, 0.35)`)
      glow.addColorStop(1, 'hsla(0, 0%, 0%, 0)')
      ctx.fillStyle = glow
      ctx.fillRect(st.x - st.r * 7, st.y - st.r * 7, st.r * 14, st.r * 14)
    }
  }

  drawConstellations(ctx, stars, s)

  const digest = toHex(await sha256(chunk))
  ctx.fillStyle = 'rgba(255, 250, 235, 0.55)'
  ctx.font = '600 22px Archivo, system-ui, sans-serif'
  ctx.fillText(`${pool.name} · chunk #${index}`, 28, size - 52)
  ctx.font = '16px ui-monospace, monospace'
  ctx.fillText(`sha256 ${digest.slice(0, 32)}…`, 28, size - 26)
  $('#caption').textContent = `chunk #${index} · sha256 ${digest}`
  canvas.toBlob((blob) => {
    const link = $('#download')
    if (link.href) URL.revokeObjectURL(link.href)
    link.href = URL.createObjectURL(blob)
    link.download = `star-map-chunk-${index}.png`
    link.removeAttribute('aria-disabled')
  })
}

function drawConstellations(ctx, stars, s) {
  const bright = stars.filter((st) => st.mag > 0.25)
  const used = new Set()
  ctx.strokeStyle = 'rgba(240, 130, 100, 0.7)'
  ctx.lineWidth = 2.6
  ctx.lineJoin = 'round'
  for (let c = 0; c < CONSTELLATIONS && bright.length; c++) {
    let current = bright[s.read(1)[0] % bright.length]
    const length = 4 + (s.read(1)[0] % 4)
    used.add(current)
    ctx.beginPath()
    ctx.moveTo(current.x, current.y)
    for (let k = 1; k < length; k++) {
      const next = bright
        .filter((st) => !used.has(st))
        .map((st) => [st, Math.hypot(st.x - current.x, st.y - current.y)])
        .filter(([, d]) => d > 40 && d < 260)
        .sort((a, b) => a[1] - b[1])[0]?.[0]
      if (!next) break
      used.add(next)
      ctx.lineTo(next.x, next.y)
      current = next
    }
    ctx.stroke()
  }
}
