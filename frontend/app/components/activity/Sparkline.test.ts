import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { compileTemplate, parse } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'
import { createSSRApp } from 'vue'
import * as Vue from 'vue'

// Only the TEMPLATE is compiled, and the state it reads is handed in as plain
// data. That is what keeps this test runnable under `node --test`: the script
// block pulls in ECharts and Nuxt auto-imports, neither of which survives
// outside a browser/Nuxt context. So this covers the HTML the component
// arranges around the canvas — the chart itself is only verifiable in a browser.
const renderSparkline = async (data: Record<string, unknown>) => {
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
  return renderToString(createSSRApp({ data: () => data, render }))
}

test('renders the total above the chart and only dates below it', async () => {
  const html = await renderSparkline({
    hasData: true,
    firstLabel: '07. 01.',
    totalLabel: '합계 10',
    lastLabel: '07. 30.'
  })

  const totalIndex = html.indexOf('합계 10')
  const hostIndex = html.indexOf('data-testid="sparkline-canvas"')
  const firstDateIndex = html.indexOf('07. 01.')
  const lastDateIndex = html.indexOf('07. 30.')

  assert.ok(hostIndex > -1, 'the chart host must render')
  assert.ok(totalIndex < hostIndex, 'the total must render above the chart')
  assert.ok(
    hostIndex < firstDateIndex && firstDateIndex < lastDateIndex,
    'only the start and end dates must render below the chart'
  )
})

test('renders the empty state instead of a chart host', async () => {
  const html = await renderSparkline({
    hasData: false,
    firstLabel: '',
    totalLabel: '',
    lastLabel: ''
  })

  assert.ok(html.includes('30일간 활동이 없습니다.'))
  assert.equal(
    html.includes('data-testid="sparkline-canvas"'),
    false,
    'no chart host means no ECharts instance for an inactive user'
  )
})
