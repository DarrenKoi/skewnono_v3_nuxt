<script setup lang="ts">
import type { HeaderLink } from '~/utils/headerNav'
import { canReleaseDeclaration, displayName, isUnverifiedDeclaration } from '~/utils/identityDisplay'
import { headerLinksIn, isHeaderLinkActive } from '~/utils/headerNav'

// App 정보 — the pages about the app itself (앱 소개 / 사용 통계 / 세팅) and, above them,
// who the app thinks the caller is. This grew out of IdentityPill: the pill was already a
// popover naming the caller, so those three pages cost no new header slot.
//
// The trigger says 'App 정보', not the caller's first syllable. The avatar letter was a
// person's surname standing for a menu that is mostly not about that person — it named the
// content of one block in the panel rather than the panel — and an unlabelled square beside
// the labelled 실험실 pill made the two menus look like different kinds of thing. The name
// is now inside the panel only, where it has room to be the full name plus 사번.
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

// The panel's avatar is the name's first character — a Korean name has no spaces to build
// initials from, so the first syllable is the whole convention. Only drawn beside a real
// identity, so the empty case never reaches the template.
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
  <!-- align="end": the panel is far wider than the trigger, and this is the last thing
       in the header — centred it would run off the right edge. -->
  <UPopover
    v-model:open="open"
    :content="{ align: 'end' }"
  >
    <!-- Same pill as 실험실, for the same reason: two menus side by side must read as one
         kind of control, and a header word is cheaper to parse than an icon to hover. -->
    <button
      type="button"
      class="sk-nav-pill sk-nav-pill--sm"
      :class="hasActiveLink ? 'sk-nav-pill--active sk-nav-accent' : 'sk-nav-pill--rest'"
      :aria-label="identity ? `App 정보 — ${displayName(identity)}` : 'App 정보'"
      aria-haspopup="menu"
      :aria-expanded="open"
    >
      <UIcon
        name="i-lucide-info"
        class="account-trigger__icon"
      />
      App 정보
      <UIcon
        :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        class="account-trigger__icon account-trigger__chevron"
      />
    </button>

    <template #content>
      <div class="w-[262px] p-1.5">
        <div
          v-if="identity"
          class="mb-1 flex items-center gap-2.5 border-b border-(--sk-border-soft) px-2.5 pb-2.5 pt-2"
        >
          <span
            class="account-avatar"
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
          aria-label="App 정보"
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
.account-trigger__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.account-trigger__chevron {
  opacity: 0.6;
}

/* Panel-only now: the header trigger carries the menu's name instead of the caller's
   first syllable, so the letter is drawn once, beside the full name it abbreviates. */
.account-avatar {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  flex: none;
  border-radius: var(--sk-r-chip);
  background: var(--sk-ink);
  color: var(--sk-ink-fg);
  font-size: 12px;
  font-weight: 700;
}

/* A label, not a button (DESIGN.md: warn borders at 32% alpha so badges read
   as labels). Chip radius, never rounded-full. */
.sk-unverified-badge {
  display: inline-flex;
  flex: none;
  align-items: center;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--sk-r-chip);
  background: var(--sk-warn-soft);
  border: 1px solid var(--sk-warn-border);
  color: var(--sk-ink);
}
</style>
