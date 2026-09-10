import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  MAX_REMEMBERED_VARIANTS,
  normalizeVariantMemory,
  rememberVariant,
  rememberedVariantIndex,
  resolveVariantMemoryRecipe,
  variantMemoryKey
} from './variantMemory.ts'
import { imageVariantLabels } from '../imageKind.ts'

// ── variantMemoryKey ─────────────────────────────────────────────────────────

test('key scopes the memory to recipe AND parameter', () => {
  assert.notEqual(
    variantMemoryKey('R000_GATE', 'CD_BOTTOM'),
    variantMemoryKey('R001_FIN', 'CD_BOTTOM')
  )
  assert.notEqual(
    variantMemoryKey('R000_GATE', 'CD_BOTTOM'),
    variantMemoryKey('R000_GATE', 'CD_TOP')
  )
})

test('key keeps the valid unnamed parameter distinct from an unresolved parameter', () => {
  assert.equal(variantMemoryKey(null, 'CD_BOTTOM'), null)
  assert.notEqual(variantMemoryKey('R000_GATE', ''), null)
  assert.notEqual(
    variantMemoryKey('R000_GATE', ''),
    variantMemoryKey('R000_GATE', 'CD_BOTTOM')
  )
  assert.equal(variantMemoryKey('R000_GATE', undefined), null)
  assert.equal(variantMemoryKey(undefined, undefined), null)
})

test('rowless focus uses the recipe carried by the matching MSR file', () => {
  assert.equal(resolveVariantMemoryRecipe('MSR-2', {
    msr: 'MSR-2',
    exe_detail_info: { recipe_name: 'R_FILE' }
  }, null), 'R_FILE')
})

test('a stale MSR file cannot override the current history-row recipe', () => {
  assert.equal(resolveVariantMemoryRecipe('MSR-2', {
    msr: 'MSR-1',
    exe_detail_info: { recipe_name: 'R_STALE' }
  }, 'R_ROW'), 'R_ROW')
})

test('key does not collide across a boundary that punctuation could blur', () => {
  // A printable separator would make ('A', 'B_C') and ('A_B', 'C') the same
  // bucket, cross-contaminating two parameters. Real recipe and parameter
  // names are printable, so a control-character separator has no such pair.
  for (const punct of ['_', '-', '|', '.', ':']) {
    assert.notEqual(
      variantMemoryKey('A', `B${punct}C`),
      variantMemoryKey(`A${punct}B`, 'C')
    )
  }
})

// ── rememberedVariantIndex ───────────────────────────────────────────────────

const HV = ['S04_M0004-01MP-U.jpeg', 'S04_M0004-01MP-T.jpeg', 'S04_M0004-01MP-M.jpeg', 'S04_M0004-01MP-L.jpeg']

test('a remembered suffix resolves to its position, not to a stored index', () => {
  assert.equal(rememberedVariantIndex(HV, 'M'), 2)
  assert.equal(rememberedVariantIndex(HV, 'U'), 0)
})

test('the SAME suffix resolves to a DIFFERENT index on a point missing a variant', () => {
  // This is the whole reason a label is stored instead of an index: the -T
  // shot is absent here, so index 2 is 'L', not the remembered 'M'.
  const short = ['S05_M0009-01MP-U.jpeg', 'S05_M0009-01MP-M.jpeg', 'S05_M0009-01MP-L.jpeg']
  assert.equal(rememberedVariantIndex(short, 'M'), 1)
  assert.equal(rememberedVariantIndex(HV, 'M'), 2)
})

test('a suffix this point does not carry falls back to the first image', () => {
  assert.equal(rememberedVariantIndex(['a-U.jpeg', 'a-L.jpeg'], 'T'), 0)
})

test('no memory, empty memory and an empty list all resolve to the first image', () => {
  assert.equal(rememberedVariantIndex(HV, null), 0)
  assert.equal(rememberedVariantIndex(HV, undefined), 0)
  assert.equal(rememberedVariantIndex(HV, ''), 0)
  assert.equal(rememberedVariantIndex([], 'M'), 0)
})

test('CD-SEM single-image points are unaffected by any remembered suffix', () => {
  assert.equal(rememberedVariantIndex(['S01_M0001-01MP.jpeg'], 'M'), 0)
})

test('a suffix-less name matches by its 1-based positional label', () => {
  // imageVariantLabel falls back to the position when the stem has no -X
  // suffix, so the memory still round-trips for those points.
  const plain = ['first.jpeg', 'second.jpeg', 'third.jpeg']
  assert.equal(rememberedVariantIndex(plain, '2'), 1)
})

