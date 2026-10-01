<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 class="sk-page-title flex items-center gap-2">
          <UIcon
            name="i-lucide-bar-chart-3"
            class="text-sky-500"
          />
          사용 통계
        </h1>
        <p class="sk-meta mt-1">
          최근 활동, 최근 쓴 기능, 전체 사용 추이를 보여줍니다.
        </p>
        <!-- The header pill is icon-only (no width for a name in the top nav),
             so this page is where the caller reads who they are signed in as. -->
        <p
          v-if="identity"
          class="sk-meta mt-1 flex items-center gap-1.5"
        >
          <UIcon
            name="i-lucide-user-round"
            class="size-4"
          />
          <span class="font-medium text-(--sk-ink)">{{ displayName(identity) }}</span>
          <span>· 사번 {{ identity.user_id }}</span>
          <UBadge
            v-if="isUnverifiedDeclaration(identity)"
            color="warning"
            variant="subtle"
            size="sm"
            label="미검증"
          />
        </p>
      </div>
      <UButton
        :loading="refreshing"
        icon="i-lucide-refresh-cw"
        color="neutral"
        variant="ghost"
        @click="refreshAll"
      >
        새로고침
      </UButton>
    </header>

    <UAlert
      v-if="loadError"
      color="error"
      variant="subtle"
      icon="i-lucide-circle-alert"
      title="일부 활동 데이터를 불러오지 못했습니다."
      :description="loadError"
      :actions="[{ label: '다시 시도', onClick: refreshAll }]"
    />

    <UCard
      v-if="!me && !loadError"
      class="dashboard-surface"
    >
      <AppLoadingState
        variant="inline"
        title="사용 통계를 불러오는 중입니다."
      />
    </UCard>

    <!-- Personal panel: always visible -->
    <section
      v-if="me"
      class="grid grid-cols-1 lg:grid-cols-3 gap-4"
    >
      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
            <UIcon name="i-lucide-calendar-check" />
            이번 달
          </span>
        </template>
        <div class="grid grid-cols-2 gap-4">
          <ActivityStatCell
            icon="i-lucide-activity"
            color="text-sky-500"
            :value="me.this_month.requests"
            label="요청 수"
          />
          <ActivityStatCell
            icon="i-lucide-calendar-days"
            color="text-emerald-500"
            :value="me.this_month.days_active"
            label="활동일"
            unit="일"
          />
          <ActivityStatCell
            icon="i-lucide-history"
            color="text-violet-500"
            :value="myRecent"
            label="가장 최근 쓴 기능"
          />
          <ActivityStatCell
            icon="i-lucide-clock"
            color="text-amber-500"
            :value="lastSeenLabel"
            label="마지막 활동"
          />
        </div>
      </UCard>

      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
            <UIcon name="i-lucide-history" />
            내가 최근 쓴 기능 5개
          </span>
        </template>
        <ActivityRecentFeatureList
          :items="me.recent_features"
          empty-text="아직 기록된 활동이 없습니다."
        />
      </UCard>

      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
            <UIcon name="i-lucide-trending-up" />
            30일 활동
          </span>
        </template>
        <ActivitySparkline :series="me.daily" />
      </UCard>

      <UCard class="dashboard-surface lg:col-span-3">
        <template #header>
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
            <UIcon name="i-lucide-calendar-days" />
            내 방문 달력 · 최근 3개월 (90일)
          </span>
        </template>
        <ActivityCalendar :series="me.visits ?? []" />
      </UCard>
    </section>

    <!-- Shared usage panel: visible to every viewer -->
    <template v-if="me">
      <div class="flex items-center gap-2 pt-2">
        <UIcon
          name="i-lucide-users"
          class="text-sky-500"
        />
        <h2 class="sk-heading">
          전체 사용 현황
        </h2>
        <UBadge
          color="primary"
          variant="subtle"
          size="sm"
        >
          전체 공개
        </UBadge>
      </div>

      <!-- KPI row -->
      <section class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <ActivityKpiCard
          v-for="kpi in kpiCards"
          :key="kpi.label"
          :label="kpi.label"
          :value="kpi.value"
          :hint="kpi.hint"
          :icon="kpi.icon"
          :color="kpi.color"
        />
      </section>

      <!-- Top features bar chart -->
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-list-ordered" />
              인기 기능 Top 10
            </span>
            <UTabs
              v-model="windowKey"
              :items="windowTabs"
              variant="pill"
              size="xs"
            />
          </div>
        </template>
        <ActivityFeatureBarList
          :items="topFeaturesForWindow"
          empty-text="아직 데이터가 없습니다."
        />
        <p
          v-if="rankingNotice"
          class="mt-2 text-xs text-(--sk-ink-subtle)"
        >
          {{ rankingNotice }}
        </p>
      </UCard>

      <!-- Fab별 페이지 사용 -->
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-factory" />
              Fab별 페이지 사용
              <!-- rankableFabRows drops the 미지정 bucket. Saying so matters:
                   a silent omission reads as "this is all the traffic", and
                   device-statistics and AFM are missing from this card entirely. -->
              <span class="sk-meta font-normal">· FAB 무관 페이지 제외</span>
            </span>
            <UTabs
              v-model="fabWindowKey"
              :items="windowTabs"
              variant="pill"
              size="xs"
            />
          </div>
        </template>
        <div
          v-if="fabsForWindow.length"
          class="grid grid-cols-1 md:grid-cols-[minmax(0,11rem)_1fr] gap-4"
        >
          <nav
            aria-label="Fab 선택"
            class="flex flex-row md:flex-col gap-1 overflow-x-auto md:overflow-visible border-b md:border-b-0 md:border-r border-(--sk-border) pb-2 md:pb-0 md:pr-3"
          >
            <button
              v-for="row in fabsForWindow"
              :key="row.fab"
              type="button"
              :aria-pressed="selectedFab === row.fab"
              class="flex items-center justify-between gap-2 rounded-lg px-3 py-1.5 text-sm shrink-0 w-full text-left transition-colors"
              :class="selectedFab === row.fab
                ? 'bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 font-semibold shadow-sm'
                : 'text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800'"
              @click="selectedFab = row.fab"
            >
              <span class="font-semibold tracking-wide truncate">{{ row.fab }}</span>
              <span class="tabular-nums text-xs shrink-0 opacity-80">
                활성 {{ row.total.toLocaleString() }}명
              </span>
            </button>
          </nav>
          <ActivityFeatureBarList
            :items="selectedFabPages"
            empty-text="아직 데이터가 없습니다."
          />
        </div>
        <div
          v-else
          class="sk-body"
        >
          아직 데이터가 없습니다.
        </div>
      </UCard>

      <!-- Admin tools: the /admin pages are deliberately kept out of the
           nav (see intro.vue's visibleSections), so this is the only place an
           admin can reach them without typing the URL. -->
      <UCard
        v-if="isAdmin"
        class="dashboard-surface"
      >
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-shield-check" />
              관리자 도구
            </span>
            <UBadge
              color="warning"
              variant="subtle"
              size="sm"
            >
              관리자 전용
            </UBadge>
          </div>
        </template>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <NuxtLink
            v-for="link in adminLinks"
            :key="link.to"
            :to="link.to"
            class="group flex items-start gap-3 rounded-(--sk-r-card) border border-(--sk-border) p-3 transition hover:bg-(--sk-accent-soft)"
          >
            <UIcon
              :name="link.icon"
              class="size-5 shrink-0 mt-0.5 text-(--sk-ink-muted)"
            />
            <div class="min-w-0">
              <div class="text-sm font-medium text-(--sk-ink) flex items-center gap-1.5">
                {{ link.title }}
                <UIcon
                  name="i-lucide-arrow-right"
                  class="size-3.5 opacity-0 transition group-hover:opacity-100"
                />
              </div>
              <p class="sk-meta mt-0.5">
                {{ link.description }}
              </p>
            </div>
          </NuxtLink>
        </div>
      </UCard>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  resetActivityCache,
  useActivityMe,
  useActivityFabs,
  useActivitySummary,
  type FeatureCount,
  type FabUsageRow
} from '~/composables/useActivityApi'
import { activityFeatureLabel, pageViewNotice, rankableFabRows } from '~/utils/activity'
import { displayName, isUnverifiedDeclaration } from '~/utils/identityDisplay'
import { operationalDataErrorMessage } from '~/utils/operationalDataError'
import { formatKoreanDateTime } from '~/utils/dateTime'

