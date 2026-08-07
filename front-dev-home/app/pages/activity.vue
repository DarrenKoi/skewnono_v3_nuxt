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
          최근 활동, 자주 쓰는 기능, 전체 사용 추이를 보여줍니다.
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
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
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
          <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
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
            <span class="sk-meta">
              최근 30일 기준
            </span>
          </div>
        </template>
        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums">
              {{ personalInsights.recent7Requests.toLocaleString() }}
            </div>
            <div class="sk-meta">
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
            <div class="sk-meta">
              이전 7일 대비
            </div>
          </div>
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums">
              {{ personalInsights.activeDays7 }}<span class="text-sm font-normal text-(--sk-ink-muted)"> / 7일</span>
            </div>
            <div class="sk-meta">
              최근 활동일
            </div>
          </div>
          <div>
            <div class="text-2xl font-semibold font-mono tabular-nums">
              {{ personalInsights.averagePerActiveDay30.toLocaleString() }}
            </div>
            <div class="sk-meta">
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
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-factory" />
              Fab별 페이지 사용
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

      <!-- Admin tools: the two /admin pages are deliberately kept out of the
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
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
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

      <!-- Users table: per-employee rows are admin-only (backend returns 403) -->
      <UCard
        v-if="isAdmin"
        class="dashboard-surface"
      >
        <template #header>
          <div class="flex items-center justify-between gap-3">
            <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
              <UIcon name="i-lucide-users" />
              사용자
            </span>
            <div class="flex items-center gap-2">
              <UBadge
                color="warning"
                variant="subtle"
                size="sm"
              >
                관리자 전용
              </UBadge>
              <UBadge
                color="neutral"
                variant="subtle"
              >
                {{ filteredUsers.length }} / {{ users?.users.length ?? 0 }}
              </UBadge>
              <span
                v-if="users"
                class="sk-meta"
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
            placeholder="이름·사번·팀 또는 기능 검색"
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
          <UTooltip text="클립보드 복사">
            <UButton
              size="sm"
              color="neutral"
              variant="outline"
              icon="i-lucide-clipboard"
              aria-label="표를 클립보드에 복사"
              :disabled="filteredUsers.length === 0"
              @click="copyUsersTable"
            />
          </UTooltip>
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
            icon="i-lucide-refresh-cw"
            label="새로고침"
            :disabled="!hasActiveUserControls"
            @click="resetUserControls"
          />
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left sk-eyebrow border-b border-(--sk-border)">
                <th class="py-2 pr-4">
                  사용자
                </th>
                <th class="py-2 pr-4">
                  팀
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
                  <!-- Name leads, employee number underneath rather than
                       instead of: every other screen and the activity log
                       itself key on the empno, so it has to stay readable.
                       No second line when there is no name — the id is
                       already the first one. -->
                  <td class="py-2.5 pr-4">
                    <div class="sk-value">
                      {{ userDisplayName(row) }}
                    </div>
                    <div
                      v-if="row.emp_nm"
                      class="sk-meta"
                    >
                      {{ row.user_id }}
                    </div>
                  </td>
                  <!-- Its own column rather than a third line under the name:
                       the team is a different axis from "who is this", and a
                       column is what an admin scans down to compare orgs. -->
                  <td class="py-2.5 pr-4 sk-value">
                    {{ userTeamLabel(row) }}
                  </td>
                  <td class="py-2.5 pr-4 text-right sk-value-num">
                    {{ row.requests_30d.toLocaleString() }}
                  </td>
                  <td class="py-2.5 pr-4 text-right sk-value-num">
                    {{ row.days_active_30d }}
                  </td>
                  <td class="py-2.5 pr-4 sk-value">
                    {{ activityFeatureLabel(row.favorite_feature) }}
                  </td>
                  <td class="py-2.5 pr-4 sk-value-num">
                    {{ formatTime(row.last_seen) }}
                  </td>
                  <td class="py-2.5 text-(--sk-ink-muted)">
                    <UIcon :name="expandedUser === row.user_id ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'" />
                  </td>
                </tr>
                <tr
                  v-if="expandedUser === row.user_id"
                  class="border-b border-(--sk-border)"
                >
                  <td
                    colspan="7"
                    class="py-3 pl-4 pr-4 bg-zinc-50/60 dark:bg-zinc-900/40"
                  >
                    <div
                      v-if="userDetailLoading"
                      class="sk-body"
                    >
                      로딩 중…
                    </div>
                    <div
                      v-else-if="userDetailError"
                      class="sk-body text-rose-500"
                    >
                      불러오기 실패: {{ userDetailError }}
                    </div>
                    <div
                      v-else-if="userDetail"
                      class="grid grid-cols-1 lg:grid-cols-3 gap-4"
                    >
                      <div>
                        <div class="sk-eyebrow mb-2">
                          이번 달
                        </div>
                        <div class="text-2xl font-semibold tabular-nums">
                          {{ userDetail.this_month.requests }}
                        </div>
                        <div class="sk-meta">
                          요청 · {{ userDetail.this_month.days_active }}일 활동
                        </div>
                      </div>
                      <div class="lg:col-span-1">
                        <div class="sk-eyebrow mb-2">
                          자주 쓰는 기능
                        </div>
                        <ActivityFeatureBarList
                          :items="userDetail.top_features"
                          :cap="5"
                          empty-text="—"
                        />
                      </div>
                      <div>
                        <div class="sk-eyebrow mb-2">
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
                  colspan="7"
                  class="py-10 text-center sk-body"
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
  resetActivityCache,
  useActivityMe,
  useActivityFabs,
  useActivitySummary,
  useActivityUsers,
  type FeatureCount,
  type FabUsageRow
} from '~/composables/useActivityApi'
import { activityFeatureLabel, summarizePersonalActivity, pageViewNotice, userDisplayName, userTeamLabel } from '~/utils/activity'
import { displayName, isUnverifiedDeclaration } from '~/utils/identityDisplay'
import { operationalDataErrorMessage } from '~/utils/operationalDataError'

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
// them. The users list is admin-only on the backend (403 otherwise), so it is
// fetched only when /activity/me says the viewer is an admin.
const sharedQueries = await Promise.all([
  useActivitySummary(),
  useActivityFabs()
]).then(
  ([summary, fabs]) => ({ summary, fabs })
)
const usersQuery = isAdmin.value ? await useActivityUsers() : null

