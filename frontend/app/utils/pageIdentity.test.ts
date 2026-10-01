import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { resolvePageIdentity, buildPageViewPath, createPageViewTracker, pageFamily, pageViewEndpoint } from './pageIdentity.ts'

// Contract test: frontend identity must partition paths the same way the backend
// does — two paths share an identity IFF page_to_feature gives them the same slug
// AND page_to_family gives them the same tool family.
const loadContract = () => {
  const __dir = dirname(fileURLToPath(import.meta.url))
  const fixture = readFileSync(join(__dir, '__fixtures__/pageIdentityContract.json'), 'utf-8')
  return JSON.parse(fixture) as Array<{
    path: string
    query: Record<string, unknown>
    slug: string | null
    family: string | null
    finerThanSlug?: boolean
    comment?: string
  }>
}

const contract = loadContract()

test('a fab switch on the same page is the same identity', () => {
  const a = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const b = resolvePageIdentity('/ebeam/cd-sem/M16B/storage', {})

  assert.equal(a, b)
})

test('a filter query change is the same identity', () => {
  const a = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const b = resolvePageIdentity('/ebeam/cd-sem/M14/storage', { ppid: 'X1' })

  assert.equal(a, b)
})

test('different pages are different identities', () => {
  assert.notEqual(
    resolvePageIdentity('/ebeam/cd-sem/M14/storage', {}),
    resolvePageIdentity('/ebeam/cd-sem/M14/hardware', {})
  )
})

test('recipe-status tabs are three different identities', () => {
  const tat = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })
  const align = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'align' })
  const meas = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'meas' })

  // Three distinct identities: product ranks them separately even though align and meas
  // share the same backend slug (fail_issue)
  assert.equal(new Set([tat, align, meas]).size, 3)
})

test('recipe-status without a tab is unresolved', () => {
  // RecipeStatusView writes ?tab= back on mount; firing before that would
  // count one visit twice.
  assert.equal(resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', {}), null)
})

test('an array-valued tab takes its first entry', () => {
  // Vue router surfaces a repeated query key as an array.
  assert.equal(
    resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: ['tat', 'align'] }),
    resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })
  )
})

test('the reported path carries the tab and nothing else', () => {
  assert.equal(
    buildPageViewPath('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat', ppid: 'X1' }),
    '/ebeam/cd-sem/M14/recipe-status?tab=tat'
  )
  assert.equal(
    buildPageViewPath('/ebeam/cd-sem/M14/storage', { ppid: 'X1' }),
    '/ebeam/cd-sem/M14/storage'
  )
})

test('recipe-search sub-pages (compare, open, lateral) are the same identity', () => {
  const base = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search', {})
  const compare = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/compare', {})
  const open = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/open', {})
  const lateral = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/lateral', {})

  assert.equal(base, compare)
  assert.equal(base, open)
  assert.equal(base, lateral)
})

test('recipe-search and recipe-search/meas-hist are different identities', () => {
  const search = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search', {})
  const measHist = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/meas-hist', {})

  assert.notEqual(search, measHist)
})

test('afm sub-paths with different files are the same identity', () => {
  const map608 = resolvePageIdentity('/afm/map608/a.tif', {})
  const mapc01 = resolvePageIdentity('/afm/mapc01/b.tif', {})

  assert.equal(map608, mapc01)
})

test('device-statistics and device-statistics/comparison are the same identity', () => {
  const base = resolvePageIdentity('/ebeam/cd-sem/device-statistics', {})
  const comparison = resolvePageIdentity('/ebeam/cd-sem/device-statistics/comparison', {})

  assert.equal(base, comparison)
})

test('storage and hardware remain different identities', () => {
  const storage = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})
  const hardware = resolvePageIdentity('/ebeam/cd-sem/M14/hardware', {})

  assert.notEqual(storage, hardware)
})

test('fab switch invariance holds on collapsed pages', () => {
  const m14search = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-search/compare', {})
  const m16search = resolvePageIdentity('/ebeam/cd-sem/M16B/recipe-search/compare', {})
  const m14stats = resolvePageIdentity('/ebeam/cd-sem/M14/device-statistics/comparison', {})
  const m16stats = resolvePageIdentity('/ebeam/cd-sem/M16B/device-statistics/comparison', {})

  assert.equal(m14search, m16search)
  assert.equal(m14stats, m16stats)
})