// One sub-position under two extensions (JPEG preview + TIFF original,
// user-confirmed 2026-08-24). Per-name labels collide here (U, U, L, L) —
// the regression this block pins is that resolving a stored label always
// answered the FIRST file, so the second chip of each pair could be clicked
// but never stayed selected.
const CROSS_EXT = ['S04_M0004-01MP-U.jpeg', 'S04_M0004-01MP-U.TIF', 'S04_M0004-01MP-L.jpeg', 'S04_M0004-01MP-L.TIF']

test('every chip of a cross-extension point round-trips to itself', () => {
  for (let i = 0; i < CROSS_EXT.length; i++) {
    const memory = rememberVariant({}, 'k', imageVariantLabels(CROSS_EXT)[i]!)
    assert.equal(rememberedVariantIndex(CROSS_EXT, memory['k']), i)
  }
})

test('a pre-disambiguation stored suffix still lands on that sub-position', () => {
  // Memories persisted before labels carried rendition tags hold bare "U".
  assert.equal(rememberedVariantIndex(CROSS_EXT, 'U'), 0)
  assert.equal(rememberedVariantIndex(CROSS_EXT, 'L'), 2)
})

test('a rendition-tagged memory falls back to the sub-position on a single-rendition point', () => {
  // Picked U·TIF on a two-rendition point; this point lists U once. The pick
  // means "depth U", so it must find that file rather than reset to the first.
  assert.equal(rememberedVariantIndex(['a-U.jpeg', 'a-L.jpeg'], 'U·TIF'), 0)
  assert.equal(rememberedVariantIndex(['a-U.jpeg', 'a-L.jpeg'], 'L·TIF'), 1)
})

// ── rememberVariant ──────────────────────────────────────────────────────────

test('remembering does not mutate the previous map — the persisted ref needs a new object', () => {
  const before = { a: 'U' }
  const after = rememberVariant(before, 'b', 'L')
  assert.deepEqual(before, { a: 'U' })
  assert.equal(after.b, 'L')
  assert.equal(after.a, 'U')
})

test('re-picking overwrites that key and leaves the others alone', () => {
  const memory = rememberVariant(rememberVariant({}, 'a', 'U'), 'a', 'L')
  assert.deepEqual(memory, { a: 'L' })
})

test('a null key is a no-op — an unresolved recipe must not write a shared bucket', () => {
  const before = { a: 'U' }
  assert.equal(rememberVariant(before, null, 'L'), before)
})

test('the map is capped, evicting the least recently picked key', () => {
  let memory: Record<string, string> = {}
  for (let i = 0; i < MAX_REMEMBERED_VARIANTS + 5; i++) {
    memory = rememberVariant(memory, `key-${i}`, 'U')
  }
  const keys = Object.keys(memory)
  assert.equal(keys.length, MAX_REMEMBERED_VARIANTS)
  assert.equal(keys.includes('key-0'), false)
  assert.equal(keys.at(-1), `key-${MAX_REMEMBERED_VARIANTS + 4}`)
})

test('re-picking an existing key refreshes its recency instead of adding a slot', () => {
  const memory = rememberVariant(rememberVariant(rememberVariant({}, 'a', 'U'), 'b', 'T'), 'a', 'L')
  assert.deepEqual(Object.keys(memory), ['b', 'a'])
})

// ── normalizeVariantMemory ───────────────────────────────────────────────────

test('normalize keeps string→string pairs and drops everything else', () => {
  assert.deepEqual(
    normalizeVariantMemory({ a: 'U', b: 3, c: null, d: 'L', e: { f: 'M' } }),
    { a: 'U', d: 'L' }
  )
})

test('normalize rejects a non-object payload rather than throwing', () => {
  assert.deepEqual(normalizeVariantMemory(null), {})
  assert.deepEqual(normalizeVariantMemory('U'), {})
  assert.deepEqual(normalizeVariantMemory([1, 2]), {})
})

test('normalize caps an oversized stored payload, keeping the most recent tail', () => {
  const oversized: Record<string, string> = {}
  for (let i = 0; i < MAX_REMEMBERED_VARIANTS + 3; i++) oversized[`key-${i}`] = 'U'
  const normalized = normalizeVariantMemory(oversized)
  assert.equal(Object.keys(normalized).length, MAX_REMEMBERED_VARIANTS)
  assert.equal('key-0' in normalized, false)
  assert.equal(`key-${MAX_REMEMBERED_VARIANTS + 2}` in normalized, true)
})
