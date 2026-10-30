<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 class="sk-page-title flex items-center gap-2">
          <UIcon
            name="i-lucide-activity"
            class="text-(--sk-ink-muted)"
          />
          요청 분석
          <UBadge
            color="warning"
            variant="subtle"
            size="sm"
          >
            관리자 전용
          </UBadge>
        </h1>
        <!-- Says what a 요청 is, because the obvious reading — every HTTP
             call — is not it, and the gap is large (polling, failures). -->
        <p class="sk-meta mt-1">
          사용자가 화면에서 보낸 API 요청 건수입니다. 페이지 열람·실패한 요청·API Token 호출·백그라운드 갱신·익명 요청은 세지 않습니다.
        </p>
      </div>
      <div class="flex items-center gap-1">
        <UButton
          to="/admin"
          icon="i-lucide-arrow-left"
          color="neutral"
          variant="ghost"
        >
          관리자 도구
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
        title="일부 요청 데이터를 불러오지 못했습니다."
        :description="loadError"
        :actions="[{ label: '다시 시도', onClick: refreshAll }]"
      />

      <section
        v-if="days.length"
        class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4"
      >
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
              <UIcon name="i-lucide-chart-column" />
              일별 요청 추이
              <!-- Today's bar is a day still in progress; said so it is not
                   read as a drop. -->
              <span class="sk-meta font-normal">· KST 기준, 오늘은 진행 중</span>
            </span>
            <UTabs
              v-model="windowKey"
              :items="VISITOR_WINDOW_TABS"
              variant="pill"
              size="xs"
            />
          </div>
        </template>
        <ActivityRequestsChart :series="windowDays" />
      </UCard>

      <section class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <UCard class="dashboard-surface">
          <template #header>
            <div class="flex items-center justify-between gap-3">
              <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
                <UIcon name="i-lucide-list-ordered" />
                기능별 요청 Top 10
                <!-- Not 사용 통계's 인기 기능: that one ranks page opens. -->
                <span class="sk-meta font-normal">· 페이지 열람 수가 아닌 요청 건수</span>
              </span>
              <UTabs
                v-model="featureWindowKey"
                :items="RANKING_WINDOW_TABS"
                variant="pill"
                size="xs"
              />
            </div>
          </template>
          <ActivityFeatureBarList
            :items="featureWindow?.features ?? []"
            empty-text="아직 데이터가 없습니다."
          />
          <p
            v-if="remainderNote"
            class="mt-2 text-xs text-(--sk-ink-subtle)"
          >
            {{ remainderNote }}
          </p>
        </UCard>

        <UCard class="dashboard-surface">
          <template #header>
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-trophy" />
              요청이 많은 사용자 Top 10
              <span class="sk-meta font-normal">· 요청 (30일)</span>
            </span>
          </template>
          <ActivityCountBarList
            :items="requesters"
            unit="건"
            empty-text="아직 데이터가 없습니다."
          />
        </UCard>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  resetActivityCache,
  useActivityRequests,
  useActivityUsers
} from '~/composables/useActivityApi'
import { RANKING_WINDOW_TABS, type RankingWindowKey } from '~/utils/activity'
import { requestKpis, requestRemainderNote, topRequesters } from '~/utils/activityRequests'
import { VISITOR_WINDOW_TABS, visitorWindow, type VisitorWindowKey } from '~/utils/activityVisitors'
import { operationalDataErrorMessage } from '~/utils/operationalDataError'

useHead({ title: '요청 분석 | SKEWNONO' })

// Same gate as 방문자 분석: only a caller KNOWN not to be an admin is turned
// away here; otherwise the backend's own 403 or outage shows in the alert.
const { identity } = useIdentity()
const blocked = computed(() => identity.value !== null && !identity.value.is_admin)

const [requestsQuery, usersQuery] = blocked.value
  ? [null, null]
  : await Promise.all([useActivityRequests(), useActivityUsers()])

const stats = computed(() => requestsQuery?.data.value ?? null)
const days = computed(() => stats.value?.days ?? [])

const loadError = computed(() => {
  const error = requestsQuery?.error.value ?? usersQuery?.error.value
  if (!error) return null
  return operationalDataErrorMessage(error, '요청 데이터를 불러오지 못했습니다.')
})

const refreshing = computed(() =>
  requestsQuery?.status.value === 'pending' || usersQuery?.status.value === 'pending'
)

const refreshAll = async () => {
  resetActivityCache()
  await Promise.all([requestsQuery?.refresh(), usersQuery?.refresh()])
}

const kpiCards = computed(() => requestKpis(days.value))

const windowKey = ref<VisitorWindowKey>('1m')
const windowDays = computed(() => visitorWindow(days.value, windowKey.value))

const featureWindowKey = ref<RankingWindowKey>('7d')
const featureWindow = computed(() => stats.value?.[`window_${featureWindowKey.value}`])
const remainderNote = computed(() => requestRemainderNote(featureWindow.value))

const requesters = computed(() => topRequesters(usersQuery?.data.value?.users ?? []))
</script>
