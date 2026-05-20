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
        <p class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
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
      <section class="grid grid-cols-1 sm:grid-cols-3 gap-4">
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

      <!-- Users table -->
      <UCard class="dashboard-surface">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
              <UIcon name="i-lucide-users" />
              사용자 ({{ users?.users.length ?? 0 }})
            </span>
            <span
              v-if="users"
              class="text-xs text-zinc-500"
            >
              {{ formatTime(users.generated_at) }}
            </span>
          </div>
        </template>
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
                v-for="row in users?.users ?? []"
                :key="row.user_id"
              >
                <tr
                  class="border-b border-(--sk-border) last:border-b-0 cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-800/50"
                  @click="toggleUser(row.user_id)"
                >
                  <td class="py-2.5 pr-4 font-medium">
                    {{ row.user_id }}
                  </td>
                  <td class="py-2.5 pr-4 text-right tabular-nums font-semibold">
                    {{ row.requests_30d }}
                  </td>
                  <td class="py-2.5 pr-4 text-right tabular-nums">
                    {{ row.days_active_30d }}
                  </td>
                  <td class="py-2.5 pr-4 text-zinc-600 dark:text-zinc-400">
                    {{ row.favorite_feature ?? '—' }}
                  </td>
                  <td class="py-2.5 pr-4 text-zinc-500 tabular-nums">
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
  useActivitySummary,
  useActivityUsers,
  type FeatureCount,
  type UserHistoryResponse
} from '~/composables/useActivityApi'

definePageMeta({ layout: 'hub' })
useHead({ title: '사용 통계 | SKEWNONO' })

const { data: me, refresh: refreshMe, status: meStatus } = await useActivityMe()

// Summary + users are shared activity views, so every viewer fetches them.
const sharedQueries = await Promise.all([useActivitySummary(), useActivityUsers()]).then(
  ([summary, users]) => ({ summary, users })
)

const summary = computed(() => sharedQueries.summary.data.value ?? null)
const users = computed(() => sharedQueries.users.data.value ?? null)

const refreshing = computed(() => {
  if (meStatus.value === 'pending') return true
  if (sharedQueries.summary.status.value === 'pending') return true
  if (sharedQueries.users.status.value === 'pending') return true
  return false
})

const refreshAll = async () => {
  resetActivityCache()
  const jobs: Array<Promise<unknown>> = [refreshMe()]
  jobs.push(sharedQueries.summary.refresh(), sharedQueries.users.refresh())
  await Promise.all(jobs)
}

const myFavorite = computed(() => me.value?.top_features?.[0]?.feature ?? '—')

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ko-KR', { hour12: false })
}

const lastSeenLabel = computed(() => formatTime(me.value?.last_seen))

// --- shared usage: KPI cards ---
const kpiCards = computed(() => {
  if (!summary.value) return []
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
