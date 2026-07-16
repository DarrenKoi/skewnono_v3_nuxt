<template>
  <UCard class="dashboard-surface rounded-3xl">
    <template #header>
      <div class="flex items-center justify-between gap-3">
        <h2 class="font-semibold">
          API Tokens
        </h2>
        <UButton
          icon="i-lucide-plus"
          size="sm"
          color="primary"
          :disabled="creatingBusy"
          @click="openCreate"
        >
          New token
        </UButton>
      </div>
    </template>

    <p class="mb-4 text-sm text-gray-500 dark:text-zinc-400">
      내부 서비스나 스크립트에서 <code class="text-xs">/api/*</code>를 호출하려면 토큰을 만드세요.
      토큰은 <code class="text-xs">Authorization: Bearer ...</code> 헤더에 넣어 사용합니다.
      토큰은 내 계정과 같은 읽기 권한을 가집니다. 유출되면 바로 폐기하세요.
    </p>

    <div
      v-if="pending && !tokens.length"
      class="py-6 text-center text-sm text-gray-500"
    >
      Loading…
    </div>
    <div
      v-else-if="error"
      class="py-6 text-center text-sm text-red-500"
    >
      Failed to load tokens.
    </div>
    <div
      v-else-if="!tokens.length"
      class="py-6 text-center text-sm text-gray-500"
    >
      No tokens yet.
    </div>
    <UTable
      v-else
      :data="tokens"
      :columns="columns"
    >
      <template #last_used_at-cell="{ row }">
        <span :class="row.original.last_used_at ? '' : 'text-gray-400'">
          {{ row.original.last_used_at ?? 'never used' }}
        </span>
      </template>
      <template #actions-cell="{ row }">
        <UButton
          icon="i-lucide-trash-2"
          size="xs"
          color="error"
          variant="ghost"
          :loading="revokingId === row.original.id"
          @click="onRevoke(row.original.id)"
        >
          Revoke
        </UButton>
      </template>
    </UTable>

    <UModal
      v-model:open="creating"
      title="Create API token"
    >
      <template #body>
        <UFormField
          label="Label"
          hint="A short name so you can identify this token later."
        >
          <UInput
            v-model="newLabel"
            placeholder="e.g. nightly backup script"
            autofocus
            class="w-full"
          />
        </UFormField>
      </template>
      <template #footer>
        <div class="flex justify-end gap-2">
          <UButton
            variant="ghost"
            @click="creating = false"
          >
            Cancel
          </UButton>
          <UButton
            :loading="creatingBusy"
            :disabled="!newLabel.trim()"
            @click="confirmCreate"
          >
            Create
          </UButton>
        </div>
      </template>
    </UModal>

    <UModal
      v-model:open="showingPlaintext"
      :dismissible="false"
      :close="false"
      title="Token created"
    >
      <template #body>
        <div class="space-y-3">
          <UAlert
            color="warning"
            variant="soft"
            icon="i-lucide-triangle-alert"
            title="This token will not be shown again"
            description="Copy it now and store it somewhere safe. If you lose it, revoke and reissue."
          />
          <div class="flex items-center gap-2 rounded-lg bg-gray-100 dark:bg-zinc-800 p-3">
            <code class="flex-1 text-xs break-all">{{ plaintext }}</code>
            <UButton
              :icon="copied ? 'i-lucide-check' : 'i-lucide-copy'"
              size="xs"
              variant="ghost"
              @click="copyPlaintext"
            />
          </div>
        </div>
      </template>
      <template #footer>
        <div class="flex justify-end">
          <UButton @click="dismissPlaintext">
            Done
          </UButton>
        </div>
      </template>
    </UModal>
  </UCard>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { ApiTokenRow } from '~/composables/useApiTokens'

const { tokens, pending, error, create, revoke } = useApiTokens()
const toast = useToast()

const columns: TableColumn<ApiTokenRow>[] = [
  { accessorKey: 'label', header: 'Label' },
  { accessorKey: 'created_at', header: 'Created' },
  { accessorKey: 'last_used_at', header: 'Last used' },
  { id: 'actions', header: '' }
]

const creating = ref(false)
const newLabel = ref('')
const creatingBusy = ref(false)

const showingPlaintext = ref(false)
const plaintext = ref('')
const copied = ref(false)

const revokingId = ref<string | null>(null)

const openCreate = () => {
  newLabel.value = ''
  creating.value = true
}

const confirmCreate = async () => {
  if (!newLabel.value.trim()) return
  creatingBusy.value = true
  try {
    const res = await create(newLabel.value)
    plaintext.value = res.plaintext
    creating.value = false
    showingPlaintext.value = true
  } catch (e) {
    toast.add({ title: 'Failed to create token', description: String(e), color: 'error' })
  } finally {
    creatingBusy.value = false
  }
}

const copyPlaintext = async () => {
  try {
    await navigator.clipboard.writeText(plaintext.value)
    copied.value = true
    setTimeout(() => {
      copied.value = false
    }, 1500)
  } catch {
    toast.add({ title: 'Clipboard unavailable', description: 'Copy the token manually.', color: 'warning' })
  }
}

const dismissPlaintext = () => {
  showingPlaintext.value = false
  plaintext.value = ''
  copied.value = false
}

const onRevoke = async (id: string) => {
  if (!confirm('Revoke this token? Any service still using it will start getting 401s.')) return
  revokingId.value = id
  try {
    await revoke(id)
  } catch (e) {
    toast.add({ title: 'Failed to revoke token', description: String(e), color: 'error' })
  } finally {
    revokingId.value = null
  }
}
</script>