useHead({ title: '사용 통계 | SKEWNONO' })

// Already fetched by the route middleware — no extra /api/me request here.
const { identity } = useIdentity()

const {
  data: me,
  error: meError,
  refresh: refreshMe,
  status: meStatus
} = await useActivityMe()

const isAdmin = computed(() => me.value?.is_admin === true)

// Kept in sync with intro.vue's `section: 'admin'` page guides.
const adminLinks = [
  {
    to: '/admin/visitors',
    icon: 'i-lucide-user-round-search',
    title: '방문자 분석',
    description: 'DAU·WAU·MAU 추이와 누가 얼마나 자주 방문하는지 봅니다.'
  },
  {
    to: '/admin/logs',
    icon: 'i-lucide-file-search',
    title: '운영 로그',
    description: 'level·path·사번으로 요청 로그와 오류를 추적합니다.'
  },
  {
    to: '/admin/access',
    icon: 'i-lucide-shield-check',
    title: '접근 권한 관리',
    description: 'X-사번 차단 예외를 허용하고 최근 차단 시도를 확인합니다.'
  }
]

// Summary + fab breakdown are shared activity views, so every viewer fetches
// them. Everything per-employee is admin-only and lives on /admin/visitors.
const sharedQueries = await Promise.all([
  useActivitySummary(),
  useActivityFabs()
]).then(
  ([summary, fabs]) => ({ summary, fabs })
)

