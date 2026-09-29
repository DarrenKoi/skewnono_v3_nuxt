import { test } from 'node:test'
import assert from 'node:assert/strict'
import { escapeHtml } from './html.ts'

test('escapes all five characters, so the result is safe inside an attribute too', () => {
  assert.equal(escapeHtml(`<a href="x" title='y'>&</a>`), '&lt;a href=&quot;x&quot; title=&#39;y&#39;&gt;&amp;&lt;/a&gt;')
})
