<template>
  <section class="dashboard-surface space-y-4 rounded-lg border border-(--sk-border) p-4">
    <div>
      <h2 class="flex items-center gap-2 sk-title">
        <UIcon
          name="i-lucide-folder-lock"
          class="text-(--sk-ink-muted)"
        />
        장비 파일 접근
      </h2>
      <p class="mt-1 sk-meta">
        승인된 팀의 구성원과 승인된 사번은 신청 없이 장비 파일 탐색기를 씁니다.
        팀 소속 변경은 최대 10분 늦게 반영됩니다.
      </p>
    </div>

    <p
      v-if="grantsError"
      class="sk-body text-rose-600 dark:text-rose-400"
    >
      {{ grantsError }}
    </p>

    <p
      v-if="formError"
      class="sk-meta text-rose-600 dark:text-rose-400"
      role="alert"
    >
      {{ formError }}
    </p>

    <div class="space-y-2">
      <h3 class="sk-label">
        대기 신청
        <span class="ml-1 sk-meta tabular-nums">{{ pending.length }}</span>
      </h3>
      <p
        v-if="!pending.length && !grantsError"
        class="sk-meta"
      >
        대기 중인 신청이 없습니다.
      </p>
      <ul
        v-else
        class="divide-y divide-(--sk-border)"
      >
        <li
          v-for="row in pending"
          :key="row.empno"
          class="flex items-start justify-between gap-3 py-2"
        >
          <div class="min-w-0 space-y-0.5">
            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span class="sk-value-num">{{ row.empno }}</span>
              <span
                v-if="row.emp_nm"
                class="sk-body"
              >{{ row.emp_nm }}</span>
              <span class="sk-meta">{{ row.dept_nm ?? '소속 정보 없음' }}</span>
              <span class="sk-meta">{{ formatKoreanDateTime(row.requested_at) }}</span>
            </div>
            <p class="sk-body whitespace-pre-wrap break-words">
              {{ row.reason }}
            </p>
          </div>
          <div class="flex shrink-0 gap-1.5">
            <UButton
              size="xs"
              color="primary"
              :loading="mutating"
              @click="onApprove(row)"
            >
              승인
            </UButton>
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              :loading="mutating"
              @click="onReject(row)"
            >
              거절
            </UButton>
            <UButton
              v-if="row.dept_nm"
              size="xs"
              color="neutral"
              variant="subtle"
              :loading="mutating"
              @click="onApproveTeam(row.dept_nm)"
            >
              이 팀 전체 승인<span
                v-if="row.teamPending > 1"
                class="ml-1 tabular-nums"
              >({{ row.teamPending }}건)</span>
            </UButton>
          </div>
        </li>
      </ul>
    </div>

    <div class="grid gap-4 md:grid-cols-2">
      <div class="space-y-2">
        <h3 class="sk-label">
          팀 승인
          <span class="ml-1 sk-meta tabular-nums">{{ rows.teams.length }}</span>
        </h3>
        <form
          class="flex gap-2"
          @submit.prevent="onGrant('team', teamPick)"
        >
          <USelectMenu
            v-model="teamPick"
            class="w-64"
            size="sm"
            color="neutral"
            variant="subtle"
            :items="teamOptions"
            value-key="value"
            :placeholder="teamsError ? '팀 목록을 불러오지 못했습니다' : '팀 선택'"
            aria-label="승인할 팀"
          />
          <UButton
            type="submit"
            size="sm"
            :loading="mutating"
            :disabled="!teamPick"
          >
            승인
          </UButton>
        </form>
        <p
          v-if="teams && !teams.complete"
          class="sk-meta"
        >
          구성원 목록 일부를 읽지 못해 인원수가 실제보다 적을 수 있습니다.
        </p>
        <ul class="divide-y divide-(--sk-border)">
          <li
            v-for="row in rows.teams"
            :key="row.value"
            class="flex items-center justify-between gap-3 py-2"
          >
            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span class="sk-body">{{ row.value }}</span>
              <UBadge
                v-if="row.warnEmpty"
                color="warning"
                variant="subtle"
                size="sm"
              >
                구성원 0명
              </UBadge>
              <span
                v-else-if="row.members !== null"
                class="sk-meta tabular-nums"
              >{{ row.members }}명</span>
              <span class="sk-meta">{{ formatKoreanDateTime(row.granted_at) }} · {{ row.granted_by }}</span>
            </div>
            <UButton
              class="shrink-0"
              size="xs"
              color="error"
              variant="soft"
              :loading="mutating"
              @click="onRevoke('team', row.value)"
            >
              회수
            </UButton>
          </li>
        </ul>
      </div>

      <div class="space-y-2">
        <h3 class="sk-label">
          개인 승인
          <span class="ml-1 sk-meta tabular-nums">{{ rows.emps.length }}</span>
        </h3>
        <form
          class="flex gap-2"
          @submit.prevent="onGrant('emp', empInput.trim())"
        >
          <UInput
            v-model="empInput"
            class="w-64"
            size="sm"
            color="neutral"
            variant="subtle"
            icon="i-lucide-user-plus"
            placeholder="사번 (예: 2067928)"
            aria-label="승인할 사번"
          />
          <UButton
            type="submit"
            size="sm"
            :loading="mutating"
            :disabled="!empInput.trim()"
          >
            승인
          </UButton>
        </form>
        <p class="sk-meta">
          개인 승인을 회수해도 그 사람의 팀이 승인되어 있으면 접근은 유지됩니다.
        </p>
        <ul class="divide-y divide-(--sk-border)">
          <li
            v-for="row in rows.emps"
            :key="row.value"
            class="flex items-center justify-between gap-3 py-2"
          >
            <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
              <span class="sk-value-num">{{ row.value }}</span>
              <span
                v-if="row.dept_nm"
                class="sk-meta"
              >{{ row.dept_nm }}</span>
              <UBadge
                v-if="row.coveredByTeam"
                color="info"
                variant="subtle"
                size="sm"
              >
                팀 승인으로 유지
              </UBadge>
              <span class="sk-meta">{{ formatKoreanDateTime(row.granted_at) }} · {{ row.granted_by }}</span>
            </div>
            <UButton
              class="shrink-0"
              size="xs"
              color="error"
              variant="soft"
              :loading="mutating"
              @click="onRevoke('emp', row.value)"
            >
              회수
            </UButton>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { useToolFilesAdminApi, type ToolFilesGrantKind } from '~/composables/useToolFilesApi'
