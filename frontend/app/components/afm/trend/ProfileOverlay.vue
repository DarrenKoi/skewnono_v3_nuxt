<template>
  <AfmCard
    icon="i-lucide-chart-spline"
    title="라인 프로파일 × 측정"
  >
    <template
      v-if="points.length && wanted.length"
      #actions
    >
      <div class="flex flex-wrap items-center gap-2.5">
        <label class="flex items-center gap-1.5">
          <span class="sk-label">포인트</span>
          <USelect
            v-model="point"
            :items="points"
            size="xs"
            class="min-w-44"
            aria-label="포인트"
          />
        </label>
        <span class="h-4.5 w-px bg-(--sk-border)" />
        <div
          class="flex items-center gap-1"
          role="group"
          aria-label="레벨링"
        >
          <span class="sk-label">레벨링</span>
          <SkChip
            v-for="m in LEVELS"
            :key="m.value"
            size="sm"
            tone="ink"
            :label="m.label"
            :active="level === m.value"
            @click="level = m.value"
          />
        </div>
      </div>
    </template>

    <p
      v-if="!points.length"
      class="flex h-80 items-center justify-center sk-body"
    >
      선택한 측정에 포인트가 없습니다.
    </p>
    <p
      v-else-if="nothing"
      class="flex h-80 items-center justify-center sk-body"
    >
      {{ wanted.length ? `포인트 ${point}의 프로파일이 있는 측정이 없습니다.` : '이 그룹의 측정에는 프로파일이 없습니다.' }}
    </p>
    <div
      v-else-if="!opened"
      class="flex h-80 flex-col items-center justify-center gap-2"
    >
      <UButton
        size="sm"
        color="neutral"
        variant="outline"
        icon="i-lucide-download"
        :label="`프로파일 불러오기 (최대 ${wanted.length}건)`"
        @click="opened = true"
      />
      <span class="sk-hint">선택한 측정부터 읽고, 포인트를 바꿀 때마다 그 포인트의 프로파일을 측정마다 한 번씩 요청합니다.</span>
    </div>
    <template v-else>
      <AppLoadingState
        v-if="!overlay.drawn.length && pendingCount"
        variant="inline"
        class="h-80"
        title="프로파일을 불러오는 중입니다."
      />
      <p
        v-else-if="!overlay.drawn.length"
        class="flex h-80 items-center justify-center sk-body"
      >
        겹쳐 그릴 1D 프로파일이 없습니다.
      </p>
      <div
        v-else
        ref="chartEl"
        class="h-80 w-full"
      />
      <p class="mt-1.5 flex flex-wrap gap-x-3.5 gap-y-1 sk-meta">
        <span>포인트 {{ point }}{{ recipe ? ` · ${recipe}만` : '' }} · 겹친 측정 {{ overlay.drawn.length }}건</span>
        <span class="text-(--sk-ink)">레벨링: {{ LEVEL_NOTE[level] }}</span>
        <!-- The legend names only the lines on the chart: with no selected
             measurement among them, nothing is drawn in ink. -->
        <span v-if="overlay.drawn.some(l => l.key !== selected)">— {{ overlay.drawn.some(l => l.key === selected) ? '다른 측정' : '측정' }}</span>
        <span
          v-if="overlay.drawn.some(l => l.key === selected)"
          class="text-(--sk-ink)"
        >— 선택한 측정</span>
        <span>X 위치는 파일 그대로이며 맞추거나 보간하지 않습니다</span>
        <span v-if="thinned">서버가 솎은 표본이 섞여 있습니다</span>
        <span v-if="pendingCount">{{ pendingCount }}건 불러오는 중</span>
      </p>
      <div
        v-if="skipped.length"
        class="mt-3 border-t border-(--sk-border) pt-2.5"
      >
        <div class="flex items-center gap-2">
          <span class="sk-label">그리지 않은 측정 {{ skipped.length }}건</span>
          <UButton
            v-if="skipped.some(s => s.reason === 'failed')"
            size="xs"
            color="neutral"
            variant="outline"
            label="다시 시도"
            @click="run"
          />
        </div>
        <ul class="mt-1 grid grid-cols-1 gap-x-6 gap-y-0.5 sk-meta 2xl:grid-cols-2">
          <li
            v-for="s in skipped"
            :key="s.key"
          >
            <span :class="s.key === selected ? 'text-(--sk-ink)' : ''">{{ s.name }}</span> — {{ s.label }}
          </li>
        </ul>
      </div>
    </template>
  </AfmCard>
