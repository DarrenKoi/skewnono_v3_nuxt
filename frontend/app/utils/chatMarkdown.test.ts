import assert from 'node:assert/strict'
import { describe, it } from 'node:test'
import { renderChatMarkdown } from './chatMarkdown.ts'

describe('renderChatMarkdown', () => {
  it('escapes HTML so raw markup cannot reach the DOM', () => {
    const out = renderChatMarkdown('<script>alert(1)</script>')
    assert.doesNotMatch(out, /<script>/)
    assert.match(out, /&lt;script&gt;/)
  })

  it('renders fenced code blocks with escaped content', () => {
    const out = renderChatMarkdown('before\n```js\nconst a = 1 < 2\n```\nafter')
    assert.match(out, /<pre class="sk-chat-code-block"><code>const a = 1 &lt; 2/)
    assert.match(out, /before/)
    assert.match(out, /after/)
  })

  it('renders inline code', () => {
    assert.match(
      renderChatMarkdown('use `npm run dev`'),
      /<code class="sk-chat-code-inline">npm run dev<\/code>/
    )
  })

  it('renders bold', () => {
    assert.match(renderChatMarkdown('this is **bold**'), /<strong>bold<\/strong>/)
  })

  it('renders http(s) links only, with safe rel', () => {
    const out = renderChatMarkdown('see [docs](https://example.com)')
    assert.match(out, /<a href="https:\/\/example.com" target="_blank" rel="noopener noreferrer">docs<\/a>/)
  })

  it('does not linkify non-http schemes', () => {
    const out = renderChatMarkdown('[x](javascript:alert(1))')
    assert.doesNotMatch(out, /<a/)
    assert.match(out, /\[x\]/)
  })

  it('converts newlines outside code to <br>', () => {
    assert.equal(renderChatMarkdown('line1\nline2'), 'line1<br>line2')
  })

  it('returns empty string for empty input', () => {
    assert.equal(renderChatMarkdown(''), '')
  })

  it('keeps two prose paragraphs as a double <br>', () => {
    assert.equal(renderChatMarkdown('a\n\nb'), 'a<br><br>b')
  })

  it('renders headings one level down, with escaped text', () => {
    const out = renderChatMarkdown('# 기간 요약\n### <b>세부</b>')
    assert.match(out, /<h2 class="sk-chat-h">기간 요약<\/h2>/)
    assert.match(out, /<h4 class="sk-chat-h">&lt;b&gt;세부&lt;\/b&gt;<\/h4>/)
    assert.doesNotMatch(out, /<br>/)
  })

  it('renders bullet and numbered lists', () => {
    const out = renderChatMarkdown('intro\n- one **b**\n* two\n\n1. first\n2) second')
    assert.match(out, /^intro<ul class="sk-chat-list"><li>one <strong>b<\/strong><\/li><li>two<\/li><\/ul>/)
    assert.match(out, /<ol class="sk-chat-list"><li>first<\/li><li>second<\/li><\/ol>$/)
  })

  it('renders a pipe table with a header row', () => {
    const out = renderChatMarkdown('| 날짜 | 건수 |\n|---|:--:|\n| 09-12 | 9 |\n| 09-13 | 12 |\nafter')
    assert.match(out, /<table class="sk-chat-table"><thead><tr><th>날짜<\/th><th>건수<\/th><\/tr><\/thead>/)
    assert.match(out, /<tbody><tr><td>09-12<\/td><td>9<\/td><\/tr><tr><td>09-13<\/td><td>12<\/td><\/tr><\/tbody>/)
    assert.match(out, /<\/table><\/div>after$/)
  })

  it('leaves a lone pipe line without a separator as prose', () => {
    assert.equal(renderChatMarkdown('| not | a table |'), '| not | a table |')
  })
})
