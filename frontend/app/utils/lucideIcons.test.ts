import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'

// nuxt.config sets icon.fallbackToApi: false, so a lucide name the installed set
// lacks renders blank with no error (list-search did, 2026-09-30). Names built
// at runtime (`i-lucide-${x}`) escape this scan; none exist today.
const set = JSON.parse(readFileSync('node_modules/@iconify-json/lucide/icons.json', 'utf8'))
const known = new Set([...Object.keys(set.icons), ...Object.keys(set.aliases ?? {})])

const sources = (dir: string): string[] => readdirSync(dir, { withFileTypes: true }).flatMap(entry =>
  entry.isDirectory() ? sources(join(dir, entry.name)) : /\.(vue|ts)$/.test(entry.name) ? [join(dir, entry.name)] : [])

test('every i-lucide-* icon the app names exists in the installed lucide set', () => {
  const missing = sources('app').flatMap(file =>
    [...readFileSync(file, 'utf8').matchAll(/i-lucide-([a-z0-9-]+)/g)]
      .map(match => match[1]!).filter(name => !known.has(name)).map(name => `${file}: ${name}`))
  assert.deepEqual(missing, [])
})