</template>

<script lang="ts">
import type { EChartsOption } from 'echarts'
import { shallowReactive } from 'vue'
import type { ProfileLoad, ProfileSkip } from '~/utils/afmProfile'
import type { TrendEntry } from '~/utils/afmTrend'

// One read of a point's profile per tool × filename × point for the SPA's
// lifetime. Only what the overlay draws is kept: a 1D line as [x, z] pairs, a
// 2D scan as its reason alone.
// ponytail: never evicted — a 16384-sample line is ~16k pairs; add an LRU if a
// session walking many points of a 20-measurement group shows up in memory.
const profileCache = shallowReactive(new Map<string, ProfileLoad>())
const inflight = new Set<string>()
</script>

<script setup lang="ts">
type Level = 'none' | 'line'

const props = defineProps<{
  tool: string
  // One recipe's measurements in time order: a mixed group is narrowed before it gets here.
  entries: TrendEntry[]
  // Set in a mixed group: the one recipe whose profiles are overlaid.
  recipe?: string
  selected: string | null
  // Filenames whose list row says the measurement has no profile: never requested.
  noProfile: Set<string>
  exportName: string
}>()

const LEVELS: { value: Level, label: string }[] = [
  { value: 'none', label: '없음' },
  { value: 'line', label: '직선 제거' }
]
const LEVEL_NOTE: Record<Level, string> = {
  none: '없음 (파일에 저장된 높이 그대로이며, 측정마다 절대 높이가 다를 수 있습니다)',
  line: '직선 제거 (프로파일마다 자신의 최소제곱 직선을 뺀 높이이며, 저장된 높이가 아닙니다)'
}
const SKIP_LABEL: Record<ProfileSkip, string> = {
  none: '이 포인트의 프로파일 없음',
  grid: '2D 격자',
  nounit: '단위 정보 없음',
  failed: '불러오지 못함',
  unit: '단위 다름',
  unchecked: '조회하지 않음 (선택한 측정이 2D 격자)'
}

const sk = useChartPalette()
const { fetchProfile } = useAfmDetailApi()

// Requests start only once the user opens the section.
const opened = ref(false)
const level = ref<Level>('none')

// The selected measurement names the points; the rest are asked for the same name.
const anchor = computed(() => props.entries.find(entry => entry.key === props.selected) ?? props.entries[0])
const points = computed(() => [...(anchor.value?.payload.available_points ?? [])].sort(comparePoints))
const point = ref('')
watch(points, (next) => {
  if (!next.includes(point.value)) point.value = next[0] ?? ''
}, { immediate: true })

const cacheKey = (filename: string, p = point.value) => `${props.tool}|${filename}|${p}`
const wanted = computed(() => props.entries.filter(entry => !props.noProfile.has(entry.key)).map(entry => entry.key))

const fetchOne = async (filename: string, p: string) => {
  const key = cacheKey(filename, p)
  if (profileCache.has(key) || inflight.has(key)) return
  inflight.add(key)
  try {
    profileCache.set(key, readProfile(await fetchProfile(props.tool, filename, p)))
  } catch (error) {
    // The route answers 404 when the measurement has no profile for the point.
    profileCache.set(key, { skip: (error as { statusCode?: number } | null)?.statusCode === 404 ? 'none' : 'failed' })
  } finally {
    inflight.delete(key)
  }
}

const isSkip = (load: ProfileLoad | null | undefined, reason: ProfileSkip) => !!load && 'skip' in load && load.skip === reason

// The selected measurement is read first: when its scan is a 2D grid there is
// nothing to overlay on, and the others (tens of thousands of samples each) are
// not requested. The rest then go out together, as the page's detail reads do.
const run = async () => {
  const p = point.value
  const first = anchor.value?.key
  if (!opened.value || !p || !first) return
  // A failed read is asked again; every other answer is kept.
  for (const name of wanted.value) {
    if (isSkip(profileCache.get(cacheKey(name, p)), 'failed')) profileCache.delete(cacheKey(name, p))
  }
  if (wanted.value.includes(first)) await fetchOne(first, p)
  if (p !== point.value || first !== anchor.value?.key || isSkip(profileCache.get(cacheKey(first, p)), 'grid')) return
  await Promise.all(wanted.value.map(name => fetchOne(name, p)))
}
watch([opened, point, () => anchor.value?.key, () => wanted.value.join('|')], run)

