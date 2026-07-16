import type { MeasHistResponse, MeasHistRow } from '~/composables/useMeasHistApi'
import type { MsrFileResponse, MsrParamSummary, MsrFileRow } from '~/composables/useMsrFileApi'
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { TimeSeriesPoint } from '~/components/ebeam/skewvoir/TimeSeriesChart.vue'
import { formatRecipeTimestamp } from '~/utils/recipeView'
import { peerVerdicts, combineVerdicts, DEFAULT_RANGE, DEFAULT_STDDEV, type CombinedVerdict, type MethodConfig } from '~/utils/anomaly'
import { overviewSites, type OverviewSites } from '~/utils/overview'
import { parseWaferGeometry, type WaferGeometry } from '~/utils/waferGeometry'
import { buildAnalysisManifest, extractSignature, type SignatureSource } from '~/utils/skewvoirAnalysis/compatibility'
import type { AnalysisManifest, ReferenceDescriptor } from '~/utils/skewvoirAnalysis/types'
import {
  buildHandoffs,
  hasSpatialCoordinates,
  hasSequenceData as hasSequenceEvidence,
  hasImageEvidence,
  type HandoffTarget
} from '~/utils/skewvoirAnalysis/handoffs'
import {
  featureRows as computeFeatureRows,
  featureRegistry as computeFeatureRegistry,
  type FeatureSource,
  type MsrFeatureRow,
  type FeatureDefinition
} from '~/utils/skewvoirAnalysis/features'

// Cap the multi-measurement trend so a high-volume recipe doesn't fan out into
// hundreds of MsrFile fetches; we take the most recent N around the selection.
const TREND_LIMIT = 30

