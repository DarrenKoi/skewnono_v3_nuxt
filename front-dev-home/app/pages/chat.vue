<script setup lang="ts">
import type {
  ChatMessage,
  ChatModel,
  FeedbackInput,
  ThreadDetail,
  ThreadSummary
} from '~/composables/useChatApi'
import { reconcileMessageFeedback } from '~/utils/chatSources'
import { createPendingChatTurn, type PendingChatTurn } from '~/utils/chatTurn'

const api = useChatApi()
const toast = useToast()

const models = ref<ChatModel[]>([])
const selectedModel = ref<string>('')
const threads = ref<ThreadSummary[]>([])
const active = ref<ThreadDetail | null>(null)
const systemPrompt = ref('')
const draft = ref('')
const pending = ref(false)
const errorMessage = ref<string | null>(null)
const pendingTurn = ref<PendingChatTurn | null>(null)
const sidebarOpen = ref(false)
const feedbackLoadingIds = ref<Set<string>>(new Set())

const activeId = computed(() => active.value?.id ?? null)
const currentModelId = computed(() => active.value?.model ?? selectedModel.value)
const modelLabel = computed(
  () => models.value.find(m => m.id === currentModelId.value)?.label ?? ''
)

const loadThreads = async () => {
  threads.value = await api.fetchThreads()
}

const openThread = async (id: string) => {
  errorMessage.value = null
  active.value = await api.fetchThread(id)
  systemPrompt.value = active.value.system_prompt ?? ''
  selectedModel.value = active.value.model
  sidebarOpen.value = false
}

const newThread = async () => {
  const t = await api.createThread(selectedModel.value || models.value[0]?.id || '', systemPrompt.value)
  active.value = t
  sidebarOpen.value = false
  await loadThreads()
}

const startNew = () => {
  active.value = null
  errorMessage.value = null
  draft.value = ''
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

const deliver = async (thread: ThreadDetail, turn: PendingChatTurn) => {
  errorMessage.value = null
  pending.value = true
  try {
    const reply: ChatMessage = await api.sendMessage(thread.id, turn.content, turn.requestId)
    active.value!.messages.push(reply)
    pendingTurn.value = null
    await loadThreads()
  } catch (e: unknown) {
    const err = e as { data?: { error?: { message?: string } } }
    errorMessage.value = err?.data?.error?.message ?? '응답을 받지 못했습니다.'
  } finally {
    pending.value = false
  }
}

const send = async (text: string) => {
  if (!active.value) await newThread()
  const thread = active.value!
  const firstTurn = thread.messages.length === 0
  const turn = createPendingChatTurn(text)
  pendingTurn.value = turn
  thread.messages.push({
    id: `local-${Date.now()}`, thread_id: thread.id, role: 'user',
    request_id: turn.requestId, content: text, runtime: null, scope_status: null,
    sources: [], feedback: null, created_at: new Date().toISOString()
  })
  await deliver(thread, turn)
  if (firstTurn && !errorMessage.value) await titleThread(thread, text)
}

const retry = () => {
  if (pendingTurn.value && active.value) deliver(active.value, pendingTurn.value)
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

onMounted(async () => {
  models.value = await api.fetchModels()
  selectedModel.value = models.value[0]?.id ?? ''
  await loadThreads()
})
</script>

<template>
  <div class="sk-chat-shell dashboard-surface rounded-[var(--sk-r-card)]">
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
          <p
            v-if="modelLabel"
            class="sk-chat-subhead"
          >
            {{ modelLabel }}
          </p>
        </div>
        <div class="ml-auto">
          <ChatModelPicker
            v-model="selectedModel"
            :models="models"
            :disabled="!!active"
          />
        </div>
      </header>

      <ChatSystemPromptField
        v-model="systemPrompt"
        :disabled="!!active"
      />

      <ChatThread
        :messages="active?.messages ?? []"
        :pending="pending"
        :error-message="errorMessage"
        :model-label="modelLabel"
        :feedback-loading-ids="feedbackLoadingIds"
        @retry="retry"
        @example="fillExample"
        @feedback="saveFeedback"
      />

      <ChatComposer
        v-model="draft"
        :disabled="pending || !selectedModel"
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
