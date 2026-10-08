<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 class="sk-page-title flex items-center gap-2">
          <UIcon
            name="i-lucide-user-round-search"
            class="text-sky-500"
          />
          방문자 분석
          <UBadge
            color="warning"
            variant="subtle"
            size="sm"
          >
            관리자 전용
          </UBadge>
        </h1>
        <p class="sk-meta mt-1">
          DAU·WAU·MAU 추이와 누가 얼마나 자주 방문하는지 보여줍니다.
        </p>
      </div>
      <div class="flex items-center gap-1">
        <!-- The way back: this page is not in the nav, and 사용 통계's 관리자
             도구 card is the only link that leads here. -->
        <UButton
          to="/activity"
          icon="i-lucide-arrow-left"
          color="neutral"
          variant="ghost"
        >
          사용 통계
        </UButton>
        <UButton
          v-if="!blocked"
          :loading="refreshing"
          icon="i-lucide-refresh-cw"
          color="neutral"
          variant="ghost"
          @click="refreshAll"
        >
          새로고침
        </UButton>
      </div>
    </header>

    <section
      v-if="blocked"
      class="dashboard-surface rounded-lg border border-(--sk-border) p-6 text-center sk-body"
    >
      관리자만 접근할 수 있는 페이지입니다.
    </section>

    <template v-else>
      <UAlert
        v-if="loadError"
        color="error"
        variant="subtle"
        icon="i-lucide-circle-alert"
        title="일부 방문자 데이터를 불러오지 못했습니다."
        :description="loadError"
        :actions="[{ label: '다시 시도', onClick: refreshAll }]"
      />

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

      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-trending-up" />
              방문자 추이
              <!-- Says what the lines are: a rolling count ending on each day,
                   not a calendar week or month, so the last point is the KPI
                   card above it. -->
              <span class="sk-meta font-normal">· WAU·MAU는 그날까지의 7일·30일 누적 사용자</span>
            </span>
            <div class="flex items-center gap-2">
              <UTabs
                v-model="metricKey"
                :items="VISITOR_METRIC_TABS"
                variant="pill"
                size="xs"
              />
              <UTabs
                v-model="windowKey"
                :items="VISITOR_WINDOW_TABS"
                variant="pill"
                size="xs"
              />
            </div>
          </div>
        </template>
        <ActivityVisitorsChart
          :series="windowDays"
          :metric="metricKey"
        />
      </UCard>

      <!-- All three read the same 30-day users list the table below shows. -->
      <section class="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <UCard class="dashboard-surface">
          <template #header>
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-trophy" />
              자주 방문하는 사용자 Top 10
              <span class="sk-meta font-normal">· 활동일 (30일)</span>
            </span>
          </template>
          <ActivityCountBarList
            :items="topVisitors"
            unit="일"
            empty-text="아직 데이터가 없습니다."
          />
        </UCard>

        <UCard class="dashboard-surface">
          <template #header>
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-chart-column" />
              방문 빈도 분포
              <span class="sk-meta font-normal">· 30일 중 방문한 날 수</span>
            </span>
          </template>
          <ActivityCountBarList
            :items="frequencyBuckets"
            unit="명"
          />
        </UCard>

        <UCard class="dashboard-surface">
          <template #header>
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-building-2" />
              팀별 방문자
              <!-- The list caps at ten; the count says when it is not all of them. -->
              <span class="sk-meta font-normal">· {{ teams.length }}개 팀 (30일)</span>
            </span>
          </template>
          <ActivityCountBarList
            :items="teams"
            unit="명"
            empty-text="아직 데이터가 없습니다."
          />
        </UCard>
      </section>

      <ActivityUserTable :users="users" />
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  resetActivityCache,
  useActivityUsers,
  useActivityVisitors
} from '~/composables/useActivityApi'
import { activeUserKpis } from '~/utils/activity'
import {
  VISITOR_METRIC_TABS,
  VISITOR_WINDOW_TABS,
  frequentVisitors,
  stickinessPercent,
  visitFrequencyBuckets,
  visitorWindow,
  visitorsByTeam,
  type VisitorMetricKey,
  type VisitorWindowKey
} from '~/utils/activityVisitors'
import { operationalDataErrorMessage } from '~/utils/operationalDataError'

useHead({ title: '방문자 분석 | SKEWNONO' })

// The route middleware has already asked /api/me who this is, and its
// `is_admin` is the same decision the backend's admin gate makes. So only a
// caller KNOWN not to be an admin is turned away here. When the identity could
// not be fetched at all, the queries are issued anyway and the backend's own
// answer — a 403, or the outage — shows in the alert below, which has a retry.
// Asking /activity/me for one boolean cost a request and a second way to fail.
const { identity } = useIdentity()
const blocked = computed(() => identity.value !== null && !identity.value.is_admin)

const [usersQuery, visitorsQuery] = blocked.value
  ? [null, null]
  : await Promise.all([useActivityUsers(), useActivityVisitors()])

const users = computed(() => usersQuery?.data.value ?? null)
const days = computed(() => visitorsQuery?.data.value?.days ?? [])

const loadError = computed(() => {
  const error = usersQuery?.error.value ?? visitorsQuery?.error.value
  if (!error) return null
  return operationalDataErrorMessage(error, '방문자 데이터를 불러오지 못했습니다.')
})

const refreshing = computed(() =>
  usersQuery?.status.value === 'pending' || visitorsQuery?.status.value === 'pending'
)

const refreshAll = async () => {
  resetActivityCache()
  await Promise.all([usersQuery?.refresh(), visitorsQuery?.refresh()])
}

// --- KPI row: the trend's last day, so the cards and the chart cannot disagree ---
const kpiCards = computed(() => {
  const today = days.value[days.value.length - 1]
  if (!today) return []
  const stickiness = stickinessPercent(today)
  const requests30d = users.value?.users.reduce((sum, row) => sum + row.requests_30d, 0)
  return [
    ...activeUserKpis({ dau: today.visitors, wau: today.wau, mau: today.mau }),
    {
      label: 'DAU / MAU',
      value: stickiness === null ? '—' : `${stickiness}%`,
      hint: '월간 사용자 중 오늘 방문한 비율',
      icon: 'i-lucide-repeat-2',
      color: 'text-rose-500'
    },
    ...(requests30d === undefined
      ? []
      : [{
          label: '30D 요청',
          value: requests30d.toLocaleString(),
          hint: '전체 사용자의 요청 합계',
          icon: 'i-lucide-mouse-pointer-click',
          color: 'text-amber-500'
        }])
  ]
})

// --- trend metric and window toggles ---
const metricKey = ref<VisitorMetricKey>('dau')
const windowKey = ref<VisitorWindowKey>('2w')
const windowDays = computed(() => visitorWindow(days.value, windowKey.value))

// --- who visits, how often, from where ---
const userRows = computed(() => users.value?.users ?? [])
const topVisitors = computed(() => frequentVisitors(userRows.value))
const frequencyBuckets = computed(() => visitFrequencyBuckets(userRows.value))
const teams = computed(() => visitorsByTeam(userRows.value))
</script>