test('the same page under another tool family is a different identity', () => {
  // The slug is shared (both are `storage`), but the row is logged with its
  // tool family, and the families are growing their own UI. Collapsing them
  // here made a CD-SEM → HV-SEM move look like a filter change, so the second
  // page open sent no beacon and the family it belonged to was never counted.
  assert.notEqual(
    resolvePageIdentity('/ebeam/cd-sem/M14/storage', {}),
    resolvePageIdentity('/ebeam/hv-sem/M14/storage', {})
  )
  assert.notEqual(
    resolvePageIdentity('/ebeam/cd-sem/device-statistics', {}),
    resolvePageIdentity('/ebeam/hv-sem/device-statistics', {})
  )
})

test('skewvoir is the same identity for both index and analysis', () => {
  const index = resolvePageIdentity('/ebeam/cd-sem/skewvoir', {})
  const analysis = resolvePageIdentity('/ebeam/cd-sem/skewvoir/analysis', {})

  assert.equal(index, analysis)
})

test('skewvoir is one identity per tool family', () => {
  const cdsemSkewvoir = resolvePageIdentity('/ebeam/cd-sem/skewvoir', {})
  const hvsemSkewvoir = resolvePageIdentity('/ebeam/hv-sem/skewvoir', {})

  assert.notEqual(cdsemSkewvoir, hvsemSkewvoir)
})

test('the fab hub is one identity per tool family', () => {
  // /ebeam/<tool> and /ebeam/<tool>/<fab> both land on [fab]/index.vue, which
  // renders EbeamToolInventoryView (장비 상태). Within a family the fab does not
  // matter; across families it is the backend's one tool_inventory slug under
  // four different tool families.
  assert.equal(
    resolvePageIdentity('/ebeam/cd-sem', {}),
    resolvePageIdentity('/ebeam/cd-sem/M14', {})
  )
  const identities = [
    resolvePageIdentity('/ebeam/cd-sem/M14', {}),
    resolvePageIdentity('/ebeam/hv-sem/R3', {}),
    resolvePageIdentity('/ebeam/provision/R3', {}),
    resolvePageIdentity('/ebeam/veritysem/M14', {})
  ]

  assert.equal(new Set(identities).size, 4)
  // All four are still the synthesized inventory page — the marker the
  // landing rule keys on.
  for (const identity of identities) assert.ok(identity?.endsWith('#tool-inventory'), String(identity))
})

test('the fab list is not part of a page identity', () => {
  // buildFabSegment joins the selection, so a two-fab session routes through
  // /ebeam/<tool>/m14,r3/… Matching a single fab code only, the whole list
  // stayed in the canonical path, no rule matched it, and every multi-fab page
  // fell back to `landing` — one identity for the entire tool. The beacon then
  // fired for the first page of the session and deduped every page after it.
  const storage = resolvePageIdentity('/ebeam/cd-sem/M14/storage', {})

  for (const path of [
    '/ebeam/cd-sem/m14,r3/storage',
    '/ebeam/cd-sem/M14,R3/storage',
    '/ebeam/cd-sem/r3,m16b,m11/storage'
  ]) {
    assert.equal(resolvePageIdentity(path, {}), storage, path)
  }

  // Distinct pages under one multi-fab segment must stay distinct — this is
  // the half that was losing page opens.
  const identities = new Set([
    resolvePageIdentity('/ebeam/cd-sem/m14,r3/storage', {}),
    resolvePageIdentity('/ebeam/cd-sem/m14,r3/hardware', {}),
    resolvePageIdentity('/ebeam/cd-sem/m14,r3/live-alarm', {}),
    resolvePageIdentity('/ebeam/cd-sem/m14,r3', {})
  ])

  assert.equal(identities.size, 4)
})

