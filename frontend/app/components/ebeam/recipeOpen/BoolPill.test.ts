import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import { renderToString } from 'vue/server-renderer'
import {
  computed,
  createElementBlock,
  createSSRApp,
  defineComponent,
  h,
  normalizeClass,
  openBlock,
  toDisplayString,
  unref,
  type Component
} from 'vue'

const loadBoolPill = (): Component => {
  const filename = new URL('./BoolPill.vue', import.meta.url)
  const { descriptor } = parse(readFileSync(filename, 'utf8'), {
    filename: filename.pathname
  })
  const source = compileScript(descriptor, {
    id: 'recipe-open-bool-pill-test',
    inlineTemplate: true
  }).content
    .replace(/^import .*$/gm, '')
    .replace('export default', 'return')
    .replaceAll(': any', '')

  const factory = Function(
    '_defineComponent',
    'computed',
    '_unref',
    '_toDisplayString',
    '_normalizeClass',
    '_openBlock',
    '_createElementBlock',
    source
  )

  return factory(
    defineComponent,
    computed,
    unref,
    toDisplayString,
    normalizeClass,
    openBlock,
    createElementBlock
  ) as Component
}

test('a missing boolean renders as unknown without a Vue prop warning', async () => {
  const warnings: string[] = []
  const app = createSSRApp({
    render: () => h(loadBoolPill(), { value: null, okWhen: false })
  })
  app.config.warnHandler = message => warnings.push(message)

  const html = await renderToString(app)

  assert.equal(
    warnings.some(message => message.includes('type check failed for prop')),
    false
  )
  assert.match(html, />—<\/span>$/)
})