import {
  describeToolFilesGrants,
  pendingToolFilesRequests,
  toolFilesErrorCode,
  toolFilesErrorMessage,
  type ToolFilesPendingRow
} from '~/utils/toolFiles'
import { formatKoreanDateTime } from '~/utils/dateTime'

const api = useToolFilesAdminApi()

const { data: overview, error: overviewError, refresh } = useAsyncData('admin-tool-files-grants', api.fetchGrants)
const { data: teams, error: teamsError } = useAsyncData('admin-tool-files-teams', api.fetchTeams)

const grantsError = computed(() =>
  overviewError.value ? toolFilesErrorMessage(toolFilesErrorCode(overviewError.value)) : ''
)
const rows = computed(() => describeToolFilesGrants(overview.value?.grants ?? [], teams.value ?? null))
const pending = computed(() => pendingToolFilesRequests(overview.value?.requests ?? []))
const teamOptions = computed(() =>
  (teams.value?.teams ?? []).map(t => ({ label: `${t.dept_nm} (${t.members}명)`, value: t.dept_nm }))
)

const teamPick = ref<string | undefined>()
const empInput = ref('')
const mutating = ref(false)
const formError = ref('')

const run = async (action: () => Promise<unknown>) => {
  mutating.value = true
  formError.value = ''
  try {
    await action()
    await refresh()
    return true
  } catch (err) {
    formError.value = toolFilesErrorMessage(toolFilesErrorCode(err))
    if (toolFilesErrorCode(err) === 'request_changed') await refresh()
    return false
  } finally {
    mutating.value = false
  }
}

const onGrant = async (kind: ToolFilesGrantKind, value: string | undefined) => {
  if (!value) return
  if (await run(() => api.grant(kind, value))) {
    if (kind === 'team') teamPick.value = undefined
    else empInput.value = ''
  }
}

const onRevoke = (kind: ToolFilesGrantKind, value: string) => run(() => api.revoke(kind, value))

// A 409 (re-request since this list loaded) refreshes too, through run(), so
// the new request is on screen beside the message.
const onApprove = (row: ToolFilesPendingRow) => run(() => api.approve(row.empno, row.request_id))
const onReject = (row: ToolFilesPendingRow) => run(() => api.reject(row.empno, row.request_id))
const onApproveTeam = (deptNm: string) => run(() => api.approveTeam(deptNm))
</script>