// The analysis route's data layer. Given the URL-pinned selection (focus `msr`)
// and the curated comparison set (URL `msrs`), it resolves two shapes of data:
//   • focusFile  — the single MsrFile for the Dashboard (one measurement)
//   • trendPoints — mean ± min/max band across the curated set (Time-Series)
// The active parameter is the URL `mp`. The trend fetch is lazy (only on the
// Time-Series view) so the Dashboard never pays for the set fan-out.
export const useSkewvoirAnalysis = (ws: SkewvoirWorkspace) => {
  const { fetchMeasHist } = useMeasHistApi()
  const { fetchMsrFile, fetchMsrFiles } = useMsrFileApi()

  // Active scoring method + thresholds for trend anomaly verdicts. Range is the
  // authoritative default; stddev is a diagnostic lens. Shared view-state so the
  // Time-Series controls and this computation stay in sync (survives remounts).
  const anomalyCfg = useState<MethodConfig>('skewvoir-anomaly-cfg', () => ({
    method: 'range',
    range: { ...DEFAULT_RANGE },
    stddev: { ...DEFAULT_STDDEV }
  }))

  const histKey = `skewvoir-meas-hist:${ws.toolType}`

  // Shares the search landing's cached meas-hist payload (same key).
  const { data: hist } = useAsyncData<MeasHistResponse>(
    histKey,
    () => fetchMeasHist({ toolType: ws.toolType }),
    {
      default: () => ({ tool_type: ws.toolType, fab_name: null, recipe_name: null, total: 0, rows: [] }),
      getCachedData: (key, nuxtApp) => nuxtApp.payload.data[key] ?? nuxtApp.static.data[key]
    }
  )

  const rows = computed<MeasHistRow[]>(() => hist.value?.rows ?? [])
  // The URL-pinned focus msr, independent of whether meas_hist has a matching
  // row (a deep-link msr may not) — the reliable "which chip is active" key
  // for the focus-switcher chip strip.
  const focusMsr = computed<string | null>(() => ws.selection.value?.msr ?? null)
  const focusRow = computed<MeasHistRow | null>(() =>
    rows.value.find(r => r.msr === focusMsr.value) ?? null
  )
  // The focus measurement's fab (per-measurement, e.g. 'M11B') — for fab-scoped
  // links like the recipe 열어보기 page.
  const fab = computed<string>(() => focusRow.value?.fab_name ?? '')

  // --- Single measurement (Dashboard) ---
  const focusFile = ref<MsrFileResponse | null>(null)
  const focusPending = ref(false)
  // Focus load failure. When set, consumers show an error + retry rather than
  // keeping the PREVIOUS msr's data rendered as if it were the new focus.
  const focusError = ref<Error | null>(null)

  // Declared here (ahead of its populating watcher further down) purely so
  // loadFocus below — which is invoked immediately by a `watch(..., {
  // immediate: true })` a few lines later — can read it without tripping the
  // temporal-dead-zone: `setFiles` must already be initialized by the time
  // that first synchronous loadFocus call runs.
  const setFiles = ref<Map<string, MsrFileResponse>>(new Map())

  // Session cache for focus MsrFile responses, keyed by msr. Bounded at
  // TREND_LIMIT (30) with insertion-order eviction (oldest key dropped first),
  // so a chip strip switching among the curated set (also capped at
  // TREND_LIMIT) fits entirely without evicting anything mid-session. A
  // cache hit lets a chip switch back to a just-viewed msr render with 0
  // network requests. Module-scope Map (not a ref) — it's a resolution-order
  // optimization, not reactive UI state.
  const focusCache = new Map<string, MsrFileResponse>()

  const cacheFocusFile = (msr: string, file: MsrFileResponse) => {
    // Delete-then-set moves an existing key to the most-recently-inserted
    // position (Map iteration order), so re-touching a cached msr counts as
    // fresh recency rather than aging out first.
    focusCache.delete(msr)
    focusCache.set(msr, file)
    if (focusCache.size > TREND_LIMIT) {
      const oldest = focusCache.keys().next().value
      if (oldest !== undefined) focusCache.delete(oldest)
    }
  }

  // Key on the URL msr itself (not the meas-hist row): the backend resolves the
  // parent class_name/total_images on its own, so a deep/shared link still loads
  // even when the row isn't in the currently-loaded meas-hist list. When the row
  // IS known, pass its fields to skip that backend lookup.
  //
  // Resolution order: session cache → the curated set's already-fetched
  // `setFiles` → `fetchMsrFile` (the only network path). A chip switch to an
  // msr already resolved by either of the first two costs 0 requests.
  //
  // Stale-response guard: A→B→A genuinely races because fetchMsrFile has only
  // in-flight dedupe, no completed-response cache. We capture the requested msr
  // before the await and DISCARD the result if the URL focus has moved on. The
  // two synchronous cache-hit paths below are race-free (nothing to await) but
  // still only ASSIGN when the requested msr still matches the current
  // selection — populating focusCache happens unconditionally either way.
  const loadFocus = async (msr: string | undefined) => {
    if (!msr) {
      focusFile.value = null
      focusError.value = null
      return
    }
    const requestedMsr = msr

    const cached = focusCache.get(msr)
    if (cached) {
      cacheFocusFile(msr, cached) // touch recency
      if (ws.selection.value?.msr === requestedMsr) {
        focusFile.value = cached
        focusPending.value = false
        focusError.value = null
      }
      return
    }

    const fromSet = setFiles.value.get(msr)
    if (fromSet) {
      cacheFocusFile(msr, fromSet)
      if (ws.selection.value?.msr === requestedMsr) {
        focusFile.value = fromSet
        focusPending.value = false
        focusError.value = null
      }
      return
    }

    const row = focusRow.value
    focusPending.value = true
    focusError.value = null
    try {
      const res = await fetchMsrFile({
        msr,
        className: row?.class_name,
        totalImages: row?.total_images
      })
      cacheFocusFile(msr, res)
      if (ws.selection.value?.msr !== requestedMsr) return
      focusFile.value = res
    } catch (err) {
      if (ws.selection.value?.msr !== requestedMsr) return
      focusError.value = err instanceof Error ? err : new Error('focus load failed')
      focusFile.value = null
    } finally {
      if (ws.selection.value?.msr === requestedMsr) focusPending.value = false
    }
  }

  watch(() => ws.selection.value?.msr, loadFocus, { immediate: true })

  const retryFocus = () => loadFocus(ws.selection.value?.msr)

  const paramSummaries = computed<MsrParamSummary[]>(() => focusFile.value?.parameters ?? [])
  const availableParams = computed(() => paramSummaries.value.map(p => p.parameter))

  // Effective parameter: honor the URL `mp` when the focus file actually has it,
  // else fall back to the file's first parameter (recipes differ — the sample's
  // WAFER param doesn't exist in a GATE_CD recipe).
  const activeParam = computed(() => {
    const want = ws.selection.value?.mp
    const params = availableParams.value
    if (want && params.includes(want)) return want
    return params[0] ?? want ?? ''
  })

  const activeSummary = computed<MsrParamSummary | null>(() =>
    paramSummaries.value.find(p => p.parameter === activeParam.value) ?? null
  )
  const activeUnit = computed(() => activeSummary.value?.unit ?? '')
  const siteRows = computed<MsrFileRow[]>(() => focusFile.value?.rows ?? [])

  // Physical wafer geometry (size, centre, die pitch) parsed from the focus
  // file's exe_detail_info — the single source for placing points on the wafer
  // map and measuring radius, so the map, radius plot and table agree on units.
  const waferGeo = computed<WaferGeometry>(() => parseWaferGeometry(focusFile.value?.exe_detail_info))

  // Focused measurement point (sequence) — shared inspection state for linked
  // selection across the overview panels. useState so it survives remounts;
  // resets whenever the focus MSR or active parameter changes (a sequence only
  // identifies a point within one measurement + parameter).
  const focusedSequence = useState<number | null>(`skewvoir-focused-seq-${ws.toolType}`, () => null)
  const setFocusedSequence = (seq: number | null) => {
    focusedSequence.value = seq
  }
  watch([() => ws.selection.value?.msr, activeParam], () => {
    focusedSequence.value = null
  })

  // Focused canonical site key — shared linked-site state across the analysis
  // views, carried in the URL `site` param so a shared link restores it. useState
  // so it survives remounts; seeded from the URL. Its full consumers are later
  // spatial/gallery tasks; here we own its lifecycle + reset.
  const focusedSite = useState<string | null>(
    `skewvoir-focused-site-${ws.toolType}`,
    () => ws.siteParam.value ?? null
  )
  const setFocusedSite = (siteKey: string | null) => {
    focusedSite.value = siteKey
    ws.setSite(siteKey)
  }
  // The site keys the current focus can address (Phase-1: die identity from
  // chip_number). When the active parameter or focus group changes and the held
  // site key is no longer among them, reset the linked site so a stale key from
  // a different measurement/parameter never lingers.
  const validSiteKeys = computed(() => new Set(siteRows.value.map(r => r.chip_number)))
  watch([activeParam, () => ws.selection.value?.msr], () => {
    if (focusedSite.value && !validSiteKeys.value.has(focusedSite.value)) {
      setFocusedSite(null)
    }
  })

  // --- Overview → detail hand-offs (Task 13) ---
  // Four evidence hand-offs, generated ONLY from facts already sitting in
  // memory (siteRows/availableParams/focusedSite) — no new fetch. A hand-off
  // whose underlying fact isn't confirmed carries `ready: false` + a reason
  // string instead of a working target, so a caller renders the reason rather
  // than a CTA that would land on an empty page.
  const handoffs = computed<HandoffTarget[]>(() => buildHandoffs(
    {
      activeParam: activeParam.value,
      availableParams: availableParams.value,
      focusedSite: focusedSite.value
    },
    {
      coordinates: hasSpatialCoordinates(siteRows.value, activeParam.value),
      sequence: hasSequenceEvidence(siteRows.value, activeParam.value),
      images: hasImageEvidence(siteRows.value, activeParam.value)
    }
  ))

  // Navigate a hand-off atomically: ONE router.replace carrying `view` plus the
  // target state, so a single click lands on the detail view already
  // configured (no extra history entry, no second render with stale state).
  const goHandoff = (target: HandoffTarget) => {
    if (!target.ready) return
    ws.patchQuery(target.query)
  }

  // The B1 overview roll-up (coverage, outlier count, status, table rows) for the
  // ACTIVE parameter. overviewFor() computes the same for any parameter (navigator).
  const activeOverview = computed<OverviewSites>(() =>
    overviewSites(siteRows.value, activeParam.value, anomalyCfg.value)
  )
  const overviewFor = (parameter: string): OverviewSites =>
    overviewSites(siteRows.value, parameter, anomalyCfg.value)

  // Once the file loads, if the URL `mp` isn't one of its parameters the charts
  // fall back to the first param — but the rail/breadcrumb and any saved link
  // still show the stale `mp`. Write the effective param back to the URL so the
  // displayed selection (and saved views) match what's actually plotted.
  watch([availableParams, () => ws.selection.value?.mp], ([params, mp]) => {
    if (params.length === 0) return
    if (mp && params.includes(mp)) return
    if (activeParam.value && activeParam.value !== mp) ws.setParam(activeParam.value)
  })

  // --- Curated set (Time-Series + Position Stack), fetched lazily ---
  // Both views consume the same batch-fetched MsrFiles of the URL `msrs` set:
  // Time-Series builds the trend, Position Stack builds the composite map.
  // The curated comparison set is shared across ALL non-dashboard detail views
  // under `set` scope (position / time-series / correlation / gallery), so a set
  // edited in one view is present in the others. Dashboard stays excluded to
  // preserve the single-measurement lazy-load invariant (no set fan-out).
  const wantSet = computed(() =>
    ws.scope.value === 'set' && ws.activeKind.value !== 'dashboard'
  )

  // meas_hist row lookup by msr, for resolving the curated set + picker labels.
  const rowByMsr = computed(() => new Map(rows.value.map(r => [r.msr, r])))

  // Chip-strip label for an msr in the URL `msrs` set: the row's eqp_id +
  // timestamp when meas_hist has loaded a row for it, else the bare msr id
  // (deep-link msr with no row). Rendering a label never requires an msr_file
  // fetch — it only reads the already-loaded meas_hist list.
  const msrLabel = (msr: string): string => {
    const row = rowByMsr.value.get(msr)
    if (!row) return msr
    return `${row.eqp_id} · ${formatRecipeTimestamp(row.timestamp)}`
  }

  // Move the focus to another MSR in place (no history entry): rewrites the URL
  // `msr` and the focus identity `lot`/`eq`/`cap` from the new focus's meas_hist
  // row (so LeftRail never shows a stale identity), while preserving
  // `msrs`/`view`/`mp`. A deep-link MSR with no row keeps the existing identity.
  const setFocusedMsr = (msr: string) => {
    if (!msr || msr === ws.selection.value?.msr) return
    const row = rowByMsr.value.get(msr)
    ws.setFocus({
      msr,
      lot: row?.lot_id,
      eq: row?.eqp_id,
      cap: row?.timestamp
    })
  }

  // All analyzable measurements — the candidate pool for the Time-Series picker.
  const candidateRows = computed<MeasHistRow[]>(() =>
    rows.value.filter(r => r.msr_check === 'Yes')
  )

  // The EXPLICIT curated comparison set, resolved from the URL `msrs` list (in
  // its authored order, capped defensively).
  const setRows = computed<MeasHistRow[]>(() =>
    ws.msrList.value
      .map(id => rowByMsr.value.get(id))
      .filter((r): r is MeasHistRow => r != null)
      .slice(0, TREND_LIMIT)
  )

  // setFiles itself is declared earlier (ahead of loadFocus's TDZ boundary);
  // this watcher is its only populating side effect.
  const setPending = ref(false)

  const setKey = computed(() =>
    wantSet.value ? setRows.value.map(r => r.msr).sort().join('|') : ''
  )

  watch(setKey, async (key) => {
    if (!key) return
    const list = setRows.value
    if (list.length === 0) {
      setFiles.value = new Map()
      return
    }
    setPending.value = true
    try {
      const res = await fetchMsrFiles(list.map(r => ({
        msr: r.msr,
        className: r.class_name,
        totalImages: r.total_images
      })))
      setFiles.value = new Map(res.map(f => [f.msr, f]))
    } catch {
      // Leave the previous map in place on failure rather than blanking the chart.
    } finally {
      setPending.value = false
    }
  }, { immediate: true })

  // One trend point per measurement in the curated set, at its meas_hist
  // timestamp, for the active param. Sorted by time for the trend line.
  const trendPoints = computed<TimeSeriesPoint[]>(() => {
    const points: (TimeSeriesPoint & { ts: number })[] = []
    for (const row of setRows.value) {
      const summary = setFiles.value.get(row.msr)?.parameters.find(p => p.parameter === activeParam.value)
      if (!summary) continue
      points.push({
        ts: new Date(row.timestamp).getTime(),
        msr: row.msr,
        label: formatRecipeTimestamp(row.timestamp),
        eqpId: row.eqp_id,
        mean: summary.mean,
        min: summary.min,
        max: summary.max,
        std: summary.std
      })
    }
    points.sort((a, b) => a.ts - b.ts)

    // Peer verdicts under the active method: level (mean) and spread (std), each
    // judged leave-one-out against the rest of the curated set, then combined.
    const meanV = peerVerdicts(points.map(p => p.mean), { config: anomalyCfg.value, metric: 'mean' })
    const spreadV = peerVerdicts(points.map(p => p.std), { config: anomalyCfg.value, metric: 'spread', tag: '산포' })

    return points.map(({ ts: _ts, ...rest }, i) => ({
      ...rest,
      verdict: combineVerdicts([meanV[i]!, spreadV[i]!])
    }))
  })

  // Watch/abnormal counts across the curated trend, for the panel meta.
  const trendSummary = computed(() => {
    let watch = 0, abnormal = 0
    for (const p of trendPoints.value) {
      if (p.verdict?.severity === 'abnormal') abnormal++
      else if (p.verdict?.severity === 'watch') watch++
    }
    return { watch, abnormal }
  })

  // Verdict for the focused measurement (if it is in the curated trend set), for the badge.
  const focusVerdict = computed<CombinedVerdict | null>(() =>
    trendPoints.value.find(p => p.msr === focusRow.value?.msr)?.verdict ?? null
  )

  // --- Cross-MSR compatibility manifest + reference (shared analysis context) ---
  // The manifest assembles the loaded MSRs — focus first, then the curated set
  // members (deduped, focus included) — and computes inclusion / exclusion /
  // groups / readiness against the focus for the active parameter. `requestedMsrs`
  // is the URL set so `counts.selected` (picked) and `counts.loaded` (fetched)
  // stay distinct. No siteKeys are passed: the Phase-1 mock carries no canonical
  // site keys, so layout-dependent readiness stays `unavailable` (intended).
  const manifest = computed<AnalysisManifest>(() => {
    const focusMsr = ws.selection.value?.msr ?? ''
    const focus = focusFile.value
    if (!focus || !focusMsr) {
      // No focus loaded yet — a safe, degenerate manifest (never throws).
      return buildAnalysisManifest(focusMsr, [], activeParam.value, {
        requestedMsrs: ws.msrList.value
      })
    }
    const sources: SignatureSource[] = [focus]
    const seen = new Set<string>([focus.msr])
    for (const file of setFiles.value.values()) {
      if (seen.has(file.msr)) continue
      seen.add(file.msr)
      sources.push(file)
    }
    return buildAnalysisManifest(focusMsr, sources, activeParam.value, {
      requestedMsrs: ws.msrList.value
    })
  })

  // The focus MSR described as the reference every candidate is compared against
  // (consumed by the spatial / sequence / hand-off tasks). Null until a focus
  // file has loaded.
  const reference = computed<ReferenceDescriptor | null>(() => {
    const focus = focusFile.value
    const focusMsr = ws.selection.value?.msr
    if (!focus || !focusMsr) return null
    return {
      msr: focusMsr,
      parameter: activeParam.value,
      scope: manifest.value.scope,
      signature: extractSignature(focus, activeParam.value)
    }
  })

  // --- Shared feature table (Task 4) ---
  // The SAME per-MSR feature source Time-Series (Task 8) and multi-MSR
  // Correlation (Task 10) read from, so neither recomputes its own
  // level/spread/spatial/FDC numbers. Sources: focus first, then the curated
  // set's loaded files, deduped by msr (mirrors `manifest` above) — featureRows
  // dedupes defensively too, so passing an already-deduped list here is just
  // an optimization, not a correctness requirement.
  const featureSources = computed<FeatureSource[]>(() => {
    const focus = focusFile.value
    const list: FeatureSource[] = []
    const seen = new Set<string>()
    if (focus) {
      list.push(focus)
      seen.add(focus.msr)
    }
    for (const file of setFiles.value.values()) {
      if (seen.has(file.msr)) continue
      seen.add(file.msr)
      list.push(file)
    }
    return list
  })

  const featureRows = computed<MsrFeatureRow[]>(() =>
    computeFeatureRows(featureSources.value, activeParam.value, anomalyCfg.value)
  )
  const featureRegistry = computed<FeatureDefinition[]>(() =>
    computeFeatureRegistry(featureSources.value, activeParam.value)
  )

  return {
    focusMsr,
    focusRow,
    fab,
    focusFile,
    focusPending,
    focusError,
    retryFocus,
    activeParam,
    availableParams,
    // Re-exported so the Data Summary rows can switch the plotted parameter.
    // It replaced the header's parameter select, which read as dead chrome.
    setParam: ws.setParam,
    paramSummaries,
    activeSummary,
    activeUnit,
    siteRows,
    waferGeo,
    focusedSequence,
    setFocusedSequence,
    focusedSite,
    setFocusedSite,
    setFocusedMsr,
    handoffs,
    goHandoff,
    // For the overview focus-switcher chip strip: chip order comes from
    // ws.msrList directly, labels from rowByMsr/msrLabel — no msr_file fetch.
    rowByMsr,
    msrLabel,
    msrList: ws.msrList,
    scope: ws.scope,
    manifest,
    reference,
    activeOverview,
    overviewFor,
    candidateRows,
    setRows,
    setFiles,
    setPending,
    trendPoints,
    anomalyCfg,
    trendSummary,
    focusVerdict,
    featureRows,
    featureRegistry
  }
}

export type SkewvoirAnalysis = ReturnType<typeof useSkewvoirAnalysis>
