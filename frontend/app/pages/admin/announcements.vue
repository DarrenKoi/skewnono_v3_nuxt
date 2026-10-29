<template>
  <div class="mx-auto max-w-4xl space-y-4 px-4 py-6">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 class="flex items-center gap-2 sk-page-title">
          <UIcon
            name="i-lucide-megaphone"
            class="text-(--sk-ink-muted)"
          />
          배너 공지
        </h1>
        <p class="mt-1 sk-meta">
          올린 공지는 다음 화면 로드부터 모든 사용자의 화면 상단에 표시됩니다
        </p>
      </div>
      <UButton
        :loading="pending"
        color="neutral"
        variant="outline"
        icon="i-lucide-refresh-cw"
        @click="() => refresh()"
      >
        Refresh
      </UButton>
    </header>

    <section
      v-if="!isAdmin"
      class="dashboard-surface rounded-lg border border-(--sk-border) p-6 text-center sk-body"
    >
      관리자만 접근할 수 있는 페이지입니다.
    </section>

    <template v-else>
      <!-- New announcement -->
      <section class="dashboard-surface rounded-lg border border-(--sk-border) p-4">
        <h2 class="sk-title">
          새 공지
        </h2>
        <form
          class="mt-2 space-y-2"
          @submit.prevent="onAdd"
        >
          <div class="flex gap-2">
            <USelect
              v-model="draft.level"
              size="sm"
              color="neutral"
              variant="subtle"
              :items="levelOptions"
              class="w-28"
            />
            <UInput
              v-model="draft.title"
              size="sm"
              color="neutral"
              variant="subtle"
              placeholder="제목 (필수)"
              :maxlength="200"
              class="flex-1"
            />
          </div>
          <UTextarea
            v-model="draft.body"
            size="sm"
            color="neutral"
            variant="subtle"
            placeholder="내용"
            :maxlength="2000"
            :rows="3"
            autoresize
            class="w-full"
          />
          <div class="flex flex-wrap items-center gap-3">
            <label class="flex items-center gap-2 sk-meta">
              시작
              <UInput
                v-model="draft.starts_at"
                type="datetime-local"
                size="xs"
                color="neutral"
                variant="subtle"
              />
            </label>
            <label class="flex items-center gap-2 sk-meta">
              종료
              <UInput
                v-model="draft.ends_at"
                type="datetime-local"
                size="xs"
                color="neutral"
                variant="subtle"
              />
            </label>
            <UCheckbox
              v-model="draft.dismissible"
              label="사용자가 닫을 수 있음"
            />
            <UButton
              type="submit"
              size="sm"
              class="ml-auto"
              icon="i-lucide-send"
              :loading="mutating"
              :disabled="!draft.title.trim()"
            >
              올리기
            </UButton>
          </div>
          <p class="sk-meta">
            시작·종료는 비워 두면 제한이 없습니다. 닫은 배너는 그 사용자의 브라우저에서 다시 뜨지 않습니다.
          </p>
        </form>
        <p
          v-if="formError"
          class="mt-2 sk-meta text-(--sk-bad)"
        >
          {{ formError }}
        </p>
      </section>

      <!-- Stored announcements -->
      <section class="dashboard-surface rounded-lg border border-(--sk-border) p-4">
        <h2 class="sk-title">
          등록된 공지
          <span class="ml-1 sk-meta tabular-nums">
            {{ rows.length }}
          </span>
        </h2>
        <p
          v-if="!rows.length"
          class="mt-2 sk-body"
        >
          등록된 공지가 없습니다.
        </p>
        <ul
          v-else
          class="mt-2 divide-y divide-(--sk-border)"
        >
          <li
            v-for="row in rows"
            :key="row.id"
            class="flex items-start justify-between gap-3 py-2"
          >
            <div class="min-w-0 space-y-0.5">
              <div class="flex items-center gap-2">
                <UBadge
                  :color="colorFor(row.level)"
                  variant="subtle"
                  size="sm"
                >
                  {{ levelLabel[row.level] }}
                </UBadge>
                <span class="sk-body font-medium">{{ row.title }}</span>
              </div>
              <p
                v-if="row.body"
                class="sk-meta whitespace-pre-line"
              >
                {{ row.body }}
              </p>
              <p class="sk-meta">
                {{ windowText(row) }} · {{ row.dismissible ? '닫기 가능' : '닫기 불가' }}
              </p>
            </div>
            <UButton
              size="xs"
              color="error"
              variant="soft"
              icon="i-lucide-trash-2"
              :loading="mutating"
              @click="onRemove(row.id)"
            >
              삭제
            </UButton>
          </li>
        </ul>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  ANNOUNCEMENTS_CACHE_KEY,
  useAnnouncementsAdminApi,
  type Announcement,
  type AnnouncementDraft,
  type AnnouncementLevel
} from '~/composables/useAnnouncementsApi'

const { fetchAll, add, remove } = useAnnouncementsAdminApi()

const { data: me } = await useActivityMe()
const isAdmin = computed(() => me.value?.is_admin === true)

const { data, pending, refresh } = useAsyncData<Announcement[]>(
  'admin-announcements',
  () => (isAdmin.value ? fetchAll() : Promise.resolve([]))
)
const rows = computed(() => data.value ?? [])

const levelLabel: Record<AnnouncementLevel, string> = { info: '안내', warning: '주의', critical: '긴급' }
const levelOptions = (Object.keys(levelLabel) as AnnouncementLevel[]).map(value => ({ value, label: levelLabel[value] }))

const emptyDraft = (): AnnouncementDraft => ({ level: 'info', title: '', body: '', dismissible: true, starts_at: '', ends_at: '' })
const draft = ref(emptyDraft())
const mutating = ref(false)
const formError = ref('')

// The admin list and the live banner both change on every write.
const runMutation = async (action: () => Promise<unknown>) => {
  mutating.value = true
  formError.value = ''
  try {
    await action()
    await Promise.all([refresh(), refreshNuxtData(ANNOUNCEMENTS_CACHE_KEY)])
    return true
  } catch (err) {
    const body = (err as { data?: { error?: { message?: string } } }).data
    formError.value = body?.error?.message ?? '요청을 처리하지 못했습니다.'
    return false
  } finally {
    mutating.value = false
  }
}

const onAdd = async () => {
  if (await runMutation(() => add(draft.value))) draft.value = emptyDraft()
}
const onRemove = (id: string) => runMutation(() => remove(id))

const colorFor = (level: AnnouncementLevel) =>
  level === 'critical' ? 'error' : level === 'warning' ? 'warning' : 'info'

// Bounds are naive KST wall-clock strings (datetime-local), shown as typed.
const windowText = (row: Announcement) => {
  const fmt = (v?: string) => v?.replace('T', ' ').slice(0, 16)
  if (!row.starts_at && !row.ends_at) return '기간 제한 없음'
  return `${fmt(row.starts_at) ?? '지금'} ~ ${fmt(row.ends_at) ?? '계속'}`
}
</script>
