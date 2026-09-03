import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import { compileScript, parse } from '@vue/compiler-sfc'
import { renderToString } from '@vue/server-renderer'
import {
  computed,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createSSRApp,
  defineComponent,
  Fragment,
  h,
  openBlock,
  unref,
  type Component
} from 'vue'

const loadCondMarks = (): Component => {
  const filename = new URL('./CondMarks.vue', import.meta.url)
  const { descriptor } = parse(readFileSync(filename, 'utf8'), { filename: filename.pathname })
  const source = compileScript(descriptor, {
    id: 'recipe-open-cond-marks-test',
    inlineTemplate: true
  }).content
    .replace(/^import .*$/gm, '')
    .replace('export default', 'return')
    .replaceAll(': any', '')

  const factory = Function(
    '_defineComponent', '_createCommentVNode', '_unref', '_openBlock',
    '_createElementBlock', '_createElementVNode', '_Fragment', 'computed',
    source
  )
  return factory(
    defineComponent, createCommentVNode, unref, openBlock,
    createElementBlock, createElementVNode, Fragment, computed
  ) as Component
}

test('the box mark renders as its center point, not an outline', async () => {
  const marks = {
    pixel: [512, 512],
    box: [0.2, 0.3, 0.6, 0.7],
    crosshair: null
  }
  const html = await renderToString(createSSRApp({
    render: () => h(loadCondMarks(), { marks })
  }))

  assert.doesNotMatch(html, /<rect/)
  assert.match(html, /<circle cx="204.8" cy="256" r="3.2"/)
})
