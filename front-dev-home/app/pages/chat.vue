<script setup lang="ts">
import type {
  FeedbackInput,
  ThreadDetail,
  ThreadSummary
} from '~/composables/useChatApi'
import { reconcileMessageFeedback } from '~/utils/chatSources'
import { generateUuid } from '~/utils/uuid'

const api = useChatApi()
const toast = useToast()

/**
 * A turn is a resource on the server, so this page keeps no state machine of
 * its own for it. The assistant row carries `pending` / `done` / `failed`, and
 * everything below is read from the thread. That is also what makes a reload
 * pick a turn back up: the row is already there, and the poll starts itself.
 */
const POLL_INTERVAL_MS = 2000

const threads = ref<ThreadSummary[]>([])
const active = ref<ThreadDetail | null>(null)
const draft = ref('')
const sidebarOpen = ref(false)
const feedbackLoadingIds = ref<Set<string>>(new Set())
// Only for a POST that never landed — a turn that failed on the server says
// so on its own row.
const sendError = ref<string | null>(null)

const activeId = computed(() => active.value?.id ?? null)
const messages = computed(() => active.value?.messages ?? [])
const pendingTurn = computed(
  () => messages.value.find(m => m.role === 'assistant' && m.status === 'pending') ?? null
)
const failedTurn = computed(
  () => messages.value.find(m => m.role === 'assistant' && m.status === 'failed') ?? null
)
// A reserved row is empty until it settles; showing it would render a blank
// assistant bubble under the typing dots.
const visibleMessages = computed(() =>
  messages.value.filter(m => m.role !== 'assistant' || m.status === 'done')
)
const errorMessage = computed(
  () => sendError.value ?? failedTurn.value?.error_message ?? null
)

const loadThreads = async () => {
  threads.value = await api.fetchThreads()
}

const openThread = async (id: string) => {
  sendError.value = null
  active.value = await api.fetchThread(id)
  sidebarOpen.value = false
}

const newThread = async () => {
  const t = await api.createThread()
  active.value = t
  sidebarOpen.value = false
  await loadThreads()
}

const startNew = () => {
  active.value = null
  draft.value = ''
  sendError.value = null
  sidebarOpen.value = false
}

const removeThread = async (id: string) => {
  await api.deleteThread(id)
  if (active.value?.id === id) active.value = null
  await loadThreads()
}

// Name a fresh thread after its first user message so the sidebar is legible.
const titleThread = async (thread: ThreadDetail, text: string) => {
  const title = text.replace(/\s+/g, ' ').trim().slice(0, 40) || 'New chat'
  try {
    await api.renameThread(thread.id, title)
    thread.title = title
    await loadThreads()
  } catch {
    // Titling is best-effort; a failure here never blocks the conversation.
  }
}

const refresh = async (threadId: string) => {
  const fresh = await api.fetchThread(threadId)
  if (active.value?.id === threadId) active.value = fresh
}

const deliver = async (threadId: string, content: string, requestId: string) => {
  sendError.value = null
  try {
    await api.sendMessage(threadId, content, requestId)
    await refresh(threadId)
    return true
  } catch (e: unknown) {
    const err = e as { data?: { error?: { message?: string } } }
    sendError.value = err?.data?.error?.message ?? '질문을 보내지 못했습니다.'
    return false
  }
}

const send = async (text: string) => {
  if (!active.value) await newThread()
  const thread = active.value!
  const firstTurn = thread.messages.length === 0
  // Optimistic, and replaced by the refetch a moment later: it exists so the
  // composer clears against something visible, not to be reconciled.
  thread.messages.push({
    id: `local-${Date.now()}`, thread_id: thread.id, role: 'user',
    request_id: null, content: text, runtime: null, scope_status: null,
    status: 'done', error_code: null, error_message: null,
    sources: [], feedback: null, rewrite: null, follow_ups: [],
    created_at: new Date().toISOString()
  })
  const succeeded = await deliver(thread.id, text, generateUuid())
  if (firstTurn && succeeded) await titleThread(thread, text)
  await loadThreads()
}

