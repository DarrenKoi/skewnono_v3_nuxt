<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header class="flex items-end justify-between flex-wrap gap-4">
      <div>
        <h1 class="text-3xl font-bold flex items-center gap-2">
          <UIcon
            name="i-lucide-trophy"
            class="text-amber-500"
          />
          내 활동 / 리더보드
        </h1>
        <p class="text-sm text-zinc-500 dark:text-zinc-400 mt-1">
          API 호출이 곧 점수입니다. 많이 둘러볼수록 등급이 올라갑니다.
        </p>
      </div>
      <UButton
        :loading="meRefreshing || lbRefreshing"
        icon="i-lucide-refresh-cw"
        color="neutral"
        variant="ghost"
        @click="refreshAll"
      >
        새로고침
      </UButton>
    </header>

    <section
      v-if="me"
      class="grid grid-cols-1 lg:grid-cols-3 gap-4"
    >
      <UCard class="dashboard-surface lg:col-span-2">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
              내 등급
            </span>
            <UBadge
              :color="tierColor(me.tier.current.key)"
              variant="subtle"
              size="lg"
            >
              <UIcon
                :name="tierIconName(me.tier.current.icon)"
                class="mr-1"
              />
              {{ me.tier.current.label }}
            </UBadge>
          </div>
        </template>

        <div class="flex items-center gap-4">
          <div
            class="w-16 h-16 rounded-full bg-gradient-to-br from-amber-400 to-rose-500 flex items-center justify-center text-white text-xl font-bold shadow-md"
          >
            {{ avatarInitials(me.user_id) }}
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-xl font-semibold truncate">
              {{ me.user_id }}
            </div>
            <div class="text-sm text-zinc-500 dark:text-zinc-400">
              전체 {{ me.stats.total_users }}명 중
              <span class="font-semibold text-zinc-900 dark:text-zinc-100">
                #{{ me.stats.rank }}
              </span>
            </div>
          </div>
          <div class="text-right">
            <div class="text-3xl font-bold tabular-nums">
              {{ me.stats.score }}
            </div>
            <div class="text-xs uppercase tracking-wider text-zinc-500">
              점
            </div>
          </div>
        </div>

        <div
          v-if="me.tier.next"
          class="mt-5"
        >
          <div class="flex items-center justify-between text-xs text-zinc-500 mb-1.5">
            <span>
              다음 등급:
              <span class="font-medium text-zinc-700 dark:text-zinc-200">
                {{ me.tier.next.label }}
              </span>
            </span>
            <span class="tabular-nums">
              {{ me.tier.score_to_next }}점 남음
            </span>
          </div>
          <div class="h-2 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
            <div
              class="h-full bg-gradient-to-r from-amber-400 to-rose-500 transition-all"
              :style="{ width: `${me.tier.pct}%` }"
            />
          </div>
        </div>
        <div
          v-else
          class="mt-5 text-sm text-amber-600 dark:text-amber-400 flex items-center gap-1.5"
        >
          <UIcon name="i-lucide-crown" />
          최고 등급에 도달했습니다.
        </div>
      </UCard>

      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400">
            한눈에 보기
          </span>
        </template>
        <div class="grid grid-cols-2 gap-4">
          <ActivityStatCell
            icon="i-lucide-flame"
            color="text-orange-500"
            :value="me.stats.streak_days"
            label="연속 활동일"
            unit="일"
          />
          <ActivityStatCell
            icon="i-lucide-calendar-check"
            color="text-emerald-500"
            :value="me.stats.days_active"
            label="누적 활동일"
            unit="일"
          />
          <ActivityStatCell
            icon="i-lucide-sparkles"
            color="text-violet-500"
            :value="me.stats.favorite_feature ?? '—'"
            label="가장 많이 쓴 기능"
          />
          <ActivityStatCell
            icon="i-lucide-clock"
            color="text-sky-500"
            :value="lastSeenLabel"
            label="마지막 활동"
          />
        </div>
      </UCard>
    </section>

    <section class="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <UCard class="dashboard-surface lg:col-span-2">
        <template #header>
          <div class="flex items-center justify-between">
            <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
              <UIcon name="i-lucide-list-ordered" />
              리더보드 Top {{ leaderboard?.top.length ?? 0 }}
            </span>
            <span
              v-if="leaderboard"
              class="text-xs text-zinc-500"
            >
              {{ formatTime(leaderboard.generated_at) }}
            </span>
          </div>
        </template>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-zinc-500 border-b border-(--sk-border)">
                <th class="py-2 pr-4 w-12">
                  순위
                </th>
                <th class="py-2 pr-4">
                  사용자
                </th>
                <th class="py-2 pr-4">
                  등급
                </th>
                <th class="py-2 pr-4 text-right">
                  점수
                </th>
                <th class="py-2 text-right">
                  연속 활동일
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="row in leaderboard?.top ?? []"
                :key="row.user_id"
                :class="['border-b border-(--sk-border) last:border-b-0', row.is_me ? 'bg-amber-50/60 dark:bg-amber-500/10' : '']"
              >
                <td class="py-2.5 pr-4 font-semibold tabular-nums">
                  {{ rankLabel(row.rank) }}
                </td>
                <td class="py-2.5 pr-4">
                  <span class="font-medium">{{ row.user_id }}</span>
                  <UBadge
                    v-if="row.is_me"
                    color="warning"
                    variant="subtle"
                    size="sm"
                    class="ml-2"
                  >
                    나
                  </UBadge>
                </td>
                <td class="py-2.5 pr-4">
                  <UBadge
                    :color="tierColor(row.tier)"
                    variant="subtle"
                    size="sm"
                  >
                    {{ tierLabel(row.tier) }}
                  </UBadge>
                </td>
                <td class="py-2.5 pr-4 text-right tabular-nums font-semibold">
                  {{ row.score }}
                </td>
                <td class="py-2.5 text-right tabular-nums text-zinc-600 dark:text-zinc-400">
                  <UIcon
                    name="i-lucide-flame"
                    class="text-orange-500 mr-0.5"
                  />
                  {{ row.streak_days }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div
          v-if="leaderboard?.me"
          class="mt-4 pt-3 border-t border-dashed border-(--sk-border) flex items-center gap-3 text-sm"
        >
          <UIcon
            name="i-lucide-corner-down-right"
            class="text-zinc-400"
          />
          <span class="text-zinc-500">Top 밖이지만 본인은</span>
          <span class="font-semibold tabular-nums">
            #{{ leaderboard.me.rank }}
          </span>
          <span class="tabular-nums">
            ({{ leaderboard.me.score }}점)
          </span>
        </div>
      </UCard>

      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
            <UIcon name="i-lucide-pie-chart" />
            기능별 사용
          </span>
        </template>
        <div
          v-if="me && featureBreakdown.length"
          class="space-y-2.5"
        >
          <div
            v-for="row in featureBreakdown"
            :key="row.feature"
            class="space-y-1"
          >
            <div class="flex items-center justify-between text-xs">
              <span class="font-medium text-zinc-700 dark:text-zinc-200">
                {{ row.feature }}
              </span>
              <span class="text-zinc-500 tabular-nums">
                {{ row.count }} ({{ row.pct }}%)
              </span>
            </div>
            <div class="h-1.5 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
              <div
                class="h-full bg-gradient-to-r from-sky-400 to-violet-500"
                :style="{ width: `${row.pct}%` }"
              />
            </div>
          </div>
        </div>
        <div
          v-else
          class="text-sm text-zinc-500"
        >
          아직 기록된 활동이 없습니다.
        </div>
      </UCard>
    </section>

    <section v-if="me?.recent.length">
      <UCard class="dashboard-surface">
        <template #header>
          <span class="text-sm font-medium text-zinc-500 dark:text-zinc-400 flex items-center gap-1.5">
            <UIcon name="i-lucide-history" />
            최근 활동 ({{ me.recent.length }})
          </span>
        </template>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-xs uppercase tracking-wider text-zinc-500 border-b border-(--sk-border)">
                <th class="py-2 pr-4">
                  시각
                </th>
                <th class="py-2 pr-4">
                  기능
                </th>
                <th class="py-2 pr-4">
                  메서드
                </th>
                <th class="py-2 pr-4">
                  경로
                </th>
                <th class="py-2 text-right">
                  상태
                </th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="(row, idx) in me.recent.slice(0, 20)"
                :key="`${row.timestamp}-${idx}`"
                class="border-b border-(--sk-border) last:border-b-0"
              >
                <td class="py-2 pr-4 text-zinc-500 tabular-nums">
                  {{ formatTime(row.timestamp) }}
                </td>
                <td class="py-2 pr-4 font-medium">
                  {{ row.feature }}
                </td>
                <td class="py-2 pr-4 font-mono text-xs">
                  {{ row.method }}
                </td>
                <td class="py-2 pr-4 font-mono text-xs text-zinc-600 dark:text-zinc-400 truncate max-w-md">
                  {{ row.path }}
                </td>
                <td class="py-2 text-right tabular-nums">
                  {{ row.status }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </UCard>
    </section>
  </div>
</template>

<script setup lang="ts">
import {
  useActivityLeaderboard,
  useActivityMe,
  type Tier
} from '~/composables/useActivityApi'

definePageMeta({ layout: 'hub' })
useHead({ title: '내 활동 | SKEWNONO' })

const { data: me, refresh: refreshMe, status: meStatus } = await useActivityMe()
const { data: leaderboard, refresh: refreshLeaderboard, status: lbStatus } = await useActivityLeaderboard()

const meRefreshing = computed(() => meStatus.value === 'pending')
const lbRefreshing = computed(() => lbStatus.value === 'pending')

const refreshAll = async () => {
  await Promise.all([refreshMe(), refreshLeaderboard()])
}

const TIER_COLORS: Record<Tier, 'neutral' | 'info' | 'warning' | 'primary' | 'success'> = {
  bronze: 'neutral',
  silver: 'info',
  gold: 'warning',
  platinum: 'primary',
  diamond: 'success'
}

const TIER_LABELS: Record<Tier, string> = {
  bronze: 'Bronze',
  silver: 'Silver',
  gold: 'Gold',
  platinum: 'Platinum',
  diamond: 'Diamond'
}

const tierColor = (tier: Tier) => TIER_COLORS[tier]
const tierLabel = (tier: Tier) => TIER_LABELS[tier]
const tierIconName = (icon: string) => `i-lucide-${icon}`

const avatarInitials = (userId: string) => {
  if (!userId) return '?'
  const cleaned = userId.replace(/[^a-zA-Z0-9가-힣]/g, '')
  return cleaned.slice(0, 2).toUpperCase() || '?'
}

const rankLabel = (rank: number) => {
  if (rank === 1) return '🥇'
  if (rank === 2) return '🥈'
  if (rank === 3) return '🥉'
  return `#${rank}`
}

const featureBreakdown = computed(() => {
  if (!me.value) return []
  const entries = Object.entries(me.value.stats.by_feature)
  const total = entries.reduce((sum, [, n]) => sum + n, 0)
  if (total === 0) return []
  return entries
    .map(([feature, count]) => ({
      feature,
      count,
      pct: Math.max(1, Math.round((count * 100) / total))
    }))
    .sort((a, b) => b.count - a.count)
})

const formatTime = (iso: string | null | undefined) => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('ko-KR', { hour12: false })
}

const lastSeenLabel = computed(() => {
  if (!me.value?.stats.last_seen) return '—'
  return formatTime(me.value.stats.last_seen)
})
</script>
