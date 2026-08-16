<script setup lang="ts">
import type { HeaderLink } from '~/utils/headerNav'
import { useNavigationStore } from '~/stores/navigation'
import { buildFabSegment, canonicalFabList, DEFAULT_FAB } from '~/utils/fab'
import { isSingleFabFeature } from '~/utils/features'
import { headerLinksIn, isHeaderLinkActive } from '~/utils/headerNav'

// 실험실 — the tools that are not tied to a feature tab. Before 2026-08-15 these were four
// of eight unlabelled icons in the header; the icons had to be hovered to be read, and two
// of them collided with icons the feature tabs already used. One labelled trigger with a
// named menu behind it costs one click and removes both problems.
//
// Every row here asks something of a CD-SEM or HV-SEM tool, so the trigger is drawn only
// where a tool is in scope — the same rule as the feature tabs. On the landing hub the
// visitor is still choosing a tool, and a menu of that tool's instruments would be answering
// a question they have not asked yet. (API 리스트 moved to App 정보 for the same reason: it
// lists this app's endpoints, not a tool's, so it must stay reachable from the hub.)

const route = useRoute()
const nav = useNavigationStore()

const isToolScoped = useToolScopedRoute()

const open = ref(false)
const links = headerLinksIn('lab')

// The fab-scoped rows jump to the remembered tool/fab selection (default cd-sem / R3
// before any ebeam visit). Multi-fab-capable rows use the full fabs list so a multi-fab
// selection survives the URL round-trip; single-fab pages (tttm, pm-tune — see
// SINGLE_FAB_FEATURES) get the primary fab only, because their useFabRoute would
// immediately collapse a multi segment anyway and the label below must not promise
// fabs the page will drop.
//
// 라이브 알람 follows the remembered tool type (cd-sem and hv-sem both have that board);
// TTTM and PM-Tune are cd-sem only, gated that way in useNavigation, so they pin their own.
const liveAlarmToolType = computed(() => nav.toolType.value === 'hv-sem' ? 'hv-sem' : 'cd-sem')
const CD_SEM_ONLY_TOOL_TYPE = 'cd-sem'

const toolTypeFor = (link: HeaderLink) =>
  link.scope === 'tttm' || link.scope === 'pm-tune'
    ? CD_SEM_ONLY_TOOL_TYPE
    : liveAlarmToolType.value

const fabsFor = (link: HeaderLink) => {
  const fabs = canonicalFabList(nav.fabs.value)
  const resolved = fabs.length > 0 ? fabs : [DEFAULT_FAB]
  return link.scope && isSingleFabFeature(link.scope) ? resolved.slice(0, 1) : resolved
}

// Resolved per row rather than per menu: this used to return the live-alarm target for
// ANY `to: null` link, which was correct only while there was exactly one of them.
// `scope` doubles as the route's last segment, which holds for every row today
// ('live-alarm', 'tttm', 'pm-tune'). Give a future scope a name that is also its
// segment, or split the two apart here rather than letting the link quietly point at
// nothing.
const linkTarget = (link: HeaderLink) =>
  link.to ?? `/ebeam/${toolTypeFor(link)}/${buildFabSegment(fabsFor(link))}/${link.scope}`

// These rows' destinations move under the user, so each says where it goes — the same
// fab list the link actually uses, single-fab rows included.
const scopeLabel = (link: HeaderLink) =>
  `${toolTypeFor(link).toUpperCase()} · ${fabsFor(link).join(', ')}`

const isActive = (link: HeaderLink) => isHeaderLinkActive(link, route.path)

// The trigger itself goes ink when the current page is inside the menu, so the header
// still answers "where am I" without being opened.
const hasActiveLink = computed(() => links.some(isActive))
</script>

<template>
  <!-- align="end": the panel is wider than its trigger, and both menus live at the right
       edge of the header — centred, the 실험실 panel would hang over 계정 and read as
       belonging to it. -->
  <UPopover
    v-if="isToolScoped"
    v-model:open="open"
    :content="{ align: 'end' }"
  >
    <button
      type="button"
      class="sk-nav-pill sk-nav-pill--sm"
      :class="hasActiveLink ? 'sk-nav-pill--active sk-nav-accent' : 'sk-nav-pill--rest'"
      aria-haspopup="menu"
      :aria-expanded="open"
    >
      <UIcon
        name="i-lucide-flask-conical"
        class="lab-trigger__icon"
      />
      실험실
      <UIcon
        :name="open ? 'i-lucide-chevron-up' : 'i-lucide-chevron-down'"
        class="lab-trigger__icon lab-trigger__chevron"
      />
    </button>

    <template #content>
      <div class="w-[300px] p-1.5">
        <div class="flex items-center justify-between gap-2 px-2.5 pb-1.5 pt-2">
          <span class="sk-eyebrow">실험실</span>
          <span class="lab-beta">BETA</span>
        </div>
        <nav
          aria-label="실험실"
          class="flex flex-col gap-0.5"
        >
          <NavHeaderMenuItem
            v-for="link in links"
            :key="link.label"
            :label="link.label"
            :icon="link.icon"
            :description="link.description"
            :to="linkTarget(link)"
            :active="isActive(link)"
            :separated="link.separated"
            @select="open = false"
          >
            <template
              v-if="link.to === null"
              #note
            >
              <span class="lab-scope">{{ scopeLabel(link) }}</span>
            </template>
          </NavHeaderMenuItem>
        </nav>
      </div>
    </template>
  </UPopover>
</template>

<style scoped>
.lab-trigger__icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.lab-trigger__chevron {
  opacity: 0.6;
}

/* BETA is a label, not a button — warn borders at 32% alpha, chip radius, never
   rounded-full (DESIGN.md §Tags / Badges). */
.lab-beta {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  font-size: 10px;
  font-weight: 600;
  border-radius: var(--sk-r-chip);
  background: var(--sk-warn-soft);
  border: 1px solid var(--sk-warn-border);
  color: var(--sk-ink);
}

/* Which tool and fab the fab-scoped row will land on. Mono because it is an identifier
   pair, matching the meta-bar eyebrow that names the same scope on the page itself. */
.lab-scope {
  padding: 0 5px;
  font-family: var(--font-mono);
  font-size: 10px;
  border-radius: var(--sk-r-chip);
  background: var(--sk-muted-surface);
  border: 1px solid var(--sk-border-soft);
  white-space: nowrap;
}
</style>
