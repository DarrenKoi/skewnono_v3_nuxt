<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 class="text-3xl font-bold flex items-center gap-2">
          <UIcon
            name="i-lucide-bar-chart-3"
            class="text-sky-500"
          />
          사용 통계
        </h1>
        <p class="text-sm text-(--sk-ink-muted) mt-1">
          최근 활동, 자주 쓰는 기능, 전체 사용 추이를 보여줍니다.
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
      <div class="flex items-center justify-center gap-2 py-12 text-sm text-(--sk-ink-muted)">
        <UIcon
          name="i-lucide-loader-circle"
          class="animate-spin"
        />
        사용 통계를 불러오는 중입니다.
      </div>
    </UCard>

    <!-- Personal panel: always visible -->
    <section
      v-if="me"
      class="grid grid-cols-1 lg:grid-cols-3 gap-4"
    >
      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
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
            icon="i-lucide-sparkles"
            color="text-violet-500"
            :value="myFavorite"
            label="가장 많이 쓴 기능"
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
          <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
            <UIcon name="i-lucide-pie-chart" />
            내가 자주 쓰는 기능
          </span>
        </template>
        <ActivityFeatureBarList
          :items="me.top_features"
          empty-text="아직 기록된 활동이 없습니다."
        />
      </UCard>

      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
            <UIcon name="i-lucide-trending-up" />
            30일 활동
          </span>
        </template>
        <ActivitySparkline
          :series="me.daily"
          color="from-sky-400 to-violet-500"
        />
      </UCard>

      <UCard class="dashboard-surface lg:col-span-3">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-gauge" />
              내 활동 인사이트
            </span>
            <span class="text-xs text-(--sk-ink-muted)">
              최근 30일 기준
            </span>
          </div>
        </template>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums">
              {{ personalInsights.recent7Requests.toLocaleString() }}
            </div>
            <div class="text-xs text-(--sk-ink-muted)">
              최근 7일 요청
            </div>
          </div>
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums flex items-center gap-1.5">
              <UIcon
                :name="weeklyChange.icon"
                :class="weeklyChange.color"
                class="text-lg"
              />
              {{ weeklyChange.label }}
            </div>
            <div class="text-xs text-(--sk-ink-muted)">
              이전 7일 대비
            </div>
          </div>
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums">
              {{ personalInsights.activeDays7 }}<span class="text-sm font-normal text-(--sk-ink-muted)"> / 7일</span>
            </div>
            <div class="text-xs text-(--sk-ink-muted)">
              최근 활동일
            </div>
          </div>
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums">
              {{ personalInsights.averagePerActiveDay30.toLocaleString() }}
            </div>
            <div class="text-xs text-(--sk-ink-muted)">
              활동일당 평균 요청
            </div>
          </div>
        </div>
      </UCard>
    </section>

    <!-- Shared usage panel: visible to every viewer -->
    <template v-if="me">
      <div class="flex items-center gap-2 pt-2">
        <UIcon
          name="i-lucide-users"
          class="text-sky-500"
        />
        <h2 class="text-lg font-semibold">
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
      <section class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">
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
            <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
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
      </UCard>

      <!-- SEM List usage per equipment model -->
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
              <UIcon name="i-lucide-microscope" />
              SEM List 모델별 사용
            </span>
            <UTabs
              v-model="modelWindowKey"
              :items="windowTabs"
              variant="pill"
              size="xs"
            />
          </div>
        </template>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div
            v-for="group in modelGroups"
            :key="group.vendor"
          >
            <div class="text-xs font-semibold text-(--sk-ink-muted) uppercase tracking-[0.05em] mb-2">
              {{ group.vendor }}
            </div>
            <ActivityModelBarList
              :items="group.rows"
              empty-text="아직 데이터가 없습니다."
            />
          </div>
        </div>
        <div
          v-if="!modelGroups.length"
          class="text-sm text-zinc-500"
        >
          아직 데이터가 없습니다.
        </div>
      </UCard>

      <!-- Users table -->
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
              <UIcon name="i-lucide-users" />
              사용자
            </span>
            <div class="flex items-center gap-2">
              <UBadge
                color="neutral"
                variant="subtle"
              >
                {{ filteredUsers.length }} / {{ users?.users.length ?? 0 }}
              </UBadge>
              <span
                v-if="users"
                class="text-xs text-(--sk-ink-muted)"
              >
                {{ formatTime(users.generated_at) }}
              </span>
            </div>
          </div>
        </template>
        <div class="flex flex-wrap items-center gap-2 pb-3 mb-1 border-b border-(--sk-border)">
          <UInput
            v-model="userQuery"
            class="flex-1 min-w-56"
            size="sm"
            icon="i-lucide-search"
            color="neutral"
            variant="subtle"
            placeholder="사용자 또는 기능 검색"
          />
          <USelect
            v-model="featureFilter"
            class="w-44"
            size="sm"
            color="neutral"
            variant="subtle"
            :items="featureFilterOptions"
          />
          <USelect
            v-model="userSort"
            class="w-44"
            size="sm"
            color="neutral"
            variant="subtle"
            :items="userSortOptions"
          />
          <UButton
            size="sm"
            color="neutral"
            variant="outline"
            icon="i-lucide-download"
            label="CSV 다운로드"
            :disabled="filteredUsers.length === 0"
            @click="downloadUsersCsv"
          />
          <UButton
            size="sm"
            color="neutral"
            variant="ghost"
            icon="i-lucide-rotate-ccw"
            label="초기화"
            :disabled="!hasActiveUserControls"
            @click="resetUserControls"
          />
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-zinc-500 border-b border-(--sk-border)">
                <th class="py-2 pr-4">
                  사용자
                </th>
                <th class="py-2 pr-4 text-right">
                  요청 (30일)
                </th>
                <th class="py-2 pr-4 text-right">
                  활동일 (30일)
                </th>
                <th class="py-2 pr-4">
                  가장 많이 쓴 기능
                </th>
                <th class="py-2 pr-4">
                  마지막 활동
                </th>
                <th class="py-2 w-8" />
              </tr>
            </thead>
            <tbody>
              <template
                v-for="row in filteredUsers"
                :key="row.user_id"
              >
                <tr
                  class="border-b border-(--sk-border) last:border-b-0 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  tabindex="0"
                  :aria-expanded="expandedUser === row.user_id"
                  @click="toggleUser(row.user_id)"
                  @keydown.enter="toggleUser(row.user_id)"
                  @keydown.space.prevent="toggleUser(row.user_id)"
                >
                  <td class="py-2.5 pr-4 font-mono font-medium text-(--sk-ink)">
                    {{ row.user_id }}
                  </td>
                  <td class="py-2.5 pr-4 text-right font-mono tabular-nums font-semibold text-(--sk-ink)">
                    {{ row.requests_30d.toLocaleString() }}
                  </td>
                  <td class="py-2.5 pr-4 text-right font-mono tabular-nums text-(--sk-ink)">
                    {{ row.days_active_30d }}
                  </td>
                  <td class="py-2.5 pr-4 text-(--sk-ink)">
                    {{ activityFeatureLabel(row.favorite_feature) }}
                  </td>
                  <td class="py-2.5 pr-4 font-mono text-(--sk-ink) tabular-nums">
                    {{ formatTime(row.last_seen) }}
                  </td>
                  <td class="py-2.5 text-zinc-400">
                    <UIcon :name="expandedUser === row.user_id ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
                  </td>
                </tr>
                <tr
                  v-if="expandedUser === row.user_id"
                  class="border-b border-(--sk-border)"
                >
                  <td
                    colspan="6"
                    class="py-3 pl-4 pr-4 bg-zinc-50/60 dark:bg-zinc-900/40"
                  >
                    <div
                      v-if="userDetailLoading"
                      class="text-sm text-zinc-500"
                    >
                      로딩 중…
                    </div>
                    <div
                      v-else-if="userDetailError"
                      class="text-sm text-rose-500"
                    >
                      불러오기 실패: {{ userDetailError }}
                    </div>
                    <div
                      v-else-if="userDetail"
                      class="grid grid-cols-1 lg:grid-cols-3 gap-4"
                    >
                      <div>
                        <div class="text-xs uppercase tracking-wider text-zinc-500 mb-2">
                          이번 달
                        </div>
                        <div class="text-2xl font-semibold tabular-nums">
                          {{ userDetail.this_month.requests }}
                        </div>
                        <div class="text-xs text-zinc-500">
                          요청 · {{ userDetail.this_month.days_active }}일 활동
                        </div>
                      </div>
                      <div class="lg:col-span-1">
                        <div class="text-xs uppercase tracking-wider text-zinc-500 mb-2">
                          자주 쓰는 기능
                        </div>
                        <ActivityFeatureBarList
                          :items="userDetail.top_features"
                          :cap="5"
                          empty-text="—"
                        />
                      </div>
                      <div>
                        <div class="text-xs uppercase tracking-wider text-zinc-500 mb-2">
                          30일 활동
                        </div>
                        <ActivitySparkline
                          :series="userDetail.daily"
                          color="from-rose-400 to-amber-500"
                        />
                      </div>
                    </div>
                  </td>
                </tr>
              </template>
              <tr v-if="filteredUsers.length === 0">
                <td
                  colspan="6"
                  class="py-10 text-center text-sm text-(--sk-ink-muted)"
                >
                  검색·필터 조건에 맞는 사용자가 없습니다.
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  fetchUserHistory,
  resetActivityCache,
  useActivityMe,
  useActivitySemModels,
  useActivitySummary,
  useActivityUsers,
  type FeatureCount,
  type SemModelCount,
  type UserListRow,
  type UserHistoryResponse
} from '~/composables/useActivityApi'
import { activityFeatureLabel, summarizePersonalActivity } from '~/utils/activity'
import { downloadCsv } from '~/utils/csvDownload'

