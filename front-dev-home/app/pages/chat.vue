<script setup lang="ts">
import type { ChatMessage, ChatModel, ThreadDetail, ThreadSummary } from '~/composables/useChatApi'

const api = useChatApi()

const models = ref<ChatModel[]>([])
const selectedModel = ref<string>('')
const threads = ref<ThreadSummary[]>([])
const active = ref<ThreadDetail | null>(null)
const systemPrompt = ref('')
const pending = ref(false)
const errorMessage = ref<string | null>(null)
const lastSent = ref<string | null>(null)

const activeId = computed(() => active.value?.id ?? null)

const loadThreads = async () => {
  threads.value = await api.fetchThreads()
}

const openThread = async (id: string) => {
  errorMessage.value = null
  active.value = await api.fetchThread(id)
  systemPrompt.value = active.value.system_prompt ?? ''
  selectedModel.value = active.value.model
}

const newThread = async () => {
  const t = await api.createThread(selectedModel.value || models.value[0]?.id || '', systemPrompt.value)
  active.value = t
  await loadThreads()
}

const removeThread = async (id: string) => {
  await api.deleteThread(id)
  if (active.value?.id === id) active.value = null
  await loadThreads()
}

const send = async (text: string) => {
  if (!active.value) await newThread()
  const thread = active.value!
  errorMessage.value = null
  lastSent.value = text
  active.value!.messages.push({
    id: `local-${Date.now()}`, thread_id: thread.id, role: 'user',
    content: text, created_at: new Date().toISOString()
  })
  pending.value = true
  try {
    const reply: ChatMessage = await api.sendMessage(thread.id, text)
    active.value!.messages.push(reply)
    lastSent.value = null
    await loadThreads()
  } catch (e: unknown) {
    const err = e as { data?: { error?: { message?: string } } }
    errorMessage.value = err?.data?.error?.message ?? '응답을 받지 못했습니다.'
  } finally {
    pending.value = false
  }
}

const retry = () => {
  if (lastSent.value) send(lastSent.value)
}

onMounted(async () => {
  models.value = await api.fetchModels()
  selectedModel.value = models.value[0]?.id ?? ''
  await loadThreads()
})
</script>

<template>
  <div class="flex h-[calc(100vh-4rem)]">
    <ChatSidebar
      :threads="threads"
      :active-id="activeId"
      @select="openThread"
      @create="newThread"
      @remove="removeThread"
    />
    <section class="flex-1 flex flex-col min-w-0">
      <div class="flex items-center gap-3 border-b border-default px-4 py-2">
        <h1 class="sk-page-title text-base flex items-center gap-2">
          <UIcon name="i-lucide-message-square" class="text-sky-500" />
          채팅
        </h1>
        <div class="ml-auto">
          <ChatModelPicker v-model="selectedModel" :models="models" :disabled="!!active" />
        </div>
      </div>
      <ChatSystemPromptField v-model="systemPrompt" />
      <ChatThread
        :messages="active?.messages ?? []"
        :pending="pending"
        :error-message="errorMessage"
        @retry="retry"
      />
      <ChatComposer :disabled="pending || !selectedModel" @send="send" />
    </section>
  </div>
</template>