test('a multi-fab recipe-status keeps the tab as its only distinction', () => {
  // The tab branch keys on the canonical path, so an unstripped fab list gave
  // each fab combination its own identity for the same tab — splitting one
  // feature into as many series as there are ways to pick fabs.
  const single = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })

  assert.equal(
    resolvePageIdentity('/ebeam/cd-sem/m14,r3/recipe-status', { tab: 'tat' }),
    single
  )
  assert.notEqual(
    resolvePageIdentity('/ebeam/cd-sem/m14,r3/recipe-status', { tab: 'align' }),
    single
  )
})

test('a malformed fab list is not swallowed as a fab', () => {
  // A trailing comma or an unknown code must fall through (unresolved) rather
  // than being stripped, which would misfile it as the page that happens to
  // follow it.
  assert.equal(resolvePageIdentity('/ebeam/cd-sem/m14,/storage', {}), null)
  assert.equal(resolvePageIdentity('/ebeam/cd-sem/m14,x9/storage', {}), null)
})

test('an unmapped e-beam page has no identity, so no beacon fires', () => {
  // The old fallback grouped these by tool, which is how "CD-SEM" kept turning
  // up in the ranking: a tool family is not a page. Nor may it be counted as
  // 장비 상태 — a confident wrong answer instead of no answer.
  for (const path of [
    '/ebeam/cd-sem/M14/unmapped-page',
    '/ebeam/hv-sem/R3/unmapped-page',
    '/ebeam/provision/M14/unmapped-page',
    '/ebeam/veritysem/M14/unmapped-page',
    '/ebeam'
  ]) {
    assert.equal(resolvePageIdentity(path, {}), null, path)
  }
})

test('a fabless page shape shares the fab shape identity', () => {
  assert.equal(
    resolvePageIdentity('/ebeam/cd-sem/hardware', {}),
    resolvePageIdentity('/ebeam/cd-sem/M14/hardware', {})
  )
})

test('legacy recipe-tat and fail-issue routes are their own identities', () => {
  const tat = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-tat', {})
  const fail = resolvePageIdentity('/ebeam/cd-sem/M14/fail-issue', {})
  const statusTat = resolvePageIdentity('/ebeam/cd-sem/M14/recipe-status', { tab: 'tat' })

  assert.notEqual(tat, fail)
  assert.notEqual(tat, statusTat)
})

test('ops pages have no rankable identity', () => {
  assert.equal(resolvePageIdentity('/admin/logs', {}), null)
  assert.equal(resolvePageIdentity('/activity', {}), null)
})

test('the home hub has no rankable identity', () => {
  // Not an ops page — product surface excluded for a different reason: it is
  // a waypoint, and DAU already counts how many people passed through.
  assert.equal(resolvePageIdentity('/', {}), null)
})

// Which navigations in a sequence the beacon reports, in order.
const reported = (...paths: string[]) => {
  const track = createPageViewTracker()
  return paths.map(path => track(path, {}))
}

test('a fab switch on the same page is one page open, not two', () => {
  assert.deepEqual(
    reported('/ebeam/cd-sem/M14/storage', '/ebeam/cd-sem/M16B/storage'),
    [true, false]
  )
})

test('landing on 장비 상태 from home is not a page open', () => {
  // Home's tool cards link to /ebeam/<tool>/<fab>, so every "pick a tool" trip
  // passes through 장비 상태 on the way to wherever the user was going. Counting
  // it would rank "entered e-beam", which DAU already reports — the same reason
  // / itself is unranked. Switching fab on arrival changes nothing.
  assert.deepEqual(
    reported('/', '/ebeam/cd-sem/M14', '/ebeam/cd-sem/R3', '/ebeam/cd-sem/R3/storage'),
    [false, false, false, true]
  )
})

test('choosing 장비 상태 from another page is a page open', () => {
  // The 장비 상태 tab clicked from a feature page is intent, and it is the only
  // way the page earns a count. A rule that dropped the page outright would
  // still pass the landing test above; this is what stops it.
  assert.deepEqual(
    reported('/', '/ebeam/cd-sem/M14', '/ebeam/cd-sem/M14/storage', '/ebeam/cd-sem/M14'),
    [false, false, true, true]
  )
})

test('a fresh load straight onto 장비 상태 is not a page open', () => {
  // A reload or a restored tab arrives with nothing before it — the same
  // waypoint as coming from home.
  assert.deepEqual(reported('/ebeam/hv-sem/R3'), [false])
  assert.deepEqual(reported('/ebeam/hv-sem/R3/storage'), [true])
})

