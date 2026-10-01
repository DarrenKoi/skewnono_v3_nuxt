<template>
  <UCard class="dashboard-surface">
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <span class="text-sm font-medium text-(--sk-ink-muted) flex items-center gap-1.5">
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
        label="Excel 다운로드"
        :disabled="filteredUsers.length === 0"
        @click="downloadUsersExcel"
      />
      <!-- Deliberately NOT 새로고침: the page header already has a button
           by that name, and it does something else entirely (refetches
           every activity query from the server). This one only clears the
           toolbar above — search box, feature filter, sort — and touches
           nothing on the server. Naming the target is also what keeps it
           from reading as destructive next to a table of per-employee
           records, which is why it is not 초기화 either. -->
      <UTooltip text="검색어·기능 필터·정렬을 기본값으로 되돌립니다">
        <UButton
          size="sm"
          color="neutral"
          variant="ghost"
          icon="i-lucide-filter-x"
          label="필터 해제"
          :disabled="!hasActiveUserControls"
          @click="resetUserControls"
        />
      </UTooltip>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left sk-label border-b border-(--sk-border)">
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
              가장 최근 쓴 기능
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
                {{ activityFeatureLabel(row.recent_feature) }}
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
                    <div class="sk-label mb-2">
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
                    <div class="sk-label mb-2">
                      최근 쓴 기능 5개
                    </div>
                    <ActivityRecentFeatureList
                      :items="userDetail.recent_features"
                      empty-text="—"
                    />
                  </div>
                  <div>
                    <div class="sk-label mb-2">
                      30일 활동
                    </div>
                    <ActivitySparkline
                      :series="userDetail.daily"
                      tone="brand"
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

<script setup lang="ts">
import type { UserListResponse } from '~/composables/useActivityApi'
import { activityFeatureLabel, userDisplayName, userTeamLabel } from '~/utils/activity'
import { formatKoreanDateTime } from '~/utils/dateTime'

// Per-employee rows are admin-only (the backend answers 403 otherwise), so
// the page that mounts this has already decided the viewer may see them.
const props = defineProps<{
  users: UserListResponse | null
}>()

const formatTime = (iso: string | null | undefined) => formatKoreanDateTime(iso)

const userRows = computed(() => props.users?.users ?? [])
const {
  query: userQuery,
  featureFilter,
  sort: userSort,
  sortOptions: userSortOptions,
  featureFilterOptions,
  filteredRows: filteredUsers,
  hasActiveControls: hasActiveUserControls,
  resetControls: resetUserControls,
  download: downloadUsersExcel,
  copy: copyUsersTable,
  expandedUser,
  userDetail,
  userDetailLoading,
  userDetailError,
  toggleUser
} = useActivityUserTable(userRows)
</script>
