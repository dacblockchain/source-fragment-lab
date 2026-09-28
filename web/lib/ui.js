// Shared page pieces: the fragment loader and the "bytes used" status line.
// A File cannot follow the user between pages, so only the demo choice is
// remembered (sessionStorage); a real fragment is re-selected on each page.

import { formatBytes } from './bytes.js'
import { FragmentPool } from './pool.js'

export const DEMO_BIN = new URL('../demo/demo-fragment.bin', import.meta.url)
export const DEMO_PROOF = new URL('../demo/demo-fragment.proof.json', import.meta.url)
const DEMO_FLAG = 'source-fragment-lab/demo'

export const $ = (sel, root = document) => root.querySelector(sel)

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'class') node.className = v
    else if (k.startsWith('on')) node.addEventListener(k.slice(2), v)
    else node.setAttribute(k, v)
  }
  for (const c of children) node.append(c)
  return node
}

function remember(isDemo) {
  try {
    if (isDemo) sessionStorage.setItem(DEMO_FLAG, '1')
    else sessionStorage.removeItem(DEMO_FLAG)
  } catch {
    // no storage: the demo simply is not remembered across pages
  }
}

function demoRemembered() {
  try {
    return sessionStorage.getItem(DEMO_FLAG) === '1'
  } catch {
    return false
  }
}

export async function fetchDemo() {
  const [bin, proof] = await Promise.all([fetch(DEMO_BIN), fetch(DEMO_PROOF)])
  if (!bin.ok || !proof.ok) throw new Error('the demo fragment could not be loaded')
  const blob = await bin.blob()
  return { blob, proofText: await proof.text() }
}

/**
 * Render a loader into `host`. `onLoad({pool, blob, name, demo, proofText})`
 * fires once per fragment. With `withProof`, a proof.json can be picked too.
 */
export function mountLoader(host, onLoad, { withProof = false } = {}) {
  const fileInput = el('input', { type: 'file', accept: withProof ? '.bin,.json,application/json' : '.bin', multiple: withProof ? '' : null })
  if (!withProof) fileInput.removeAttribute('multiple')
  const note = el('p', { class: 'small muted' })
  const drop = el(
    'div',
    { class: 'drop' },
    el('p', {}, withProof ? 'Drop your source-fragment .bin (and its .proof.json) here, or ' : 'Drop your source-fragment .bin here, or '),
    el('label', { class: 'button' }, 'choose file', fileInput),
    el('p', { class: 'small' }, 'Files never leave your browser.'),
  )
  fileInput.style.display = 'none'
  const demoButton = el('button', { type: 'button' }, 'Try the demo fragment')
  const demoTag = el('span', { class: 'tag demo' }, 'PRNG demo, not quantum')
  host.replaceChildren(drop, el('div', { class: 'row', style: 'margin-top:12px' }, demoButton, demoTag), note)

  async function load(blob, name, demo, proofText = null) {
    try {
      const pool = await FragmentPool.open(blob, name)
      remember(demo)
      note.textContent = `Loaded ${name} (${formatBytes(blob.size)})${demo ? ' — demo bytes from a seeded PRNG, not quantum entropy.' : '.'}`
      note.className = demo ? 'small warn' : 'small ok'
      await onLoad({ pool, blob, name, demo, proofText })
    } catch (err) {
      note.textContent = err.message
      note.className = 'small bad'
    }
  }

  async function fromFiles(files) {
    const list = [...files]
    const bin = list.find((f) => !f.name.endsWith('.json'))
    const proofFile = list.find((f) => f.name.endsWith('.json'))
    if (!bin) {
      note.textContent = 'Pick the .bin file (the proof alone is not enough).'
      note.className = 'small bad'
      return
    }
    await load(bin, bin.name, false, proofFile ? await proofFile.text() : null)
  }

  async function demo() {
    try {
      const { blob, proofText } = await fetchDemo()
      await load(blob, 'demo-fragment.bin', true, proofText)
    } catch (err) {
      note.textContent = err.message
      note.className = 'small bad'
    }
  }

  fileInput.addEventListener('change', () => fromFiles(fileInput.files))
  drop.addEventListener('dragover', (e) => { e.preventDefault(); drop.classList.add('over') })
  drop.addEventListener('dragleave', () => drop.classList.remove('over'))
  drop.addEventListener('drop', (e) => {
    e.preventDefault()
    drop.classList.remove('over')
    fromFiles(e.dataTransfer.files)
  })
  demoButton.addEventListener('click', demo)
  if (demoRemembered()) demo()
  return { demo }
}

/** Keep a "N used · M left" line and a meter in sync with the pool. */
export function mountPoolStatus(host, pool) {
  const text = el('p', { class: 'small muted', style: 'margin:0 0 6px' })
  const bar = el('div')
  host.replaceChildren(text, el('div', { class: 'meter' }, bar))
  const render = () => {
    const used = pool.consumed
    text.textContent = `${formatBytes(used)} used · ${formatBytes(pool.size - used)} left of ${formatBytes(pool.size)}`
    bar.style.width = `${((100 * used) / pool.size).toFixed(2)}%`
  }
  render()
  pool.onChange(render)
}

export function header(active) {
  const pages = [
    ['index.html', 'Lab'],
    ['dice.html', 'Dice'],
    ['starmap.html', 'Star map'],
    ['maze.html', 'Maze'],
    ['draw.html', 'Draw'],
  ]
  const nav = el('nav', { class: 'site', 'aria-label': 'Pages' })
  for (const [href, label] of pages) {
    const a = el('a', { href }, label)
    if (href === active) a.setAttribute('aria-current', 'page')
    nav.append(a)
  }
  return el(
    'header',
    { class: 'site' },
    el('div', { class: 'wrap' }, el('a', { class: 'brand', href: 'index.html' }, 'Source Fragment ', el('span', {}, 'Lab')), nav),
  )
}

export const RULE_TEXT = 'Never use these bytes alone as a key — we saw them. Mix them with your own randomness.'
