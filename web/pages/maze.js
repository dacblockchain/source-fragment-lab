import { randbelow, refillingReader } from '../lib/rng.js'
import { $, header, mountLoader, mountPoolStatus } from '../lib/ui.js'

document.body.prepend(header('maze.html'))

// Walls per cell as bits; a carved passage clears the bit on both sides.
const N = 1, E = 2, S = 4, W = 8
const DIRS = { up: [0, -1, N, S], right: [1, 0, E, W], down: [0, 1, S, N], left: [-1, 0, W, E] }
let pool = null
let game = null
let timer = 0

mountLoader($('#loader'), ({ pool: loaded }) => {
  pool = loaded
  mountPoolStatus($('#status'), pool)
  $('#new').disabled = false
  newMaze()
})

/** Iterative depth-first carve; every choice is an unbiased randbelow. */
async function carve(size, read) {
  const cells = new Uint8Array(size * size).fill(N | E | S | W)
  const seen = new Uint8Array(size * size)
  const stack = [[0, 0]]
  seen[0] = 1
  while (stack.length) {
    const [x, y] = stack[stack.length - 1]
    const options = Object.values(DIRS).filter(([dx, dy]) => {
      const nx = x + dx
      const ny = y + dy
      return nx >= 0 && ny >= 0 && nx < size && ny < size && !seen[ny * size + nx]
    })
    if (!options.length) {
      stack.pop()
      continue
    }
    const [dx, dy, wall, opposite] = options[await randbelow(options.length, read)]
    const nx = x + dx
    const ny = y + dy
    cells[y * size + x] &= ~wall
    cells[ny * size + nx] &= ~opposite
    seen[ny * size + nx] = 1
    stack.push([nx, ny])
  }
  return cells
}

async function newMaze() {
  if (!pool) return
  const size = Number($('#size').value)
  $('#new').disabled = true
  try {
    // One mixed draw (32 fragment bytes) yields 8,160 bytes: plenty for any size here.
    const read = refillingReader(() => pool.mixed('maze', 8160))
    game = { size, cells: await carve(size, read), x: 0, y: 0, moves: 0, start: 0, done: false, trail: [[0, 0]] }
    clearInterval(timer)
    $('#time').textContent = '0.0 s'
    $('#moves').textContent = '0'
    $('#message').textContent = 'Go! The clock starts on your first move.'
    $('#message').className = 'small muted'
    draw()
  } catch (err) {
    $('#message').textContent = err.message
    $('#message').className = 'small bad'
  } finally {
    $('#new').disabled = false
  }
}

function move(dir) {
  if (!game || game.done) return
  const [dx, dy, wall] = DIRS[dir]
  if (game.cells[game.y * game.size + game.x] & wall) return
  if (!game.start) {
    game.start = performance.now()
    timer = setInterval(() => { $('#time').textContent = `${((performance.now() - game.start) / 1000).toFixed(1)} s` }, 100)
  }
  game.x += dx
  game.y += dy
  game.moves += 1
  game.trail.push([game.x, game.y])
  $('#moves').textContent = String(game.moves)
  if (game.x === game.size - 1 && game.y === game.size - 1) {
    game.done = true
    clearInterval(timer)
    const seconds = ((performance.now() - game.start) / 1000).toFixed(1)
    $('#time').textContent = `${seconds} s`
    $('#message').textContent = `Out in ${seconds} s and ${game.moves} moves. Carve another?`
    $('#message').className = 'small ok'
  }
  draw()
}

function draw() {
  const canvas = $('#board')
  const ctx = canvas.getContext('2d')
  const css = getComputedStyle(document.documentElement)
  const { size, cells } = game
  const pad = 20
  const cell = (canvas.width - 2 * pad) / size
  ctx.fillStyle = css.getPropertyValue('--surface-2').trim()
  ctx.fillRect(0, 0, canvas.width, canvas.height)

  const accent = css.getPropertyValue('--accent').trim()
  const exit = [pad + (size - 0.5) * cell, pad + (size - 0.5) * cell]
  const glow = ctx.createRadialGradient(...exit, 0, ...exit, cell * 1.4)
  glow.addColorStop(0, accent)
  glow.addColorStop(1, 'transparent')
  ctx.fillStyle = glow
  ctx.fillRect(exit[0] - cell * 1.5, exit[1] - cell * 1.5, cell * 3, cell * 3)

  ctx.strokeStyle = accent
  ctx.globalAlpha = 0.35
  ctx.lineWidth = Math.max(2, cell * 0.18)
  ctx.lineCap = 'round'
  ctx.beginPath()
  game.trail.forEach(([x, y], i) => {
    const px = pad + (x + 0.5) * cell
    const py = pad + (y + 0.5) * cell
    if (i) ctx.lineTo(px, py)
    else ctx.moveTo(px, py)
  })
  ctx.stroke()
  ctx.globalAlpha = 1

  ctx.strokeStyle = css.getPropertyValue('--text').trim()
  ctx.lineWidth = Math.max(2, cell * 0.08)
  ctx.lineCap = 'square'
  ctx.beginPath()
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const c = cells[y * size + x]
      const x0 = pad + x * cell
      const y0 = pad + y * cell
      if (c & N) { ctx.moveTo(x0, y0); ctx.lineTo(x0 + cell, y0) }
      if (c & W) { ctx.moveTo(x0, y0); ctx.lineTo(x0, y0 + cell) }
      if (y === size - 1 && c & S) { ctx.moveTo(x0, y0 + cell); ctx.lineTo(x0 + cell, y0 + cell) }
      if (x === size - 1 && c & E) { ctx.moveTo(x0 + cell, y0); ctx.lineTo(x0 + cell, y0 + cell) }
    }
  }
  ctx.stroke()

  ctx.fillStyle = accent
  ctx.beginPath()
  ctx.arc(pad + (game.x + 0.5) * cell, pad + (game.y + 0.5) * cell, cell * 0.3, 0, Math.PI * 2)
  ctx.fill()
}

const KEYS = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', w: 'up', s: 'down', a: 'left', d: 'right' }
document.addEventListener('keydown', (e) => {
  const dir = KEYS[e.key] ?? KEYS[e.key.toLowerCase?.()]
  if (!dir || e.target.closest('input, select, textarea')) return
  e.preventDefault()
  move(dir)
})
for (const b of document.querySelectorAll('.pad button')) b.addEventListener('click', () => move(b.dataset.dir))

let touch = null
$('#board').addEventListener('pointerdown', (e) => { touch = [e.clientX, e.clientY] })
$('#board').addEventListener('pointerup', (e) => {
  if (!touch) return
  const dx = e.clientX - touch[0]
  const dy = e.clientY - touch[1]
  touch = null
  if (Math.max(Math.abs(dx), Math.abs(dy)) < 24) return
  move(Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : dy > 0 ? 'down' : 'up')
})
$('#new').addEventListener('click', newMaze)
$('#size').addEventListener('change', newMaze)
