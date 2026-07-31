<template>
  <!-- Anonymous callers are en route to /identify (route gate) and a failed
       /api/me leaves identity null — neither state has anything true to show,
       so the pill renders nothing rather than a guess. -->
  <UPopover
    v-if="identity && canReleaseDeclaration(identity)"
    v-model:open="open"
  >
    <UButton
      color="neutral"
      variant="ghost"
      aria-label="내 신원"
    >
      <span class="flex items-center gap-1.5">
        <UIcon
          name="i-lucide-user-round"
          class="size-4"
        />
        <span class="text-sm font-medium">{{ displayName(identity) }}</span>
        <span
          v-if="isUnverifiedDeclaration(identity)"
          class="sk-unverified-badge"
        >미검증</span>
      </span>
    </UButton>

    <template #content>
      <div class="w-64 space-y-3 p-4">
        <div class="space-y-1">
          <p class="text-sm font-medium text-(--sk-ink)">
            {{ displayName(identity) }}
          </p>
          <p class="text-xs text-(--sk-ink-muted)">
            사번 {{ identity.user_id }} · 본인 확인으로 등록됨
          </p>
          <p
            v-if="isUnverifiedDeclaration(identity)"
            class="text-xs text-(--sk-ink-muted)"
          >
            디렉터리에서 확인되지 않은 신원입니다.
          </p>
        </div>
        <UButton
          block
          color="neutral"
          variant="outline"
          :loading="releasing"
          @click="releaseDeclaration"
        >
          본인이 아닙니다
        </UButton>
      </div>
    </template>
  </UPopover>

  <div
    v-else-if="identity && !isAnonymous"
    class="flex items-center gap-1.5 px-2 text-(--sk-ink-muted)"
  >
    <UIcon
      name="i-lucide-user-round"
      class="size-4"
    />
    <span class="text-sm font-medium">{{ displayName(identity) }}</span>
  </div>
</template>

<script setup lang="ts">
import { canReleaseDeclaration, displayName, isUnverifiedDeclaration } from '~/utils/identityDisplay'

const route = useRoute()
const { identity, isAnonymous, signOut } = useIdentity()

const open = ref(false)
const releasing = ref(false)

const releaseDeclaration = async () => {
  if (releasing.value) return
  releasing.value = true
  try {
    await signOut()
    open.value = false
    // Dropping the declaration usually reveals `anonymous`, and the route
    // gate only runs on navigation — send the caller to the form now, with
    // the way back. A cookie identity may remain instead; then they stay.
    if (isAnonymous.value) {
      await navigateTo({ path: '/identify', query: { next: route.fullPath } })
    }
  } catch {
    // A failed DELETE leaves the declaration in place server-side, so the
    // pill already shows the truth; there is no error state to invent.
  } finally {
    releasing.value = false
  }
}
</script>

<style scoped>
/* A label, not a button (DESIGN.md: warn borders at 32% alpha so badges read
   as labels). Chip radius, never rounded-full. */
.sk-unverified-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 600;
  border-radius: var(--sk-r-chip);
  background: var(--sk-warn-soft);
  border: 1px solid var(--sk-warn-border);
  color: var(--sk-ink);
}
</style>
