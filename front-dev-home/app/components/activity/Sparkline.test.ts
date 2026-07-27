import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { compileTemplate, parse } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import * as Vue from 'vue'

test('renders the total above the bars and only dates below them', async () => {
  const filename = fileURLToPath(new URL('./Sparkline.vue', import.meta.url))
  const { descriptor } = parse(readFileSync(filename, 'utf8'), { filename })
  assert.ok(descriptor.template)

  const compiled = compileTemplate({
    source: descriptor.template.content,
    filename,
    id: 'activity-sparkline-test',
    compilerOptions: { mode: 'function' }
  })
  assert.deepEqual(compiled.errors, [])

  const render = new Function('Vue', compiled.code)(Vue)
  const html = await renderToString(createSSRApp({
    data: () => ({
      hasData: true,
      width: 300,
      height: 60,
      gradientId: 'test-gradient',
      gradientStops: { start: '#38bdf8', end: '#8b5cf6' },
      bars: [{ x: 4, y: 4, h: 52 }],
      barWidth: 8,
      firstLabel: '07.01',
      totalLabel: '합계 10',
      lastLabel: '07.30'
    }),
    render
  }))

  const totalIndex = html.indexOf('합계 10')
  const svgStartIndex = html.indexOf('<svg')
  const svgEndIndex = html.indexOf('</svg>')
  const firstDateIndex = html.indexOf('07.01')
  const lastDateIndex = html.indexOf('07.30')

  assert.ok(totalIndex < svgStartIndex, 'the total must render above the bars')
  assert.ok(
    svgEndIndex < firstDateIndex && firstDateIndex < lastDateIndex,
    'only the start and end dates must render below the bars'
  )
})
