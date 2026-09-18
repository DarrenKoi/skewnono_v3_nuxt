// Minimal, dependency-free markdown for assistant chat replies.
//
// Inline: fenced code, inline code, bold, http(s) links. Block (added
// 2026-09-19 when the chat's job became report-shaped answers): headings
// (#, ##, ###), bullet and numbered lists, and pipe tables. Nothing else — a
// full markdown engine would be the first dependency whose output reaches
// v-html, and these six constructs are what the office model actually writes.
//
// SAFETY: every piece of source text is HTML-escaped BEFORE any tag is
// introduced, and the only tags produced here are <pre><code>, <code>,
// <strong>, <a> (http/https links only), <h2>-<h4>, <ul>/<ol>/<li>,
// <table>/<thead>/<tbody>/<tr>/<th>/<td>, <div> and <br>. There is no path
// for source text to reach the DOM as markup, so the result is safe for v-html.

const escapeHtml = (s: string): string =>
  s.replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')

// Inline transforms applied to already-escaped, non-code text.
const renderInline = (escaped: string): string =>
  escaped
    .replace(/`([^`]+)`/g, '<code class="sk-chat-code-inline">$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(
      /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>'
    )

const HEADING = /^(#{1,3})\s+(.+?)\s*#*$/
const BULLET = /^\s*[-*]\s+(.+)$/
const NUMBERED = /^\s*\d+[.)]\s+(.+)$/
// A table row is `| a | b |`; the header separator is `|---|:--:|`.
const TABLE_ROW = /^\s*\|.*\|\s*$/
const TABLE_SEPARATOR = /^\s*\|(\s*:?-+:?\s*\|)+\s*$/

const splitCells = (line: string): string[] =>
  line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim())

// One block-level pass over escaped text (no fences inside). Lines that are
// not a heading, list or table are prose and join with <br> exactly as they
// did before blocks existed — including blank lines, so a two-paragraph reply
// still reads `a<br><br>b`. Only the blanks that touch a block are dropped, so
// a heading does not arrive with a stray line break above it.
const renderBlocks = (escaped: string): string => {
  const lines = escaped.split('\n')
  const out: string[] = []
  let prose: string[] = []
  const flushProse = () => {
    while (prose.length && !prose[0]!.trim()) prose.shift()
    while (prose.length && !prose[prose.length - 1]!.trim()) prose.pop()
    if (prose.length) out.push(prose.map(renderInline).join('<br>'))
    prose = []
  }

  let i = 0
  while (i < lines.length) {
    const line = lines[i]!

    const heading = HEADING.exec(line)
    if (heading) {
      flushProse()
      // # → h2: the lane's "어시스턴트" author line is the h1-equivalent, so a
      // report's top heading sits one level under it.
      const level = heading[1]!.length + 1
      out.push(`<h${level} class="sk-chat-h">${renderInline(heading[2]!)}</h${level}>`)
      i++
      continue
    }

    if (TABLE_ROW.test(line) && i + 1 < lines.length && TABLE_SEPARATOR.test(lines[i + 1]!)) {
      flushProse()
      const header = splitCells(line).map(cell => `<th>${renderInline(cell)}</th>`).join('')
      const body: string[] = []
      i += 2
      while (i < lines.length && TABLE_ROW.test(lines[i]!)) {
        body.push(`<tr>${splitCells(lines[i]!).map(cell => `<td>${renderInline(cell)}</td>`).join('')}</tr>`)
        i++
      }
      out.push(
        `<div class="sk-chat-table-wrap"><table class="sk-chat-table"><thead><tr>${header}</tr></thead>`
        + `<tbody>${body.join('')}</tbody></table></div>`
      )
      continue
    }

    const listKind = BULLET.test(line) ? 'ul' : NUMBERED.test(line) ? 'ol' : null
    if (listKind) {
      flushProse()
      const pattern = listKind === 'ul' ? BULLET : NUMBERED
      const items: string[] = []
      while (i < lines.length) {
        const item = pattern.exec(lines[i]!)
        if (!item) break
        items.push(`<li>${renderInline(item[1]!)}</li>`)
        i++
      }
      out.push(`<${listKind} class="sk-chat-list">${items.join('')}</${listKind}>`)
      continue
    }

    prose.push(line)
    i++
  }
  flushProse()
  return out.join('')
}

export const renderChatMarkdown = (text: string): string => {
  if (!text) return ''
  const fence = /```(\w*)\n?([\s\S]*?)```/g
  let out = ''
  let last = 0
  let match: RegExpExecArray | null

  while ((match = fence.exec(text)) !== null) {
    out += renderBlocks(escapeHtml(text.slice(last, match.index)))
    out += `<pre class="sk-chat-code-block"><code>${escapeHtml(match[2] ?? '')}</code></pre>`
    last = fence.lastIndex
  }
  out += renderBlocks(escapeHtml(text.slice(last)))
  return out
}
