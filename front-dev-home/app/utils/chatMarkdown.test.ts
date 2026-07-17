import { describe, it, expect } from 'vitest'
import { renderChatMarkdown } from './chatMarkdown'

describe('renderChatMarkdown', () => {
  it('escapes HTML so raw markup cannot reach the DOM', () => {
    const out = renderChatMarkdown('<script>alert(1)</script>')
    expect(out).not.toContain('<script>')
    expect(out).toContain('&lt;script&gt;')
  })

  it('renders fenced code blocks with escaped content', () => {
    const out = renderChatMarkdown('before\n```js\nconst a = 1 < 2\n```\nafter')
    expect(out).toContain('<pre class="sk-chat-code-block"><code>const a = 1 &lt; 2')
    expect(out).toContain('before')
    expect(out).toContain('after')
  })

  it('renders inline code', () => {
    expect(renderChatMarkdown('use `npm run dev`')).toContain(
      '<code class="sk-chat-code-inline">npm run dev</code>'
    )
  })

  it('renders bold', () => {
    expect(renderChatMarkdown('this is **bold**')).toContain('<strong>bold</strong>')
  })

  it('renders http(s) links only, with safe rel', () => {
    const out = renderChatMarkdown('see [docs](https://example.com)')
    expect(out).toContain('<a href="https://example.com" target="_blank" rel="noopener noreferrer">docs</a>')
  })

  it('does not linkify non-http schemes', () => {
    const out = renderChatMarkdown('[x](javascript:alert(1))')
    expect(out).not.toContain('<a')
    expect(out).toContain('[x]')
  })

  it('converts newlines outside code to <br>', () => {
    expect(renderChatMarkdown('line1\nline2')).toBe('line1<br>line2')
  })

  it('returns empty string for empty input', () => {
    expect(renderChatMarkdown('')).toBe('')
  })
})
