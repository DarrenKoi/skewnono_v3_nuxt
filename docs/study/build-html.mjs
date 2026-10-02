// Markdown is the sole content source. Reuses markdown-it already installed by repo lint tooling.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import { fileURLToPath } from 'node:url'
import { createRequire } from 'node:module'
const root = path.dirname(fileURLToPath(import.meta.url))
const repo = path.resolve(root, '../..')
const require = createRequire(path.join(repo, 'package.json'))
const MarkdownIt = require('markdown-it')
const md = new MarkdownIt({ html: false, linkify: true, typographer: false })
const esc = value => md.utils.escapeHtml(value)
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : e.name.endsWith('.md') ? [path.join(dir, e.name)] : [])
const files = walk(root).sort((a, b) => a.localeCompare(b, 'en'))
const title = file => fs.readFileSync(file, 'utf8').match(/^# (.+)$/m)?.[1] || path.basename(file)
const htmlPath = file => file.replace(/\.md$/, '.html')
const href = (from, to) => path.relative(path.dirname(from), to).split(path.sep).join('/')
const home = path.join(root, 'README.md')
const chapters = files.filter(f => /^\d{2}-[^/]+\/README\.md$/.test(path.relative(root, f)))
const ordered = [home, ...chapters.flatMap(f => [f, ...files.filter(p => path.dirname(p) === path.dirname(f) && p !== f)]), ...files.filter(f => f !== home && !chapters.some(c => path.dirname(f) === path.dirname(c)))]
function remap(url, current) {
  if (/^(?:[a-z]+:|\/\/|#)/i.test(url)) return url
  const [file, fragment] = url.split('#')
  const absolute = path.resolve(path.dirname(current), decodeURIComponent(file))
  if (fs.existsSync(absolute) && fs.statSync(absolute).isDirectory() && fs.existsSync(path.join(absolute, 'README.md'))) return href(current, htmlPath(path.join(absolute, 'README.md'))) + (fragment ? '#' + fragment : '')
  if (absolute.startsWith(root + path.sep) && absolute.endsWith('.md') && fs.existsSync(absolute)) return href(current, htmlPath(absolute)) + (fragment ? '#' + fragment : '')
  return url
}
function render(file) {
  const source = fs.readFileSync(file, 'utf8')
  const tokens = md.parse(source, {})
  const headings = []
  const used = new Map()
  function patch(list) {
    for (let i = 0; i < list.length; i++) {
      const t = list[i]
      if (t.type === 'heading_open') {
        const text = list[i + 1].content
        const base = text.toLowerCase().replace(/[^\p{L}\p{N}_\s-]/gu, '').replace(/\s+/g, '-')
        const n = used.get(base) || 0
        used.set(base, n + 1)
        const id = base + (n ? '-' + n : '')
        t.attrSet('id', id)
        if (t.tag === 'h2') headings.push({ id, text })
      }
      if (t.type === 'link_open') {
        const url = t.attrGet('href')
        t.attrSet('href', remap(url, file))
        if (/^https?:/i.test(url)) t.attrSet('class', 'external')
        else if (!url.startsWith('#') && !path.resolve(path.dirname(file), url.split('#')[0]).startsWith(root)) t.attrSet('class', 'source-link')
      }
      if (t.children) patch(t.children)
    }
  }
  patch(tokens)
  return { source, body: md.renderer.render(tokens, md.options, {}), headings }
}
const defaultImage = md.renderer.rules.image
md.renderer.rules.image = (tokens, idx, options, env, self) => {
  const image = defaultImage(tokens, idx, options, env, self)
  return tokens[idx].attrGet('src').endsWith('.svg') ? `<span class="diagram-image" role="group" aria-label="로컬 구조도: 좁은 화면에서는 좌우로 스크롤합니다" tabindex="0">${image}</span>` : image
}
const defaultFence = md.renderer.rules.fence
md.renderer.rules.fence = (tokens, idx, options, env, self) => {
  const rendered = defaultFence(tokens, idx, options, env, self)
  return rendered.replace('<pre>', `<pre tabindex="0"${tokens[idx].info.trim() === 'text' ? ' class="diagram"' : ''}>`)
}
md.renderer.rules.table_open = () => '<div class="table-wrap" role="region" aria-label="표: 좌우로 스크롤할 수 있습니다" tabindex="0"><table>\n'
md.renderer.rules.table_close = () => '</table></div>\n'
for (const [index, file] of ordered.entries()) {
  const { source, body, headings } = render(file)
  const nav = chapters.map(c => `<li><a href="${esc(href(file, htmlPath(c)))}"${c === file ? ' aria-current="page"' : ''}>${esc(title(c))}</a></li>`).join('')
  const toc = headings.map(h => `<li><a href="#${esc(h.id)}">${esc(h.text)}</a></li>`).join('')
  const pager = [ordered[index - 1], ordered[index + 1]].map((f, i) => f ? `<a href="${esc(href(file, htmlPath(f)))}">${i ? '다음' : '이전'}: ${esc(title(f))}</a>` : '<span></span>').join('')
  const hash = crypto.createHash('sha256').update(source).digest('hex')
  const html = `<!doctype html>\n<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="source-sha256" content="${hash}"><meta name="body-sha256" content="${crypto.createHash('sha256').update(body).digest('hex')}"><title>${esc(title(file))} · SKEWNONO 학습</title><link rel="stylesheet" href="${href(file, path.join(root, 'assets/site.css'))}"></head><body><a class="skip" href="#main">본문으로 건너뛰기</a><header class="top"><a href="${href(file, htmlPath(home))}">SKEWNONO 학습 홈</a><a href="${href(file, path.join(root, 'questions.html'))}">학습 질문</a><a href="${href(file, path.join(root, 'verification.html'))}">검증 기록</a></header><div class="layout"><aside><details open><summary>전체 학습 목차</summary><ol>${nav}</ol></details></aside><main id="main" tabindex="-1"><p class="source">2026-10-03 구현 기준 · <a href="${esc(path.basename(file))}">이 문서의 Markdown 원본</a> · 외부 공식 자료는 온라인 참고 링크입니다.</p><nav class="toc" aria-label="이 문서 목차"><details><summary>이 문서에서 배우는 것</summary><ol>${toc}</ol></details></nav><article>${body}</article><nav class="pager" aria-label="이전 다음 문서">${pager}</nav></main></div><footer>Markdown을 수정한 뒤 build-html.mjs로 다시 생성합니다. 본문·그림·탐색은 로컬 파일로 작동합니다. 코드/원본 링크는 저장소 전체가 있을 때 열립니다.</footer></body></html>\n`
  fs.writeFileSync(htmlPath(file), html)
}
// README.html is the exact counterpart; index.html is a convenient duplicate entry point.
fs.copyFileSync(htmlPath(home), path.join(root, 'index.html'))
console.log(`Generated ${ordered.length} Markdown counterparts and index.html`)