/**
 * Re-run the failed turn under its own request id.
 *
 * The id is reused deliberately: a retry is the same question, and the server
 * retakes the reserved row rather than adding a second one.
 */
const retry = async () => {
  const failed = failedTurn.value
  const thread = active.value
  if (!failed?.request_id || !thread) return
  const asked = thread.messages.find(
    m => m.role === 'user' && m.request_id === failed.request_id
  )
  if (!asked) return
  await deliver(thread.id, asked.content, failed.request_id)
}

const fillExample = (text: string) => {
  draft.value = text
}

const setFeedbackLoading = (messageId: string, loading: boolean) => {
  const next = new Set(feedbackLoadingIds.value)
  if (loading) next.add(messageId)
  else next.delete(messageId)
  feedbackLoadingIds.value = next
}

const saveFeedback = async (messageId: string, input: FeedbackInput | null) => {
  const targetThreadId = active.value?.id
  const message = active.value?.messages.find(item => item.id === messageId)
  if (!targetThreadId || !message || message.role !== 'assistant'
    || feedbackLoadingIds.value.has(messageId)) return

  const previousFeedback = message.feedback
  reconcileMessageFeedback(
    active.value,
    targetThreadId,
    messageId,
    input === null ? null : { ...input, updated_at: new Date().toISOString() }
  )
  setFeedbackLoading(messageId, true)

  try {
    if (input === null) {
      await api.deleteFeedback(messageId)
      reconcileMessageFeedback(active.value, targetThreadId, messageId, null)
    } else {
      const storedFeedback = await api.putFeedback(messageId, input)
      reconcileMessageFeedback(active.value, targetThreadId, messageId, storedFeedback)
    }
  } catch {
    reconcileMessageFeedback(active.value, targetThreadId, messageId, previousFeedback)
    toast.add({
      title: '평가를 저장하지 못했습니다',
      description: '답변은 그대로 유지됩니다. 잠시 후 다시 시도해 주세요.',
      icon: 'i-lucide-triangle-alert',
      color: 'error'
    })
  } finally {
    setFeedbackLoading(messageId, false)
  }
}

// -- waiting on a turn -------------------------------------------------

const now = ref(Date.now())
let pollTimer: ReturnType<typeof setInterval> | null = null
let clockTimer: ReturnType<typeof setInterval> | null = null

const elapsedSeconds = computed(() => {
  const started = pendingTurn.value?.created_at
  if (!started) return 0
  return Math.max(0, Math.round((now.value - Date.parse(started)) / 1000))
})

const stopWaiting = () => {
  if (pollTimer) clearInterval(pollTimer)
  if (clockTimer) clearInterval(clockTimer)
  pollTimer = null
  clockTimer = null
}

const startWaiting = () => {
  if (pollTimer) return
  now.value = Date.now()
  clockTimer = setInterval(() => (now.value = Date.now()), 1000)
  pollTimer = setInterval(() => {
    const id = activeId.value
    // A poll that fails is not a turn that failed — the next tick retries,
    // and the row is the only thing that decides the outcome.
    if (id) refresh(id).catch(() => {})
  }, POLL_INTERVAL_MS)
}

// Polling starts from the ROW, not from having pressed send, so a reload or a
// second tab picks up a turn already in flight without being told about it.
watch(pendingTurn, turn => (turn ? startWaiting() : stopWaiting()), {
  immediate: true
})
onUnmounted(stopWaiting)

/**
 * null until the backend answers. The chat UI is withheld during that gap on
 * purpose: rendering it optimistically would flash a working-looking chat page
 * at production users for one round trip before the notice replaced it.
 */
const available = ref<boolean | null>(null)
const budgetSeconds = ref(0)

onMounted(async () => {
  try {
    const gate = await api.fetchAvailability()
    available.value = gate.available
    budgetSeconds.value = gate.answerTimeoutSeconds
  } catch {
    // A failed availability check must not read as "not in service" — that
    // would turn a backend outage into a false launch announcement. Fall
    // through to the real UI and let its own errors say what is wrong.
    available.value = true
  }
  if (!available.value) return

  await loadThreads()
})
</script>

