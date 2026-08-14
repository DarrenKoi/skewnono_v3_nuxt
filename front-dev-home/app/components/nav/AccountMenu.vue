<script setup lang="ts">
import type { HeaderLink } from '~/utils/headerNav'
import { canReleaseDeclaration, displayName, isUnverifiedDeclaration } from '~/utils/identityDisplay'
import { headerLinksIn, isHeaderLinkActive } from '~/utils/headerNav'

// 계정 — who the caller is, and the pages about their own use of the app. This grew out of
// IdentityPill: the pill was already a popover naming the caller, so making it the trigger
// for 서비스 소개 / 사용 통계 / 세팅 costs no new header slot.
//
// The trigger renders in every identity state, unlike the old pill. It used to hide itself
// for a cookie or anonymous caller because "본인이 아닙니다" was all it had to offer, and a
// button that does nothing is worse than none. Now the menu also holds three pages that are
// reachable nowhere else, so hiding it would strand them; the release row hides instead.

const route = useRoute()
const { identity, isAnonymous, signOut } = useIdentity()

const open = ref(false)
const releasing = ref(false)
const links = headerLinksIn('account')

const isActive = (link: HeaderLink) => isHeaderLinkActive(link, route.path)

const hasActiveLink = computed(() => links.some(isActive))

// The avatar is the name's first character — a Korean name has no spaces to build initials
// from, so the first syllable is the whole convention. Without an identity there is no
// letter to draw and the generic person icon stands in.
const initial = computed(() => identity.value ? displayName(identity.value).trim().charAt(0) : '')

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
    // menu already shows the truth; there is no error state to invent.
  } finally {
    releasing.value = false
  }
}
</script>

<template>
  <!-- align="end": the panel is far wider than the avatar trigger, and this is the
       last thing in the header — centred it would run off the right edge. -->
  <UPopover
    v-model:open="open"
    :content="{ align: 'end' }"
  >
    <button
      type="button"
      class="account-trigger"
      :class="[
        hasActiveLink ? 'account-trigger--active' : null,
        identity && isUnverifiedDeclaration(identity) ? 'sk-unverified-dot' : null
      ]"
      :aria-label="identity ? `내 계정 — ${displayName(identity)}` : '내 계정'"
      aria-haspopup="menu"
      :aria-expanded="open"
    >
      <span
        class="account-avatar"
        aria-hidden="true"
      >
        <UIcon
          v-if="!initial"
          name="i-lucide-user-round"
          class="account-avatar__icon"
        />
        <template v-else>{{ initial }}</template>
      </span>
      <UIcon
        :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        class="account-trigger__chevron"
      />
    </button>

    <template #content>
      <div class="w-[262px] p-1.5">
        <div
          v-if="identity"
          class="mb-1 flex items-center gap-2.5 border-b border-(--sk-border-soft) px-2.5 pb-2.5 pt-2"
        >
          <span
            class="account-avatar account-avatar--lg"
            aria-hidden="true"
          >{{ initial }}</span>
          <span class="min-w-0">
            <span class="flex items-center gap-1.5">
              <span class="sk-title truncate">{{ displayName(identity) }}</span>
              <span
                v-if="isUnverifiedDeclaration(identity)"
                class="sk-unverified-badge"
              >미검증</span>
            </span>
            <span class="sk-value-num block text-(--sk-ink-muted)">사번 {{ identity.user_id }}</span>
          </span>
        </div>

        <nav
          aria-label="내 계정"
          class="flex flex-col gap-0.5"
        >
          <NavHeaderMenuItem
            v-for="link in links"
            :key="link.label"
            :label="link.label"
            :icon="link.icon"
            :to="link.to ?? undefined"
            :active="isActive(link)"
            @select="open = false"
          />
          <!-- Only a *declared* identity can be released; a cookie one is authoritative
               rather than chosen, so there is nothing to undo. -->
          <NavHeaderMenuItem
            v-if="identity && canReleaseDeclaration(identity)"
            label="본인이 아닙니다"
            muted
            separated
            :loading="releasing"
            @select="releaseDeclaration"
          />
        </nav>
      </div>
    </template>
  </UPopover>
</template>

<style scoped>
/* Not a `sk-nav-pill`: it never takes the ink fill, because the avatar inside it already
   carries ink and a filled pill around a filled square reads as two nested buttons. The
   active state is the crimson underline alone. */
.account-trigger {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px 4px 4px;
  border: 1px solid var(--sk-border);
  border-radius: var(--sk-r-nav);
  background: transparent;
  cursor: pointer;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

.account-trigger:hover {
  background: var(--sk-muted-surface);
}

.account-trigger--active {
  box-shadow: inset 0 -2px 0 0 var(--sk-accent);
}

.account-trigger__chevron {
  width: 13px;
  height: 13px;
  opacity: 0.55;
  color: var(--sk-ink-muted);
}

.account-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  flex: none;
  border-radius: 7px;
  background: var(--sk-ink);
  color: var(--sk-ink-fg);
  font-size: 11px;
  font-weight: 700;
}

.account-avatar--lg {
  width: 30px;
  height: 30px;
  border-radius: var(--sk-r-chip);
  font-size: 12px;
}

.account-avatar__icon {
  width: 14px;
  height: 14px;
}

/* Icon-only triggers cannot carry the 미검증 word, so unverified is marked
   with a warn dot in the corner; the word itself is in the menu. */
.sk-unverified-dot::after {
  content: '';
  position: absolute;
  top: 2px;
  right: 2px;
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: var(--sk-warn);
}

/* A label, not a button (DESIGN.md: warn borders at 32% alpha so badges read
   as labels). Chip radius, never rounded-full. */
.sk-unverified-badge {
  display: inline-flex;
  flex: none;
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
