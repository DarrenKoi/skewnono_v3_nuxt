<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 class="sk-page-title flex items-center gap-2">
          <UIcon
            name="i-lucide-route"
            class="text-(--sk-ink-muted)"
          />
          엔드포인트 분석
          <UBadge
            color="warning"
            variant="subtle"
            size="sm"
          >
            관리자 전용
          </UBadge>
        </h1>
        <!-- The opposite scope of 요청 분석: that page keeps user intent only,
             this one is the server's load, so everything counts. -->
        <p class="sk-meta mt-1">
          서버가 받은 모든 /api 호출 건수입니다. 백그라운드 갱신·실패한 요청·API Token·익명 호출까지 모두 셉니다. 경로의 id 부분은 하나의 엔드포인트로 묶습니다.
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
          :loading="query?.status.value === 'pending'"
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
        title="호출 데이터를 불러오지 못했습니다."
        :description="loadError"
        :actions="[{ label: '다시 시도', onClick: refreshAll }]"
      />
      <UAlert
        v-if="stats?.truncated"
        color="warning"
        variant="subtle"
        icon="i-lucide-triangle-alert"
        title="기록이 많아 일부만 집계했습니다."
        description="가장 오래된 날짜의 수치가 실제보다 적을 수 있습니다."
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
              <UIcon name="i-lucide-chart-column-stacked" />
              일별 호출 추이
              <span class="sk-meta font-normal">· 기간 내 상위 5개 엔드포인트 + 기타, KST 기준, 오늘은 진행 중</span>
            </span>
            <UTabs
              v-model="windowKey"
              :items="VISITOR_WINDOW_TABS"
              variant="pill"
              size="xs"
            />
          </div>
        </template>
        <ActivityEndpointsChart :series="windowDays" />
      </UCard>

      <!-- Both rankings follow the chart's tab, so the three cards always
           describe the same days. -->
      <section class="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <UCard class="dashboard-surface">
          <template #header>
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-list-ordered" />
              호출이 많은 엔드포인트 Top 10
              <span class="sk-meta font-normal">· {{ windowLabel }}</span>
            </span>
          </template>
          <ActivityCountBarList
            :items="endpointRows"
            unit="건"
            empty-text="아직 데이터가 없습니다."
          />
        </UCard>

        <UCard class="dashboard-surface">
          <template #header>
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-trophy" />
              호출이 많은 사용자 Top 10
              <span class="sk-meta font-normal">· {{ windowLabel }}</span>
            </span>
          </template>
          <ActivityCountBarList
            :items="callerRows"
            unit="건"
            empty-text="아직 데이터가 없습니다."
          />
        </UCard>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { resetActivityCache, useActivityEndpoints } from '~/composables/useActivityApi'
import { endpointKpis, topCallers, topEndpoints } from '~/utils/activityEndpoints'
import { VISITOR_WINDOW_TABS, visitorWindow, type VisitorWindowKey } from '~/utils/activityVisitors'
import { operationalDataErrorMessage } from '~/utils/operationalDataError'

useHead({ title: '엔드포인트 분석 | SKEWNONO' })

// Same gate as 요청 분석: only a caller KNOWN not to be an admin is turned
// away here; otherwise the backend's own 403 or outage shows in the alert.
const { identity } = useIdentity()
const blocked = computed(() => identity.value !== null && !identity.value.is_admin)

const query = blocked.value ? null : await useActivityEndpoints()

const stats = computed(() => query?.data.value ?? null)
const days = computed(() => stats.value?.days ?? [])

const loadError = computed(() => {
  const error = query?.error.value
  return error ? operationalDataErrorMessage(error, '호출 데이터를 불러오지 못했습니다.') : null
})

const refreshAll = async () => {
  resetActivityCache()
  await query?.refresh()
}

const kpiCards = computed(() => endpointKpis(days.value))

const windowKey = ref<VisitorWindowKey>('1m')
const windowDays = computed(() => visitorWindow(days.value, windowKey.value))
const windowLabel = computed(() => VISITOR_WINDOW_TABS.find(tab => tab.value === windowKey.value)?.label ?? '')

const endpointRows = computed(() => topEndpoints(windowDays.value))
const callerRows = computed(() => topCallers(windowDays.value, stats.value?.names ?? {}))
</script>
