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
})
