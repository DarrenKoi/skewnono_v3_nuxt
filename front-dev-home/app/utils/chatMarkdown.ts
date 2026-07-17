// Minimal, dependency-free markdown for assistant chat replies. LLM output
// leans on fenced code, inline code, bold, and links; supporting just those
// makes replies readable without pulling in a full markdown engine.
//
// SAFETY: every piece of source text is HTML-escaped BEFORE any tag is
// introduced, and the only tags produced here are <pre><code>, <code>,
// <strong>, <a> (http/https links only). There is no path for source text to
// reach the DOM as markup, so the result is safe for v-html.

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
    .replace(/\n/g, '<br>')

export const renderChatMarkdown = (text: string): string => {
  if (!text) return ''
  const fence = /```(\w*)\n?([\s\S]*?)```/g
  let out = ''
  let last = 0
  let match: RegExpExecArray | null

  while ((match = fence.exec(text)) !== null) {
    out += renderInline(escapeHtml(text.slice(last, match.index)))
    out += `<pre class="sk-chat-code-block"><code>${escapeHtml(match[2] ?? '')}</code></pre>`
    last = fence.lastIndex
  }
  out += renderInline(escapeHtml(text.slice(last)))
  return out
}
