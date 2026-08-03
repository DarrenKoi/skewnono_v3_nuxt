<template>
  <!-- Anonymous callers are en route to /identify (route gate) and a failed
       /api/me leaves identity null — neither state has anything true to show,
       so the pill renders nothing rather than a guess.

       Icon only: the header row has no width to spare, and a Korean name has
       no spaces to break on, so rendering it here wrapped one syllable per
       line. The name lives in this popover and on /activity instead. Only a
       *declared* identity gets a trigger at all — it is the one state with an
       action to offer ("본인이 아닙니다"); a cookie identity would be a button
       that does nothing. -->
  <UPopover
    v-if="identity && canReleaseDeclaration(identity)"
    v-model:open="open"
  >
    <UButton
      color="neutral"
      variant="ghost"
      icon="i-lucide-user-round"
      :aria-label="`내 신원 — ${displayName(identity)}`"
      :title="displayName(identity)"
      :class="isUnverifiedDeclaration(identity) ? 'sk-unverified-dot' : undefined"
    />

    <template #content>
      <div class="w-64 space-y-3 p-4">
        <div class="space-y-1">
          <p class="flex items-center gap-1.5 text-sm font-medium text-(--sk-ink)">
            {{ displayName(identity) }}
            <span
              v-if="isUnverifiedDeclaration(identity)"
              class="sk-unverified-badge"
            >미검증</span>
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
</template>

<script setup lang="ts">
import { canReleaseDeclaration, displayName, isUnverifiedDeclaration } from '~/utils/identityDisplay'

const route = useRoute()
const { identity, isAnonymous, signOut } = useIdentity()
// `isAnonymous` still decides where a released declaration lands (below).

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
/* Icon-only triggers cannot carry the 미검증 word, so unverified is marked
   with a warn dot in the corner; the word itself is in the popover. */
.sk-unverified-dot {
  position: relative;
}

.sk-unverified-dot::after {
  content: '';
  position: absolute;
  top: 6px;
  right: 6px;
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--sk-warn);
}

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
