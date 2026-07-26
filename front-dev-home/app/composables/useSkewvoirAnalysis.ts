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
  featureRows as computeFeatureRows,
  featureRegistry as computeFeatureRegistry,
  type FeatureSource,
  type MsrFeatureRow,
  type FeatureDefinition
} from '~/utils/skewvoirAnalysis/features'
import { isNamedParam, paramLabel, sortByRowMpOrder } from '~/utils/skewvoirAnalysis/paramOrder'
import { resolveSetRows, shouldLoadSet } from '~/utils/skewvoirAnalysis/curatedSet'
import { cacheFocusFile, isFocusStillCurrent, lookupFocusFile } from '~/utils/skewvoirAnalysis/focusCache'
import { focusIdentityFromRow } from '~/utils/skewvoirAnalysis/routeQuery'
import { toggleKey, siteKey } from '~/utils/mpSelection'
import { assignSiteColors } from '~/utils/siteColors'
import { SK_SITE, SK_SITE_OVERFLOW } from '~/utils/chartPalette'

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

  // Session cache for focus MsrFile responses, keyed by msr — bounded and
  // evicted by cacheFocusFile (utils/skewvoirAnalysis/focusCache.ts, which owns
  // that rule). A plain Map (not a ref): it's a resolution-order optimization,
  // not reactive UI state.
  const focusCache = new Map<string, MsrFileResponse>()

  // Key on the URL msr itself (not the meas-hist row): the backend resolves the
  // parent class_name/total_images on its own, so a deep/shared link still loads
  // even when the row isn't in the currently-loaded meas-hist list. When the row
  // IS known, pass its fields to skip that backend lookup.
  //
  // lookupFocusFile owns the resolution order (session cache → the curated set's
  // `setFiles`) and isFocusStillCurrent the stale-response guard; this function
  // owns the refs, the await, and the network fetch — the only path left when
  // the lookup misses. Note the synchronous in-memory hit is race-free (nothing
  // to await) but still only ASSIGNS when the focus hasn't moved on; populating
  // focusCache happens unconditionally either way.
  const loadFocus = async (msr: string | undefined) => {
    if (!msr) {
      focusFile.value = null
      focusError.value = null
      return
    }
    const requestedMsr = msr

    const hit = lookupFocusFile(msr, focusCache, setFiles.value)
    if (hit) {
      cacheFocusFile(focusCache, msr, hit.file) // touch recency
      if (isFocusStillCurrent(ws.selection.value?.msr, requestedMsr)) {
        focusFile.value = hit.file
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
      cacheFocusFile(focusCache, msr, res)
      if (!isFocusStillCurrent(ws.selection.value?.msr, requestedMsr)) return
      focusFile.value = res
    } catch (err) {
      if (!isFocusStillCurrent(ws.selection.value?.msr, requestedMsr)) return
      focusError.value = err instanceof Error ? err : new Error('focus load failed')
      focusFile.value = null
    } finally {
      if (isFocusStillCurrent(ws.selection.value?.msr, requestedMsr)) focusPending.value = false
    }
  }

  watch(() => ws.selection.value?.msr, loadFocus, { immediate: true })

  const retryFocus = () => loadFocus(ws.selection.value?.msr)

  // Presentation order everywhere (navigator chips, 파라미터 요약, fallback
  // param) follows the rows' mp_number → sequence, not the backend array order.
  // The unnamed dummy MP is measured first, so it legitimately leads this list —
  // it is selectable (it has images to review), just never the default below.
  const paramSummaries = computed<MsrParamSummary[]>(() =>
    sortByRowMpOrder(focusFile.value?.parameters ?? [], focusFile.value?.rows ?? [])
  )
  const availableParams = computed(() => paramSummaries.value.map(p => p.parameter))

  // Effective parameter: honor the URL `mp` when the focus file actually has it,
  // else fall back to the file's first NAMED parameter (recipes differ — the
  // sample's WAFER param doesn't exist in a GATE_CD recipe).
  //
  // `want != null` rather than a truthiness test: the unnamed dummy MP's name IS
  // the empty string, and a truthy check would reject the reviewer's explicit
  // pick and bounce them to another parameter. Defaulting still skips it — you
  // land on the first real parameter and choose the dummy deliberately — but a
  // file whose ONLY parameter is the dummy falls back to it rather than to
  // nothing.
  const activeParam = computed(() => {
    const want = ws.selection.value?.mp
    const params = availableParams.value
    if (want != null && params.includes(want)) return want
    const named = params.filter(isNamedParam)
    return named[0] ?? params[0] ?? want ?? ''
  })

  // Display form of the active parameter — the unnamed MP renders as a stand-in
  // label instead of an empty string. Components interpolating the parameter
  // into user-facing text use this; row filtering always uses activeParam.
  const activeParamLabel = computed(() => paramLabel(activeParam.value))

  // --- Parameter multi-selection (compare several params side by side) ---
  // The URL `mp` stays the PRIMARY parameter (drives the single-param panels:
  // wafer map, radius, SEM image, distribution). This extra set holds the
  // parameters compared alongside it; tables that can show several params at
  // once (Measurement Points, 파라미터 요약 highlight) read `selectedParams`.
  // useState so it survives remounts; membership is re-validated against the
  // loaded file, so a param from a different recipe never lingers.
  const extraParams = useState<string[]>(`skewvoir-extra-params-${ws.toolType}`, () => [])

  // Effective selection: primary + extras, in the mp-ordered availableParams
  // order (so "display together" follows the same mp_number sort as the chips).
  const selectedParams = computed<string[]>(() => {
    const chosen = new Set(extraParams.value)
    chosen.add(activeParam.value)
    return availableParams.value.filter(p => chosen.has(p))
  })

  // Chip/row click contract: a plain click focuses ONE parameter (clears the
  // comparison), a modifier click (⌘/Ctrl/⇧) toggles membership. The primary
  // can only be removed when another selected param remains to take over.
  const toggleParam = (parameter: string, additive = false) => {
    if (!additive) {
      extraParams.value = []
      ws.setParam(parameter)
      return
    }
    const current = new Set(selectedParams.value)
    if (current.has(parameter)) {
      if (current.size <= 1) return // never empty the selection
      current.delete(parameter)
      if (parameter === activeParam.value) {
        const next = availableParams.value.find(p => current.has(p))
        if (next) ws.setParam(next)
      }
    } else {
      current.add(parameter)
    }
    extraParams.value = [...current]
  }

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

  // Measurement-point multi-selection (checkboxes in the points table). Keyed by
  // a composite (parameter, sequence) so the same sequence number under two
  // compared parameters never collides. Highlights sites on the wafer map /
  // radius plot and scopes the copy/Excel export. Independent of focusedSequence
  // (the single keyboard/SEM cursor). useState so it survives remounts; cleared
  // when the focus MSR (wafer) changes, KEPT across activeParam changes since a
  // selection may span parameters.
  const selectedSites = useState<string[]>(`skewvoir-selected-sites-${ws.toolType}`, () => [])
  const toggleSelectedSite = (param: string, seq: number) => {
    selectedSites.value = toggleKey(selectedSites.value, siteKey(param, seq))
  }
  const setSelectedSites = (list: string[]) => {
    selectedSites.value = list
  }
  const clearSelectedSites = () => {
    selectedSites.value = []
  }
  watch(() => ws.selection.value?.msr, () => {
    selectedSites.value = []
  })

  // The selected sequences BELONGING TO the active parameter - what the wafer map
  // and radius plot (single-parameter views) highlight. Membership-only (never
  // parses a key): reconstructs each candidate key via siteKey() from the known
  // (parameter, sequence) of each row and tests membership, so a separator char
  // inside a parameter name can never cause a mis-parse. After a parameter switch
  // only that parameter's picks light up.
  const selectedSeqsForActiveParam = computed<number[]>(() => {
    const p = activeParam.value
    const sel = new Set(selectedSites.value)
    const seqs = new Set<number>()
    for (const r of siteRows.value) {
      if (r.parameter === p && sel.has(siteKey(p, r.sequence))) seqs.add(r.sequence)
    }
    return [...seqs]
  })

  // Identity color per selected site — one deterministic source shared by the
  // wafer map, radius plot, distribution and points table (see utils/siteColors).
  // Keyed by the same (param, seq) key as selectedSites; picks past the palette
  // cap return null so each consumer can paint them its own neutral tone.
  const siteColorMap = computed<Record<string, string>>(() =>
    assignSiteColors(selectedSites.value, SK_SITE))
  const siteColor = (param: string, seq: number): string | null =>
    siteColorMap.value[siteKey(param, seq)] ?? null

  // The active-parameter selection as a finished seq → color map — every pick
  // resolved to its identity color or the shared overflow neutral. The wafer
  // map, radius plot and distribution all read this one source rather than each
  // re-deriving it (and re-deciding the neutral). The points table stays on the
  // raw siteColor() because it spans parameters, not just the active one.
  const seqColorsForActiveParam = computed<Record<number, string>>(() => {
    const param = activeParam.value
    const out: Record<number, string> = {}
    for (const seq of selectedSeqsForActiveParam.value) {
      out[seq] = siteColor(param, seq) ?? SK_SITE_OVERFLOW
    }
    return out
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
  // shouldLoadSet owns the rule (see utils/skewvoirAnalysis/curatedSet.ts).
  const wantSet = computed(() => shouldLoadSet(ws.scope.value, ws.activeKind.value))

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
    ws.setFocus(focusIdentityFromRow(msr, rowByMsr.value.get(msr)))
  }

  // All analyzable measurements — the candidate pool for the Time-Series picker.
  const candidateRows = computed<MeasHistRow[]>(() =>
    rows.value.filter(r => r.msr_check === 'Yes')
  )

  // The EXPLICIT curated comparison set, resolved from the URL `msrs` list (in
  // its authored order, capped defensively at TREND_LIMIT).
  const setRows = computed<MeasHistRow[]>(() =>
    resolveSetRows(ws.msrList.value, rowByMsr.value)
  )

  // setFiles itself is declared earlier (ahead of loadFocus's TDZ boundary);
  // this watcher is its only populating side effect.
  const setPending = ref(false)

  const setKey = computed(() =>
    wantSet.value ? setRows.value.map(r => r.msr).sort().join('|') : ''
  )

  watch(setKey, async (key) => {
    if (!key) {
      // scope flipped away from 'set' (or the set key is otherwise empty): drop
      // the prior set's files so manifest.counts stops reflecting a stale set
      // while the analysis views (left rail) are showing a non-set scope. No new fetch here —
      // the lazy-load invariant only fires when setKey is non-empty.
      setFiles.value = new Map()
      setPending.value = false
      return
    }
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
  // NB: the local counter is `watchCount`, not `watch` — a bare `let watch`
  // declaration makes Nuxt's unimport treat `watch` as user-provided and skip
  // auto-importing Vue's `watch`, which then throws ReferenceError at every
  // watcher above. The returned key stays `watch` (public shape unchanged).
  const trendSummary = computed(() => {
    let watchCount = 0, abnormal = 0
    for (const p of trendPoints.value) {
      if (p.verdict?.severity === 'abnormal') abnormal++
      else if (p.verdict?.severity === 'watch') watchCount++
    }
    return { watch: watchCount, abnormal }
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
    activeParamLabel,
    availableParams,
    // Re-exported so the Data Summary rows can switch the plotted parameter.
    // It replaced the header's parameter select, which read as dead chrome.
    setParam: ws.setParam,
    selectedParams,
    toggleParam,
    paramSummaries,
    activeSummary,
    activeUnit,
    siteRows,
    waferGeo,
    focusedSequence,
    setFocusedSequence,
    selectedSites,
    toggleSelectedSite,
    setSelectedSites,
    clearSelectedSites,
    selectedSeqsForActiveParam,
    siteColor,
    seqColorsForActiveParam,
    focusedSite,
    setFocusedSite,
    setFocusedMsr,
    // URL-carried X/Y param picks (Correlation single-scope explorer) and the
    // Gallery review-queue filter preset — raw passthrough of the URL params +
    // their setters, same opaque treatment as siteParam/setSite above. Consumers
    // seed local component state from these on mount and write back on change.
    xParam: ws.xParam,
    yParam: ws.yParam,
    setXY: ws.setXY,
    filterParam: ws.filterParam,
    setFilter: ws.setFilter,
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