test('moving to the same page of another family is a new page open', () => {
  assert.deepEqual(
    reported('/ebeam/cd-sem/M14/storage', '/ebeam/hv-sem/M14/storage', '/ebeam/hv-sem/R3/storage'),
    [true, true, false]
  )
})

test('switching family between two 장비 상태 landings is still a landing', () => {
  // Picking HV-SEM while standing on CD-SEM's 장비 상태 is the same act as
  // picking it from home: choosing a tool, not opening a page. Only a ranked
  // page before it makes 장비 상태 a choice.
  assert.deepEqual(
    reported('/', '/ebeam/cd-sem/M14', '/ebeam/hv-sem/M14', '/ebeam/hv-sem/M14/storage'),
    [false, false, false, true]
  )
  assert.deepEqual(
    reported('/ebeam/cd-sem/M14/storage', '/ebeam/hv-sem/M14'),
    [true, true]
  )
})

test('skewvoir does not share the msr-file identity', () => {
  // /msr-file, /msr-files and /msr-image are API paths with their own slugs;
  // fusing them onto /skewvoir would merge four distinct backend slugs.
  const skewvoir = resolvePageIdentity('/ebeam/cd-sem/skewvoir', {})

  assert.notEqual(skewvoir, resolvePageIdentity('/msr-file', {}))
  assert.notEqual(
    resolvePageIdentity('/msr-file', {}),
    resolvePageIdentity('/msr-files', {})
  )
})

test('contract: every page names the family the backend names', () => {
  // The frontend picks the beacon URL from this, and the backend rejects a
  // beacon whose URL disagrees with its page — so a drift here is not a
  // miscount, it is every page open of that family failing with a 400.
  for (const row of contract) {
    assert.equal(pageFamily(row.path), row.family, rowLabel(row))
  }
})

test('a page open is posted to its family’s beacon URL', () => {
  // The family travels in the URL because the log row's `path` is a field the
  // index already has; a separate field would have needed a mapping change.
  assert.equal(pageViewEndpoint('/ebeam/cd-sem/M14/storage'), '/page-view/cdsem')
  assert.equal(pageViewEndpoint('/ebeam/hv-sem/m14,r3/hardware'), '/page-view/hvsem')
  assert.equal(pageViewEndpoint('/ebeam/veritysem/M14'), '/page-view/veritysem')
  assert.equal(pageViewEndpoint('/afm/map608/a.tif'), '/page-view/afm')
  // No family, no segment: the endpoint every shared page has always used.
  assert.equal(pageViewEndpoint('/mag-pixel'), '/page-view')
  assert.equal(pageViewEndpoint('/chat'), '/page-view')
  assert.equal(pageViewEndpoint('/ebeam/unknown/M14/storage'), '/page-view')
})

// The ONE approved exception, enumerated so the fixture cannot quietly grow a fourth.
const APPROVED_FINER_ROWS = [
  '/ebeam/cd-sem/M14/recipe-status?tab=tat',
  '/ebeam/cd-sem/M14/recipe-status?tab=align',
  '/ebeam/cd-sem/M14/recipe-status?tab=meas'
]

const rowLabel = (row: { path: string, query: Record<string, unknown> }) => {
  const pairs = Object.entries(row.query ?? {}).map(
    ([key, value]) => `${key}=${Array.isArray(value) ? value[0] : value}`
  )
  return pairs.length ? `${row.path}?${pairs.join('&')}` : row.path
}

test('contract: every ranked page resolves to a non-null identity', () => {
  // A null identity means the beacon never fires — the page silently stops being
  // counted, which is the worst failure the governing rule exists to prevent.
  // Only rows the backend itself declines to rank (slug null: ops pages, and
  // recipe-status before its tab lands) may resolve to null.
  for (const row of contract) {
    if (row.slug === null) continue
    const identity = resolvePageIdentity(row.path, row.query)
    assert.notEqual(
      identity,
      null,
      `${rowLabel(row)} has slug "${row.slug}" but resolved to null — `
      + 'a real page open would go uncounted.'
    )
  }
})

