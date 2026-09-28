import { fromHex, toHex } from '../lib/bytes.js'
import { blockHash, latestBlock } from '../lib/chain.js'
import { CHUNK_SIZE, chunkCommitment, normaliseEntries, runDraw } from '../lib/draw.js'
import { $, el, header, mountLoader, mountPoolStatus } from '../lib/ui.js'

document.body.prepend(header('draw.html'))

const BLOCK_SECONDS = 5 // DAC mainnet block time
const LEAD_BLOCKS = 720 // suggest H about an hour ahead
let pool = null
let reserved = null

for (const tab of document.querySelectorAll('[role=tab]')) {
  tab.addEventListener('click', () => {
    for (const t of document.querySelectorAll('[role=tab]')) {
      const on = t === tab
      t.setAttribute('aria-selected', String(on))
      $(`#tab-${t.dataset.tab}`).hidden = !on
    }
  })
}

const item = (cls, text) => el('li', { class: cls }, text)

// ── Check a draw ──
$('#v-fetch').addEventListener('click', async () => {
  const out = $('#v-out')
  try {
    $('#v-hash').value = await blockHash(Number($('#v-height').value))
  } catch (err) {
    out.replaceChildren(item('warn', err.message))
  }
})

let expectedCount = null
$('#v-transcript').addEventListener('change', async () => {
  const out = $('#v-out')
  try {
    const t = JSON.parse(await $('#v-transcript').files[0].text())
    if (t.format !== 'source-fragment-lab/draw/v1') throw new Error(`not a draw/v1 transcript: ${t.format}`)
    $('#v-chunk').value = t.chunk_hex
    $('#v-hash').value = t.block_hash
    $('#v-height').value = t.block ?? ''
    $('#v-k').value = String(t.winners.length)
    expectedCount = t.entries
    out.replaceChildren(item('muted', `Transcript loaded: ${t.entries} entries, winners ${t.winners.join(', ')}. Paste the published entry list, and the commitment as it was ANNOUNCED (not from the transcript), then recompute. Fetch the block hash yourself too.`))
  } catch (err) {
    out.replaceChildren(item('bad', err.message))
  }
})

$('#v-run').addEventListener('click', async () => {
  const out = $('#v-out')
  out.replaceChildren()
  $('#winners').replaceChildren()
  try {
    const chunk = fromHex($('#v-chunk').value.replace(/\s+/g, ''))
    if (chunk.length !== CHUNK_SIZE) throw new Error(`the chunk is ${chunk.length} bytes, a draw needs ${CHUNK_SIZE}`)
    const commitment = await chunkCommitment(chunk)
    const announced = $('#v-commit').value.trim().toLowerCase()
    if (announced) {
      out.append(announced === commitment
        ? item('ok', `Chunk matches the announced commitment ✓`)
        : item('bad', `Chunk hashes to ${commitment}, NOT the announced ${announced}. Do not trust this draw.`))
    } else {
      out.append(item('bad', `No commitment given, so this check proves nothing. The chunk hashes to ${commitment}: compare it with what was announced.`))
    }
    const entries = normaliseEntries($('#v-entries').value)
    const result = await runDraw(chunk, $('#v-hash').value.trim(), entries, Number($('#v-k').value))
    out.append(item('muted', `${entries.length} entries · entries hash ${result.entriesHash}`))
    if (expectedCount != null && expectedCount !== entries.length) {
      out.append(item('bad', `The transcript says ${expectedCount} entries; the list you pasted has ${entries.length}.`))
    }
    $('#winners').replaceChildren(...result.winners.map((w) => el('li', {}, w)))
  } catch (err) {
    out.append(item('bad', err.message))
  }
})

// ── Run a draw ──
mountLoader($('#loader'), ({ pool: loaded }) => {
  pool = loaded
  reserved = null
  mountPoolStatus($('#status'), pool)
  $('#r-reserve').disabled = false
  $('#r-announce').replaceChildren()
})

function kv(term, value) {
  return [el('dt', {}, term), el('dd', { class: 'mono' }, value)]
}

$('#r-reserve').addEventListener('click', async () => {
  try {
    const { index, bytes } = await pool.takeChunk(CHUNK_SIZE)
    reserved = { index, bytes, commitment: await chunkCommitment(bytes) }
    let suggestion = ''
    try {
      const now = await latestBlock()
      suggestion = String(now + LEAD_BLOCKS)
      $('#r-height').value = suggestion
    } catch {
      suggestion = '(RPC unreachable — pick a height after your close)'
    }
    $('#r-announce').replaceChildren(
      ...kv('Fragment', pool.name),
      ...kv('Chunk index', String(index)),
      ...kv('Commitment', reserved.commitment),
      ...kv('Block H', `${suggestion} (≈ ${Math.round((LEAD_BLOCKS * BLOCK_SECONDS) / 60)} min from now — must be AFTER entries close)`),
    )
    $('#r-run').disabled = false
    $('#r-reserve').disabled = true
    $('#r-note').textContent = 'Publish these three values now, before entries close. Keep this tab open, or note the chunk index: the chunk can be re-read from your file later.'
  } catch (err) {
    $('#r-note').textContent = err.message
    $('#r-note').className = 'small bad'
  }
})

$('#r-run').addEventListener('click', async () => {
  const note = $('#r-note')
  note.className = 'small muted'
  try {
    const height = Number($('#r-height').value)
    const hash = await blockHash(height)
    const entries = normaliseEntries($('#r-entries').value)
    const k = Number($('#r-k').value)
    const result = await runDraw(reserved.bytes, hash, entries, k)
    $('#run-winners').replaceChildren(...result.winners.map((w) => el('li', {}, w)))
    // Same keys as `fragmentlab draw run`, so either tool reads the other's output.
    const transcript = {
      format: 'source-fragment-lab/draw/v1',
      block: height,
      block_hash: result.blockHash,
      chunk_commitment: result.chunkCommitment,
      chunk_hex: toHex(reserved.bytes),
      entries_hash: result.entriesHash,
      entries: entries.length,
      winners: result.winners,
    }
    const link = $('#r-transcript')
    link.href = URL.createObjectURL(new Blob([JSON.stringify(transcript, null, 2) + '\n'], { type: 'application/json' }))
    link.download = `draw-chunk-${reserved.index}.json`
    link.hidden = false
    note.textContent = `Block ${height} hash ${hash}. Publish the transcript: it holds the revealed chunk, so anyone can recompute the winners.`
  } catch (err) {
    note.textContent = err.message
    note.className = 'small bad'
  }
})
