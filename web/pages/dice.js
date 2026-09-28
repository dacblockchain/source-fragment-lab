import { randbelow, refillingReader } from '../lib/rng.js'
import { $, el, header, mountLoader, mountPoolStatus } from '../lib/ui.js'

document.body.prepend(header('dice.html'))

const KINDS = [
  ['coin', 2],
  ['d4', 4],
  ['d6', 6],
  ['d8', 8],
  ['d10', 10],
  ['d12', 12],
  ['d20', 20],
  ['d100', 100],
]
const MAX_DICE = 20
let kind = KINDS[2]
let pool = null

for (const k of KINDS) {
  const b = el('button', { type: 'button', 'aria-pressed': String(k === kind) }, k[0])
  b.addEventListener('click', () => {
    kind = k
    for (const other of $('#kinds').children) other.setAttribute('aria-pressed', String(other === b))
  })
  $('#kinds').append(b)
}

mountLoader($('#loader'), ({ pool: loaded }) => {
  pool = loaded
  mountPoolStatus($('#status'), pool)
  $('#roll').disabled = false
})

function face(label, value, sides) {
  if (sides === 2) {
    return el('div', { class: 'die coin rolling' }, value === 0 ? 'Heads' : 'Tails')
  }
  return el('div', { class: `die rolling${value === sides ? ' max' : ''}` }, el('small', {}, label), String(value))
}

$('#roll').addEventListener('click', async () => {
  if (!pool) return
  const count = Math.min(MAX_DICE, Math.max(1, Number($('#count').value) || 1))
  const [label, sides] = kind
  const button = $('#roll')
  button.disabled = true
  try {
    // One HKDF block of 64 bytes costs 32 fragment bytes; more are drawn only if needed.
    const read = refillingReader(() => pool.mixed(`dice/${label}`, 64))
    const values = []
    for (let i = 0; i < count; i++) values.push((await randbelow(sides, read)) + (sides === 2 ? 0 : 1))
    $('#tray').replaceChildren(...values.map((v) => face(label, v, sides)))
    const summary = sides === 2
      ? `${values.filter((v) => v === 0).length} heads, ${values.filter((v) => v === 1).length} tails`
      : `total ${values.reduce((a, b) => a + b, 0)}`
    $('#total').textContent = sides === 2 ? '' : values.reduce((a, b) => a + b, 0)
    $('#history').prepend(el('li', {}, `${count}×${label}: ${sides === 2 ? values.map((v) => (v ? 'T' : 'H')).join(' ') : values.join(' ')} — ${summary}`))
  } catch (err) {
    $('#tray').replaceChildren(el('p', { class: 'bad' }, err.message))
  } finally {
    button.disabled = false
  }
})