const summary = computed(() => sharedQueries.summary.data.value ?? null)
const fabs = computed(() => sharedQueries.fabs.data.value ?? null)

const loadError = computed(() => {
  const error = meError.value
    ?? sharedQueries.summary.error.value
    ?? sharedQueries.fabs.error.value
  if (!error) return null
  return operationalDataErrorMessage(
    error,
    '활동 데이터를 불러오지 못했습니다.'
  )
})

const refreshing = computed(() => {
  if (meStatus.value === 'pending') return true
  if (sharedQueries.summary.status.value === 'pending') return true
  if (sharedQueries.fabs.status.value === 'pending') return true
  return false
})

const refreshAll = async () => {
  resetActivityCache()
  const jobs: Array<Promise<unknown>> = [refreshMe()]
  jobs.push(
    sharedQueries.summary.refresh(),
    sharedQueries.fabs.refresh()
  )
  await Promise.all(jobs)
}

const myRecent = computed(() => activityFeatureLabel(me.value?.recent_features?.[0]?.feature))

const formatTime = (iso: string | null | undefined) => formatKoreanDateTime(iso)

const lastSeenLabel = computed(() => formatTime(me.value?.last_seen))

// --- shared usage: KPI cards ---
const kpiCards = computed(() => {
  if (!summary.value) return []
  const returnRate = summary.value.mau > 0
    ? Math.round((summary.value.wau / summary.value.mau) * 100)
    : 0
  return [
    {
      label: 'DAU',
      value: summary.value.dau,
      hint: '오늘 활동한 사용자',
      icon: 'i-lucide-user',
      color: 'text-sky-500'
    },
    {
      label: 'WAU',
      value: summary.value.wau,
      hint: '최근 7일 활동한 사용자',
      icon: 'i-lucide-users',
      color: 'text-violet-500'
    },
    {
      label: 'MAU',
      value: summary.value.mau,
      hint: '최근 30일 활동한 사용자',
      icon: 'i-lucide-user-check',
      color: 'text-emerald-500'
    },
    {
      label: 'WAU / MAU',
      value: `${returnRate}%`,
      hint: '월간 사용자 중 주간 활동 비율',
      icon: 'i-lucide-repeat-2',
      color: 'text-rose-500'
    }
  ]
})

// --- shared usage: top features window toggle ---
const windowKey = ref<'7d' | '30d'>('7d')
const windowTabs = [
  { label: '최근 7일', value: '7d' },
  { label: '최근 30일', value: '30d' }
]
const topFeaturesForWindow = computed<FeatureCount[]>(() => {
  if (!summary.value) return []
  return windowKey.value === '7d'
    ? summary.value.top_features_7d
    : summary.value.top_features_30d
})
const rankingNotice = computed(() =>
  pageViewNotice(windowKey.value === '7d' ? 7 : 30, new Date())
)

// --- shared usage: Fab page breakdown ---
const fabWindowKey = ref<'7d' | '30d'>('7d')
const fabsForWindow = computed<FabUsageRow[]>(() =>
  rankableFabRows(
    fabWindowKey.value === '7d'
      ? fabs.value?.fabs_7d ?? []
      : fabs.value?.fabs_30d ?? []
  )
)
const selectedFab = ref<string | null>(null)
watchEffect(() => {
  const rows = fabsForWindow.value
  if (!rows.length) {
    selectedFab.value = null
    return
  }
  if (!selectedFab.value || !rows.some(row => row.fab === selectedFab.value)) {
    selectedFab.value = rows[0]?.fab ?? null
  }
})
const selectedFabPages = computed<FeatureCount[]>(() => {
  const row = fabsForWindow.value.find(item => item.fab === selectedFab.value)
  return row?.pages ?? []
})
</script>
