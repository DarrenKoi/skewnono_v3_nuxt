<template>
  <section class="dashboard-surface space-y-4 rounded-lg border border-(--sk-border) p-4">
    <div>
      <h2 class="flex items-center gap-2 sk-title">
        <UIcon
          name="i-lucide-folder-lock"
          class="text-(--sk-ink-muted)"
        />
        FTP 접속 개인 승인
      </h2>
      <p class="mt-1 sk-meta">
        지정된 팀 소속은 승인 없이 씁니다. 그 밖의 사람(타 팀 파견 등)은 여기서 사번으로 승인합니다.
      </p>
    </div>

    <p
      v-if="overviewError"
      class="sk-body text-rose-600 dark:text-rose-400"
    >
      {{ overviewError }}
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
        v-if="!pending.length && !overviewError"
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
              @click="run(() => api.approve(row.empno, row.request_id))"
            >
              승인
            </UButton>
            <UButton
              size="xs"
              color="neutral"
              variant="outline"
              :loading="mutating"
              @click="run(() => api.reject(row.empno, row.request_id))"
            >
              거절
            </UButton>
          </div>
        </li>
      </ul>
    </div>

    <div class="space-y-2">
      <h3 class="sk-label">
        승인된 사번
        <span class="ml-1 sk-meta tabular-nums">{{ grants.length }}</span>
      </h3>
      <form
        class="flex gap-2"
        @submit.prevent="onGrant"
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
          추가
        </UButton>
      </form>
      <ul class="divide-y divide-(--sk-border)">
        <li
          v-for="row in grants"
          :key="row.empno"
          class="flex items-center justify-between gap-3 py-2"
        >
          <div class="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span class="sk-value-num">{{ row.empno }}</span>
            <span
              v-if="row.emp_nm"
              class="sk-body"
            >{{ row.emp_nm }}</span>
            <span
              v-if="row.dept_nm"
              class="sk-meta"
            >{{ row.dept_nm }}</span>
            <span class="sk-meta">{{ formatKoreanDateTime(row.granted_at) }} · {{ row.granted_by }}</span>
          </div>
          <UButton
            class="shrink-0"
            size="xs"
            color="error"
            variant="soft"
            :loading="mutating"
            @click="run(() => api.revoke(row.empno))"
          >
            회수
          </UButton>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
import { TOOL_FILES_ADMIN_KEY, useToolFilesAdminApi } from '~/composables/useToolFilesApi'
import { toolFilesErrorCode, toolFilesErrorMessage } from '~/utils/toolFiles'
import { formatKoreanDateTime } from '~/utils/dateTime'

const api = useToolFilesAdminApi()

const { data: overview, error, refresh } = useAsyncData(TOOL_FILES_ADMIN_KEY, api.fetchOverview)

const overviewError = computed(() =>
  error.value ? toolFilesErrorMessage(toolFilesErrorCode(error.value)) : ''
)
const grants = computed(() => overview.value?.grants ?? [])
// Only pending ones need a decision; a rejected request waits for the
// requester to ask again.
const pending = computed(() => (overview.value?.requests ?? []).filter(r => r.status === 'pending'))

const empInput = ref('')
const mutating = ref(false)
const formError = ref('')

// A 409 (re-request since this list loaded) refreshes too, so the new request
// is on screen beside the message.
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

const onGrant = async () => {
  if (await run(() => api.grant(empInput.value.trim()))) empInput.value = ''
}
</script>