definePageMeta({ layout: 'hub' })
useHead({ title: '사용 통계 | SKEWNONO' })

const {
  data: me,
  error: meError,
  refresh: refreshMe,
  status: meStatus
} = await useActivityMe()

// Summary + users + model breakdown are shared activity views, so every
// viewer fetches them.
const sharedQueries = await Promise.all([
  useActivitySummary(),
  useActivityUsers(),
  useActivitySemModels()
]).then(
  ([summary, users, semModels]) => ({ summary, users, semModels })
)

const summary = computed(() => sharedQueries.summary.data.value ?? null)
const users = computed(() => sharedQueries.users.data.value ?? null)
const semModels = computed(() => sharedQueries.semModels.data.value ?? null)

const loadError = computed(() => {
  const error = meError.value
    ?? sharedQueries.summary.error.value
    ?? sharedQueries.users.error.value
    ?? sharedQueries.semModels.error.value
  if (!error) return null
  return error instanceof Error ? error.message : String(error)
})

const refreshing = computed(() => {
  if (meStatus.value === 'pending') return true
  if (sharedQueries.summary.status.value === 'pending') return true
  if (sharedQueries.users.status.value === 'pending') return true
  if (sharedQueries.semModels.status.value === 'pending') return true
  return false
})

const refreshAll = async () => {
  resetActivityCache()
  const jobs: Array<Promise<unknown>> = [refreshMe()]
  jobs.push(
    sharedQueries.summary.refresh(),
    sharedQueries.users.refresh(),
    sharedQueries.semModels.refresh()
  )
  await Promise.all(jobs)
}