const summary = computed(() => sharedQueries.summary.data.value ?? null)
const users = computed(() => usersQuery?.data.value ?? null)
const fabs = computed(() => sharedQueries.fabs.data.value ?? null)

const loadError = computed(() => {
  const error = meError.value
    ?? sharedQueries.summary.error.value
    ?? usersQuery?.error.value
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
  if (usersQuery?.status.value === 'pending') return true
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
  if (usersQuery) jobs.push(usersQuery.refresh())
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
  // The request total is derived from the admin-only users list, so it is
  // dropped rather than shown as 0 for a viewer who cannot fetch it.
  const totalRequests30d = users.value
    ? users.value.users.reduce((sum, row) => sum + row.requests_30d, 0)
    : null
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
    ...(totalRequests30d === null
      ? []
      : [{
          label: '30D 요청',
          value: totalRequests30d.toLocaleString(),
          hint: '전체 사용자의 요청 합계',
          icon: 'i-lucide-mouse-pointer-click',
          color: 'text-amber-500'
        }]),
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
  fabWindowKey.value === '7d'
    ? fabs.value?.fabs_7d ?? []
    : fabs.value?.fabs_30d ?? []
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

const userRows = computed(() => users.value?.users ?? [])
const {
  query: userQuery,
  featureFilter,
  sort: userSort,
  sortOptions: userSortOptions,
  featureFilterOptions,
  filteredRows: filteredUsers,
  hasActiveControls: hasActiveUserControls,
  resetControls: resetUserControls,
  download: downloadUsersCsv,
  copy: copyUsersTable,
  expandedUser,
  userDetail,
  userDetailLoading,
  userDetailError,
  toggleUser
} = useActivityUserTable(userRows)
</script>
