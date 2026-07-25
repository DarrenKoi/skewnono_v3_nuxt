// Pure-logic tests for apiPath. Run: node --test app/utils/apiPath.test.ts
//
// joinApiPath is the seam that makes "switch phases by configuration only"
// work: every $fetch in app/composables goes through it, joining
// runtimeConfig.public.apiBase (NUXT_PUBLIC_API_BASE, default '/api') to a
// feature path. A defect here breaks every API call in all three phases, so
// the three real base shapes are pinned explicitly:
//   Phase 1/2  '/api'                          (Nitro dev proxy → Flask)
//   Phase 3    '/api'                          (Flask serves the SPA itself)
//   override   'http://localhost:5000/api'     (absolute NUXT_PUBLIC_API_BASE)
// An `undefined` base is deliberately untested: the parameter is `string`, the
// runtimeConfig default is '/api', and reaching it would need a cast that
// asserts the very thing the test claims to check. '' is the reachable
// degenerate case and is covered below.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { joinApiPath } from './apiPath.ts'

test('every base × path slash combination joins with exactly one separator', () => {
  // The whole job of the function: whichever side carries the slash — both,
  // one, or neither — the seam is a single '/'.
  for (const base of ['/api', '/api/']) {
    for (const path of ['/health/services', 'health/services']) {
      assert.equal(joinApiPath(base, path), '/api/health/services')
    }
  }
})

test('joins an absolute base, keeping scheme, host and port intact', () => {
  assert.equal(
    joinApiPath('http://localhost:5000/api', '/health/services'),
    'http://localhost:5000/api/health/services'
  )
  assert.equal(
    joinApiPath('http://sknn.skhynix.com/api', '/announcements'),
    'http://sknn.skhynix.com/api/announcements'
  )
  // The trailing-slash rule applies to an absolute base too.
  assert.equal(joinApiPath('http://localhost:5000/api/', 'x'), 'http://localhost:5000/api/x')
})

test('an empty base yields a root-relative path', () => {
  assert.equal(joinApiPath('', '/health/services'), '/health/services')
  assert.equal(joinApiPath('', 'health/services'), '/health/services')
})

test('a bare slash base does not produce a doubled slash', () => {
  // '/' + '/x' would be '//x', which the browser reads as protocol-relative
  // (host 'x') — the one join mistake that would silently leave the origin.
  assert.equal(joinApiPath('/', '/x'), '/x')
})

test('the join stays under the base, which is what makes the phase switch work', () => {
  // Phase 1/2 route /api/* through the Nitro devProxy mount; Phase 3 has Flask
  // serving the SPA and answering the same prefix. Either way the only thing
  // that moves between phases is the base, so every result must remain a child
  // of it — a normalisation that dropped the prefix would bypass the proxy in
  // dev and 404 against the SPA's static routes in production.
  const path = '/cdsem/recipe-search/recipes'
  const cases: [string, string][] = [
    ['/api', '/api'],
    ['/api/', '/api'],
    ['http://localhost:5000/api', 'http://localhost:5000/api']
  ]
  for (const [base, prefix] of cases) {
    const url = joinApiPath(base, path)
    assert.equal(url, `${prefix}${path}`)
  }
})

test('nested feature paths keep every segment', () => {
  // The tool-type-slugged shape used by recipe-search / fail-issue composables.
  assert.equal(
    joinApiPath('/api', '/cdsem/recipe-search/recipes'),
    '/api/cdsem/recipe-search/recipes'
  )
  assert.equal(
    joinApiPath('/api', '/cdsem/device-statistics/recipe-params'),
    '/api/cdsem/device-statistics/recipe-params'
  )
})

test('a query string on the path is passed through untouched', () => {
  // Composables normally hand queries to $fetch's `query` option, but a path
  // carrying its own query must not be re-encoded or split.
  assert.equal(joinApiPath('/api', '/msr-file?msr=A1&seq=2'), '/api/msr-file?msr=A1&seq=2')
  assert.equal(joinApiPath('/api/', 'msr-file?msr=A1'), '/api/msr-file?msr=A1')
})

test('path segments are not encoded — callers own encoding', () => {
  assert.equal(joinApiPath('/api', '/account/api-tokens/tok 1'), '/api/account/api-tokens/tok 1')
})

test('the path argument is always treated as relative, never as a URL', () => {
  // Pinned so the "stays under the base" guarantee above is unconditional: an
  // absolute-looking path is appended, not honoured, so no caller can escape
  // the configured base by passing one. Callers must pass feature paths only.
  assert.equal(joinApiPath('/api', 'http://evil.example/x'), '/api/http://evil.example/x')
  assert.equal(joinApiPath('/api', '//evil.example/x'), '/api//evil.example/x')
})