test('contract: the finerThanSlug marker is exactly the three recipe-status tabs', () => {
  // Without this, future drift could be silenced by marking the failing row
  // instead of fixing it. A fourth marker must force a conversation.
  const marked = contract.filter(r => r.finerThanSlug).map(rowLabel).sort()

  assert.deepEqual(marked, [...APPROVED_FINER_ROWS].sort())
})

test('contract: identity partitions match backend (slug, family) partitions', () => {
  // Two paths must produce the same identity IFF the backend maps them to the same slug
  // AND the same tool family. A null slug is unresolved whatever its family.
  // Exception: finerThanSlug rows are intentional — they differ in identity despite
  // sharing a slug, as a product decision. This test ensures drift is caught mechanically.

  // Separate marked and unmarked rows
  const markedRows = contract.filter(r => r.finerThanSlug)
  const unmarkedRows = contract.filter(r => !r.finerThanSlug)

  // Build maps by (slug, family) for each group. The map keeps the name
  // "slug" below, but its keys are the pair — spelled `slug|family`.
  const slugToUnmarkedRows = new Map<string | null, typeof unmarkedRows>()
  for (const row of unmarkedRows) {
    const key = row.slug === null ? null : `${row.slug}|${row.family ?? ''}`
    if (!slugToUnmarkedRows.has(key)) {
      slugToUnmarkedRows.set(key, [])
    }
    slugToUnmarkedRows.get(key)!.push(row)
  }

  // For unmarked rows with the same slug, all must produce the same identity
  for (const [slug, rows] of slugToUnmarkedRows.entries()) {
    const identities = rows.map(row => resolvePageIdentity(row.path, row.query))

    // All identities must be equal (or all null for unresolved pages)
    const first = identities[0]
    for (let i = 1; i < identities.length; i++) {
      assert.equal(
        identities[i],
        first,
        `Unmarked rows with slug "${slug}" produced different identities: ${first} vs ${identities[i]}`
      )
    }
  }

  // Marked rows can have different identities but still share a slug—that's their point.
  // But they must NOT collide with unmarked rows.
  const unmarkedIdentities = new Set<string | null>()
  for (const row of unmarkedRows) {
    unmarkedIdentities.add(resolvePageIdentity(row.path, row.query))
  }

  for (const markedRow of markedRows) {
    const markedIdentity = resolvePageIdentity(markedRow.path, markedRow.query)
    assert.ok(
      !unmarkedIdentities.has(markedIdentity),
      `Marked row ${markedRow.path} produced identity ${markedIdentity} `
      + `that collides with an unmarked row. Marked rows must be enumerated, not left to chance.`
    )
  }

  // For any two different non-null unmarked slugs, rows must produce different identities
  const nonNullUnmarkedSlugs = Array.from(slugToUnmarkedRows.keys()).filter(
    (slug): slug is string => slug !== null
  )
  for (let i = 0; i < nonNullUnmarkedSlugs.length; i++) {
    for (let j = i + 1; j < nonNullUnmarkedSlugs.length; j++) {
      const slug1 = nonNullUnmarkedSlugs[i] as string
      const slug2 = nonNullUnmarkedSlugs[j] as string

      const rows1 = slugToUnmarkedRows.get(slug1) ?? []
      const rows2 = slugToUnmarkedRows.get(slug2) ?? []
      if (rows1.length === 0 || rows2.length === 0) continue

      const first1 = rows1[0]!
      const first2 = rows2[0]!
      const identity1 = resolvePageIdentity(first1.path, first1.query)
      const identity2 = resolvePageIdentity(first2.path, first2.query)

      assert.notEqual(
        identity1,
        identity2,
        `Different unmarked slugs "${slug1}" and "${slug2}" produced the same identity: ${identity1}`
      )
    }
  }

  // Null slug rows must produce null identity
  const nullRows = unmarkedRows.filter(r => r.slug === null)
  for (const row of nullRows) {
    const identity = resolvePageIdentity(row.path, row.query)
    assert.equal(
      identity,
      null,
      `Unresolved page ${row.path} produced identity ${identity} instead of null`
    )
  }
})
