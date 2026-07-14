<template>
  <div class="mx-auto max-w-4xl space-y-4 px-4 py-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="flex items-center gap-2 text-2xl font-semibold text-zinc-950 dark:text-zinc-50">
          <UIcon
            name="i-lucide-shield-check"
            class="text-sky-500"
          />
          접근 권한 관리
        </h1>
        <p class="mt-1 text-sm text-zinc-500 dark:text-zinc-400">
          X-사번 차단 규칙과 예외 허용 목록을 관리합니다
        </p>
      </div>
      <UButton
        :loading="pending"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        @click="reload"
      >
        Refresh
      </UButton>
    </header>

    <section
      v-if="!isAdmin"
      class="dashboard-surface rounded-lg border border-(--sk-border) p-6 text-center text-sm text-zinc-500 dark:text-zinc-400"
    >
      관리자만 접근할 수 있는 페이지입니다.
    </section>

    <template v-else>
      <!-- Rule summary -->
      <section class="dashboard-surface flex items-start gap-3 rounded-lg border border-(--sk-border) p-4">
        <UIcon
          name="i-lucide-info"
          class="mt-0.5 shrink-0 text-sky-500"
        />
        <p class="text-sm leading-6 text-zinc-600 dark:text-zinc-300">
          사번이
          <UBadge
            color="error"
            variant="subtle"
            size="sm"
          >
            {{ overview?.rule.blocked_prefix ?? 'X' }}
          </UBadge>
          로 시작하는 사용자는 기본적으로 모든 데이터 접근이 차단됩니다.
          아래 예외 목록에 등록된 사번만 정상적으로 이용할 수 있습니다.
        </p>
      </section>

      <!-- Add exception -->
      <section class="dashboard-surface rounded-lg border border-(--sk-border) p-4">
        <h2 class="text-sm font-semibold text-zinc-950 dark:text-zinc-50">
          예외 추가
        </h2>
        <form
          class="mt-2 flex gap-2"
          @submit.prevent="onAdd"
        >
          <UInput
            v-model="newId"
            size="sm"
            color="neutral"
            variant="subtle"
            icon="i-lucide-user-plus"
            placeholder="X로 시작하는 사번 (예: X123456)"
            class="w-64"
          />
          <UButton
            type="submit"
            size="sm"
            :loading="mutating"
            :disabled="!newId.trim()"
          >
            허용
          </UButton>
        </form>
        <p
          v-if="formError"
          class="mt-2 text-xs text-red-500"
        >
          {{ formError }}
        </p>
      </section>

      <!-- Exception list -->
      <section class="dashboard-surface rounded-lg border border-(--sk-border) p-4">
        <h2 class="text-sm font-semibold text-zinc-950 dark:text-zinc-50">
          허용된 사번
          <span class="ml-1 text-xs font-normal text-zinc-500 tabular-nums">
            {{ exceptions.length }}
          </span>
        </h2>
        <p
          v-if="!exceptions.length"
          class="mt-2 text-sm text-zinc-500 dark:text-zinc-400"
        >
          아직 허용된 예외가 없습니다.
        </p>
        <ul
          v-else
          class="mt-2 divide-y divide-(--sk-border)"
        >
          <li
            v-for="row in exceptions"
            :key="row.user_id"
            class="flex items-center justify-between gap-3 py-2"
          >
            <div class="flex items-baseline gap-3">
              <span class="font-medium text-zinc-950 tabular-nums dark:text-zinc-50">
                {{ row.user_id }}
              </span>
              <span class="text-xs text-zinc-500">
                허용일 {{ formatTime(row.granted_at) }}
              </span>
            </div>
            <UButton
              size="xs"
              color="error"
              variant="soft"
              icon="i-lucide-user-minus"
              :loading="mutating"
              @click="onRemove(row.user_id)"
            >
              제거
            </UButton>
          </li>
        </ul>
      </section>

      <!-- Recently denied -->
      <section class="dashboard-surface rounded-lg border border-(--sk-border) p-4">
        <h2 class="text-sm font-semibold text-zinc-950 dark:text-zinc-50">
          최근 차단된 접근 시도
          <span class="ml-1 text-xs font-normal text-zinc-500 tabular-nums">
            {{ denied.length }}
          </span>
        </h2>
        <p class="mt-1 text-xs text-zinc-500 dark:text-zinc-400">
          서버 재시작 전까지의 최근 50건입니다. "허용"을 누르면 바로 예외 목록에 추가됩니다.
        </p>
        <p
          v-if="!denied.length"
          class="mt-2 text-sm text-zinc-500 dark:text-zinc-400"
        >
          기록된 차단 시도가 없습니다.
        </p>
        <ul
          v-else
          class="mt-2 divide-y divide-(--sk-border)"
        >
          <li
            v-for="row in denied"
            :key="row.user_id"
            class="flex items-center justify-between gap-3 py-2"
          >
            <div class="flex items-baseline gap-3">
              <span class="font-medium text-zinc-950 tabular-nums dark:text-zinc-50">
                {{ row.user_id }}
              </span>
              <span class="text-xs text-zinc-500">
                마지막 시도 {{ formatTime(row.last_denied_at) }}
              </span>
            </div>
            <UButton
              size="xs"
              color="success"
              variant="soft"
              icon="i-lucide-user-check"
              :loading="mutating"
              @click="onAllow(row.user_id)"
            >
              허용
            </UButton>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  useAccessControlApi,
  type AccessOverview
} from '~/composables/useAccessControlApi'

const { fetchOverview, addException, removeException } = useAccessControlApi()

const { data: me } = await useActivityMe()
const isAdmin = computed(() => me.value?.is_admin === true)

const {
  data: overview,
  pending,
  refresh
} = useAsyncData<AccessOverview | null>(
  'admin-access-overview',
  () => (isAdmin.value ? fetchOverview() : Promise.resolve(null))
)

const exceptions = computed(() => overview.value?.exceptions ?? [])
const denied = computed(() => overview.value?.denied ?? [])

const newId = ref('')
const mutating = ref(false)
const formError = ref('')

const reload = () => refresh()

const runMutation = async (action: () => Promise<unknown>) => {
  mutating.value = true
  formError.value = ''
  try {
    await action()
    await refresh()
    return true
  } catch (err) {
    const data = (err as { data?: { error?: { message?: string } } }).data
    formError.value = data?.error?.message ?? '요청을 처리하지 못했습니다.'
    return false
  } finally {
    mutating.value = false
  }
}

const onAdd = async () => {
  const id = newId.value.trim()
  if (!id) return
  if (await runMutation(() => addException(id))) newId.value = ''
}

const onAllow = (userId: string) => runMutation(() => addException(userId))

const onRemove = (userId: string) => runMutation(() => removeException(userId))

const formatTime = (value: string | null) => {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('ko-KR', { hour12: false })
}
</script>
