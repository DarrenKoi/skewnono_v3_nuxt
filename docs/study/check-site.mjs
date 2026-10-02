// Read-only, dependency-free checks of every Markdown/HTML counterpart and local navigation.
import fs from 'node:fs'
import path from 'node:path'
import crypto from 'node:crypto'
import assert from 'node:assert/strict'
import { fileURLToPath } from 'node:url'
const root = path.dirname(fileURLToPath(import.meta.url))
const walk = dir => fs.readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)])
const files = walk(root)
const digest = s => crypto.createHash('sha256').update(s).digest('hex')
const decode = s => s.replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&')
const errors = []
let counterparts = 0, links = 0, fences = 0
for (const md of files.filter(f => f.endsWith('.md'))) {
  const htmlFile = md.replace(/\.md$/, '.html')
  if (!fs.existsSync(htmlFile)) { errors.push(`Missing counterpart: ${htmlFile}`); continue }
  const source = fs.readFileSync(md, 'utf8')
  const html = fs.readFileSync(htmlFile, 'utf8')
  const sourceHash = html.match(/name="source-sha256" content="([a-f0-9]+)"/)?.[1]
  const bodyHash = html.match(/name="body-sha256" content="([a-f0-9]+)"/)?.[1]
  const article = html.match(/<article>([\s\S]*?)<\/article>/)?.[1]
  if (sourceHash !== digest(source)) errors.push(`Stale Markdown counterpart: ${md}`)
  if (!article || bodyHash !== digest(article)) errors.push(`Modified/missing HTML body: ${htmlFile}`)
  const renderedCode = [...html.matchAll(/<pre[^>]*><code[^>]*>([\s\S]*?)<\/code><\/pre>/g)].map(m => decode(m[1]))
  for (const m of source.matchAll(/^```[^\n]*\n([\s\S]*?)^```\s*$/gm)) {
    fences++
    if (!renderedCode.includes(m[1])) errors.push(`Code block changed: ${md}: ${m[1].slice(0, 50)}`)
  }
  counterparts++
}
for (const file of files.filter(f => f.endsWith('.html'))) {
  const html = fs.readFileSync(file, 'utf8')
  if (!html.includes('<html lang="ko">') || !html.includes('name="viewport"')) errors.push(`Language/viewport: ${file}`)
  if (/<script\b/i.test(html)) errors.push(`Unexpected script: ${file}`)
  for (const m of html.matchAll(/\b(href|src)="([^"]+)"/g)) {
    const url = decode(m[2])
    if (/^(https?:|mailto:|data:)/i.test(url)) {
      if (m[1] === 'src') errors.push(`Remote dependency: ${url}`)
      continue
    }
    links++
    const [name, fragment] = url.split('#')
    const target = name ? path.resolve(path.dirname(file), decodeURIComponent(name)) : file
    if (!fs.existsSync(target)) { errors.push(`Broken link: ${path.relative(root, file)} → ${url}`); continue }
    if (fragment && target.endsWith('.html')) {
      const targetHtml = target === file ? html : fs.readFileSync(target, 'utf8')
      const id = decodeURIComponent(fragment)
      if (!targetHtml.includes(`id="${id}"`)) errors.push(`Missing anchor: ${path.relative(root, file)} → ${url}`)
    }
  }
}
assert.equal(fs.readFileSync(path.join(root, 'index.html'), 'utf8'), fs.readFileSync(path.join(root, 'README.html'), 'utf8'), 'Home counterpart differs')
if (errors.length) {
  console.error(errors.join('\n'))
  process.exitCode = 1
} else console.log(`PASS: ${counterparts} Markdown/HTML pairs, ${fences} exact code blocks, ${links} local links/anchors; no scripts or remote media`)