<template>
  <div
    v-if="available === false"
    class="sk-chat-shell dashboard-surface rounded-[var(--sk-r-card)] sk-chat-notice"
  >
    <UIcon
      name="i-lucide-construction"
      class="w-16 h-16 mb-6 text-(--sk-ink-subtle)"
    />
    <h1 class="sk-page-title mb-2">
      채팅
    </h1>
    <p class="sk-body text-(--sk-ink-muted)">
      현재 준비 중인 기능입니다. 서비스가 시작되면 안내해 드리겠습니다.
    </p>
  </div>

  <div
    v-else-if="available"
    class="sk-chat-shell dashboard-surface rounded-[var(--sk-r-card)]"
  >
    <!-- Mobile backdrop -->
    <div
      v-if="sidebarOpen"
      class="sk-chat-backdrop"
      @click="sidebarOpen = false"
    />

    <div
      class="sk-chat-sidebar-slot"
      :class="{ 'is-open': sidebarOpen }"
    >
      <ChatSidebar
        :threads="threads"
        :active-id="activeId"
        @select="openThread"
        @create="startNew"
        @remove="removeThread"
      />
    </div>

    <section class="sk-chat-main">
      <header class="sk-chat-header">
        <UButton
          icon="i-lucide-panel-left"
          color="neutral"
          variant="ghost"
          size="sm"
          class="sk-chat-menu"
          aria-label="대화 목록"
          @click="sidebarOpen = !sidebarOpen"
        />
        <div class="min-w-0">
          <h1 class="sk-chat-heading">
            채팅
          </h1>
        </div>
      </header>

      <ChatThread
        :messages="visibleMessages"
        :pending="!!pendingTurn"
        :elapsed-seconds="elapsedSeconds"
        :budget-seconds="budgetSeconds"
        :error-message="errorMessage"
        :feedback-loading-ids="feedbackLoadingIds"
        @retry="retry"
        @example="fillExample"
        @feedback="saveFeedback"
      />

      <ChatComposer
        v-model="draft"
        :disabled="!!pendingTurn"
        @send="send"
      />
    </section>
  </div>
</template>

<style scoped>
/* Fills the layout's padded slot exactly. A viewport-relative height
   (calc(100vh - 4rem)) ignores that padding, so the panel overflowed by the
   slot's own p-8 and pushed the composer below the fold. */
.sk-chat-shell {
  position: relative;
  display: flex;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* Reuses the shell so the notice fills the same padded slot as the real page
   — a short auto-height card would leave the panel floating in the layout. */
.sk-chat-notice {
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 2rem;
  background: var(--sk-canvas);
}

.sk-chat-sidebar-slot {
  display: flex;
}

.sk-chat-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  background: var(--sk-canvas);
}

.sk-chat-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 1rem;
  border-bottom: 1px solid var(--sk-border-soft);
  background: var(--sk-canvas);
}

.sk-chat-menu {
  display: none;
}

.sk-chat-heading {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--sk-ink);
  line-height: 1.2;
}

.sk-chat-subhead {
  font-size: 0.75rem;
  color: var(--sk-ink-subtle);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sk-chat-backdrop {
  display: none;
}

/* Desktop: sidebar is inline; below md it becomes an off-canvas overlay. */
@media (max-width: 767px) {
  .sk-chat-menu {
    display: inline-flex;
  }
  .sk-chat-sidebar-slot {
    position: absolute;
    inset: 0 auto 0 0;
    z-index: 30;
    transform: translateX(-100%);
    transition: transform 0.2s ease;
  }
  .sk-chat-sidebar-slot.is-open {
    transform: translateX(0);
  }
  .sk-chat-backdrop {
    display: block;
    position: absolute;
    inset: 0;
    z-index: 20;
    background: color-mix(in srgb, var(--sk-ink) 35%, transparent);
  }
}

@media (prefers-reduced-motion: reduce) {
  .sk-chat-sidebar-slot {
    transition: none;
  }
}
</style>