const anchorGrid = computed(() => !!anchor.value && isSkip(profileCache.get(cacheKey(anchor.value.key)), 'grid'))
// Keyed by the current point, so an answer for another point is never shown as this one's.
const items = computed(() => props.entries.map((entry) => {
  const load: ProfileLoad | null = props.noProfile.has(entry.key)
    ? { skip: 'none' }
    : profileCache.get(cacheKey(entry.key)) ?? (anchorGrid.value ? { skip: 'unchecked' } : null)
  return { key: entry.key, load }
}))
const pendingCount = computed(() => opened.value ? items.value.filter(item => !item.load).length : 0)
// One empty state instead of a row per measurement: a tool that writes no profile.
const nothing = computed(() => items.value.every(item => isSkip(item.load, 'none')))
const overlay = computed(() => overlayProfiles(
  items.value.flatMap(item => item.load ? [{ key: item.key, load: item.load }] : []),
  props.selected
))

const entryOf = computed(() => new Map(props.entries.map(entry => [entry.key, entry])))
const nameOf = (key: string) => {
  const entry = entryOf.value.get(key)
  return entry ? `${entry.lot}·${entry.slot} ${shortTime(entry.time)}` : key
}
const skipped = computed(() => overlay.value.skipped.map(({ key, reason }) => {
  const load = profileCache.get(cacheKey(key))
  const units = reason === 'unit' && load && 'line' in load
    ? ` (X ${unitSymbol(load.line.xUnit)} · Z ${unitSymbol(load.line.zUnit)})`
    : ''
  return { key, reason, name: nameOf(key), label: `${SKIP_LABEL[reason]}${units}` }
}))
const thinned = computed(() => overlay.value.drawn.some(d => d.line.thinned))

// The selected measurement last, so it is drawn over the rest.
const drawn = computed(() => {
  const { drawn: lines } = overlay.value
  return [...lines.filter(l => l.key !== props.selected), ...lines.filter(l => l.key === props.selected)]
    .map(({ key, line }) => ({ key, data: level.value === 'line' ? levelLine(line.data) : line.data }))
})

const chartOption = computed<EChartsOption>(() => {
  const unit = overlay.value.unit
  const axis = (name: string, nameGap: number) => ({
    type: 'value' as const,
    scale: true,
    name,
    nameGap,
    nameLocation: 'middle' as const,
    nameTextStyle: CHART_LEGEND_LABEL,
    axisLabel: { ...CHART_AXIS_LABEL, hideOverlap: true }
  })
  return {
    grid: { left: 72, right: 16, top: 36, bottom: 48 },
    legend: { type: 'scroll', top: 0, textStyle: CHART_LEGEND_LABEL },
    // Axis-triggered: with no symbols drawn there is no item under the cursor to hit.
    tooltip: {
      trigger: 'axis',
      formatter: (params: unknown) => (Array.isArray(params) ? params : [params])
        .flatMap((p: { seriesName?: string, marker?: string, value?: unknown }) => {
          const value = p.value
          if (!Array.isArray(value) || typeof value[0] !== 'number' || typeof value[1] !== 'number') return []
          // Each profile keeps its own X grid, so each row prints its own sample's X.
          return [`${p.marker ?? ''}${escapeHtml(p.seriesName ?? '')} · X ${value[0].toFixed(2)} · Z ${formatZ(value[1], unit?.z)}`]
        })
        .join('<br/>')
    },
    xAxis: axis(axisTitle('X', unit?.x), 30),
    yAxis: axis(`${axisTitle('Z', unit?.z)}${level.value === 'line' ? ' · 직선 제거' : ''}`, 52),
    series: drawn.value.map(({ key, data }) => {
      const on = key === props.selected
      const color = on ? sk.value.ink : sk.value.muted
      return {
        name: nameOf(key),
        type: 'line' as const,
        // A single sample has no segment to draw, so it alone gets a symbol.
        showSymbol: data.length === 1,
        // A line can hold 16384 samples; lttb keeps its shape at the canvas's width.
        sampling: 'lttb' as const,
        z: on ? 6 : 2,
        lineStyle: { color, width: on ? 2.2 : 1.2, opacity: on ? 1 : 0.55 },
        itemStyle: { color, opacity: on ? 1 : 0.55 },
        emphasis: { focus: 'none' as const, lineStyle: { width: on ? 2.2 : 1.2 } },
        data
      }
    })
  }
})

const chartEl = ref<HTMLDivElement | null>(null)
useEchart(chartEl, chartOption, { exportName: props.exportName })
</script>