const myFavorite = computed(() => activityFeatureLabel(me.value?.top_features?.[0]?.feature))

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ko-KR', { hour12: false })
}

const lastSeenLabel = computed(() => formatTime(me.value?.last_seen))

const personalInsights = computed(() => summarizePersonalActivity(me.value?.daily ?? []))
const weeklyChange = computed(() => {
  const change = personalInsights.value.changePercent
  if (change === null) {
    return personalInsights.value.recent7Requests > 0
      ? { label: '새 활동', icon: 'i-lucide-sparkles', color: 'text-violet-500' }
      : { label: '변화 없음', icon: 'i-lucide-minus', color: 'text-(--sk-ink-muted)' }
  }
  if (change > 0) return { label: `+${change}%`, icon: 'i-lucide-trending-up', color: 'text-emerald-500' }
  if (change < 0) return { label: `${change}%`, icon: 'i-lucide-trending-down', color: 'text-amber-500' }
  return { label: '0%', icon: 'i-lucide-minus', color: 'text-(--sk-ink-muted)' }
})

// --- shared usage: KPI cards ---
const kpiCards = computed(() => {
  if (!summary.value) return []
  const totalRequests30d = users.value?.users.reduce((sum, row) => sum + row.requests_30d, 0) ?? 0
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
      hint: '이번 주 활동한 사용자',
      icon: 'i-lucide-users',
      color: 'text-violet-500'
    },
    {
      label: 'MAU',
      value: summary.value.mau,
      hint: '이번 달 활동한 사용자',
      icon: 'i-lucide-user-check',
      color: 'text-emerald-500'
    },
    {
      label: '30D 요청',
      value: totalRequests30d.toLocaleString(),
      hint: '전체 사용자의 요청 합계',
      icon: 'i-lucide-mouse-pointer-click',
      color: 'text-amber-500'
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

// --- shared usage: SEM List per-model breakdown ---
const modelWindowKey = ref<'7d' | '30d'>('7d')
const modelGroups = computed<{ vendor: string, rows: SemModelCount[] }[]>(() => {
  const rows = modelWindowKey.value === '7d'
    ? semModels.value?.models_7d ?? []
    : semModels.value?.models_30d ?? []
  const byVendor = new Map<string, SemModelCount[]>()
  for (const row of rows) {
    const bucket = byVendor.get(row.vendor)
    if (bucket) bucket.push(row)
    else byVendor.set(row.vendor, [row])
  }
  // Busiest vendor column first; rows arrive pre-sorted by count.
  return [...byVendor.entries()]
    .map(([vendor, vendorRows]) => ({ vendor, rows: vendorRows }))
    .sort((a, b) =>
      b.rows.reduce((s, r) => s + r.count, 0) - a.rows.reduce((s, r) => s + r.count, 0)
    )
})

// --- shared usage: user discovery controls ---
type UserSort = 'requests' | 'days' | 'recent' | 'name'

const userQuery = ref('')
const featureFilter = ref('all')
const userSort = ref<UserSort>('requests')

const userSortOptions = [
  { label: '요청 많은 순', value: 'requests' },
  { label: '활동일 많은 순', value: 'days' },
  { label: '최근 활동 순', value: 'recent' },
  { label: '사용자 이름 순', value: 'name' }
]

const featureFilterOptions = computed(() => {
  const features = new Set(
    (users.value?.users ?? [])
      .map(row => row.favorite_feature)
      .filter((feature): feature is string => Boolean(feature))
  )
  return [
    { label: '모든 기능', value: 'all' },
    ...Array.from(features)
      .sort((a, b) => activityFeatureLabel(a).localeCompare(activityFeatureLabel(b), 'ko'))
      .map(feature => ({ label: activityFeatureLabel(feature), value: feature }))
  ]
})

const filteredUsers = computed<UserListRow[]>(() => {
  const query = userQuery.value.trim().toLocaleLowerCase('ko-KR')
  const rows = (users.value?.users ?? []).filter((row) => {
    if (featureFilter.value !== 'all' && row.favorite_feature !== featureFilter.value) return false
    if (!query) return true
    const searchable = [
      row.user_id,
      row.favorite_feature ?? '',
      activityFeatureLabel(row.favorite_feature)
    ].join(' ').toLocaleLowerCase('ko-KR')
    return searchable.includes(query)
  })

  return [...rows].sort((a, b) => {
    if (userSort.value === 'days') {
      return b.days_active_30d - a.days_active_30d || b.requests_30d - a.requests_30d
    }
    if (userSort.value === 'recent') {
      const bTime = b.last_seen ? Date.parse(b.last_seen) : 0
      const aTime = a.last_seen ? Date.parse(a.last_seen) : 0
      return bTime - aTime
    }
    if (userSort.value === 'name') return a.user_id.localeCompare(b.user_id)
    return b.requests_30d - a.requests_30d || a.user_id.localeCompare(b.user_id)
  })
})

const hasActiveUserControls = computed(() =>
  Boolean(userQuery.value) || featureFilter.value !== 'all' || userSort.value !== 'requests'
)

const resetUserControls = () => {
  userQuery.value = ''
  featureFilter.value = 'all'
  userSort.value = 'requests'
}

const downloadUsersCsv = () => {
  const date = new Date().toISOString().slice(0, 10)
  downloadCsv(
    `activity-users-${date}.csv`,
    ['사용자', '요청 (30일)', '활동일 (30일)', '가장 많이 쓴 기능', '기능 키', '마지막 활동'],
    filteredUsers.value.map(row => [
      row.user_id,
      row.requests_30d,
      row.days_active_30d,
      activityFeatureLabel(row.favorite_feature),
      row.favorite_feature,
      row.last_seen
    ])
  )
}

// --- shared usage: user table drill-down ---
const expandedUser = ref<string | null>(null)
const userDetail = ref<UserHistoryResponse | null>(null)
const userDetailLoading = ref(false)
const userDetailError = ref<string | null>(null)

const toggleUser = async (userId: string) => {
  if (expandedUser.value === userId) {
    expandedUser.value = null
    userDetail.value = null
    userDetailError.value = null
    return
  }
  expandedUser.value = userId
  userDetail.value = null
  userDetailError.value = null
  userDetailLoading.value = true
  try {
    userDetail.value = await fetchUserHistory(userId)
  } catch (err) {
    userDetailError.value = err instanceof Error ? err.message : String(err)
  } finally {
    userDetailLoading.value = false
  }
}
</script>
