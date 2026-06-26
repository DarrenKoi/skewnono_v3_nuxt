import type { MeasHistResponse, MeasHistRow } from '~/composables/useMeasHistApi'
import type { MsrFileResponse, MsrParamSummary, MsrFileRow } from '~/composables/useMsrFileApi'
import type { SkewvoirWorkspace } from '~/composables/useSkewvoirWorkspace'
import type { TimeSeriesPoint } from '~/components/ebeam/skewvoir/TimeSeriesChart.vue'
import { formatRecipeTimestamp } from '~/utils/recipeView'
import { detectMadOutliers } from '~/utils/madOutliers'

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
  const focusRow = computed<MeasHistRow | null>(() =>
    rows.value.find(r => r.msr === ws.selection.value?.msr) ?? null
  )

  // --- Single measurement (Dashboard) ---
  const focusFile = ref<MsrFileResponse | null>(null)
  const focusPending = ref(false)
  const focusError = ref(false)

  // Key on the URL msr itself (not the meas-hist row): the backend resolves the
  // parent class_name/total_images on its own, so a deep/shared link still loads
  // even when the row isn't in the currently-loaded meas-hist list. When the row
  // IS known, pass its fields to skip that backend lookup.
  watch(() => ws.selection.value?.msr, async (msr) => {
    if (!msr) {
      focusFile.value = null
      return
    }
    const row = focusRow.value
    focusPending.value = true
    focusError.value = false
    try {
      focusFile.value = await fetchMsrFile({
        msr,
        className: row?.class_name,
        totalImages: row?.total_images
      })
    } catch {
      focusError.value = true
      focusFile.value = null
    } finally {
      focusPending.value = false
    }
  }, { immediate: true })

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
  const wantSet = computed(() =>
    ws.activeKind.value === 'time-series' || ws.activeKind.value === 'position-stack'
  )

  // meas_hist row lookup by msr, for resolving the curated set + picker labels.
  const rowByMsr = computed(() => new Map(rows.value.map(r => [r.msr, r])))

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

  const setFiles = ref<Map<string, MsrFileResponse>>(new Map())
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

    const meanFlags = detectMadOutliers(points.map(p => p.mean))
    const spreadFlags = detectMadOutliers(points.map(p => p.std))

    return points.map(({ ts: _ts, ...rest }, i) => ({
      ...rest,
      outlier: { mean: meanFlags[i] ?? false, spread: spreadFlags[i] ?? false }
    }))
  })

  return {
    focusRow,
    focusFile,
    focusPending,
    focusError,
    activeParam,
    availableParams,
    paramSummaries,
    activeSummary,
    activeUnit,
    siteRows,
    candidateRows,
    setRows,
    setFiles,
    setPending,
    trendPoints
  }
}

export type SkewvoirAnalysis = ReturnType<typeof useSkewvoirAnalysis>
