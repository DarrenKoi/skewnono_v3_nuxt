<script setup lang="ts">
import type { Notice, NoticeCategory } from '~/data/notices'

// 공지사항 as a timeline (Claude Design "Notices Timeline"): 중요 notices pinned on top,
// the rest grouped by month down a date rail, each card folded to its title until opened.
const { notices, lastSeen, isNew, markAllSeen } = useNotices()

const PER_PAGE = 10
const CATEGORIES: NoticeCategory[] = ['기능추가', '수정', '공지']

const query = ref('')
const category = ref<NoticeCategory | null>(null)
const area = ref<string | null>(null)
const unreadOnly = ref(false)
const page = ref(1)
const open = ref(new Set<string>())

// Any filter change starts over at page 1, or a narrowed list could leave you on an empty page.
watch([query, category, area, unreadOnly], () => {
  page.value = 1
})

const filter = computed(() => ({
  query: query.value,
  category: category.value,
  area: area.value,
  unreadAfter: unreadOnly.value ? lastSeen.value : null
}))

const pinned = computed(() => notices.filter(n => n.pinned && matchesNotice(n, filter.value)))
const timeline = computed(() => notices.filter(n => !n.pinned && matchesNotice(n, filter.value)))
const timelineTotal = notices.filter(n => !n.pinned).length

const pageCount = computed(() => Math.max(1, Math.ceil(timeline.value.length / PER_PAGE)))
const pageStart = computed(() => (Math.min(page.value, pageCount.value) - 1) * PER_PAGE)
const pageRows = computed(() => timeline.value.slice(pageStart.value, pageStart.value + PER_PAGE))
const months = computed(() => groupNoticesByMonth(pageRows.value))

const unreadCount = computed(() => notices.filter(isNew).length)

// A category with no notices yet would be a chip that can only ever empty the list.
const categoryChips = computed(() => CATEGORIES
  .map(label => ({ label, count: notices.filter(n => n.category === label).length }))
  .filter(chip => chip.count > 0))

const visibleDates = computed(() => [...pinned.value, ...pageRows.value].map(n => n.date))
const allOpen = computed(() => visibleDates.value.length > 0 && visibleDates.value.every(d => open.value.has(d)))

const toggle = (date: string) => {
  const next = new Set(open.value)
  if (!next.delete(date)) next.add(date)
  open.value = next
}
const toggleAll = () => {
  open.value = allOpen.value ? new Set() : new Set(visibleDates.value)
}
const resetFilters = () => {
  query.value = ''
  category.value = null
  area.value = null
  unreadOnly.value = false
}

const dayLabel = (notice: Notice) => {
  const [, month, day] = notice.date.split('-')
  return `${month}월 ${day}일`
}
const changeCount = (notice: Notice) => notice.sections.reduce((sum, s) => sum + s.items.length, 0)

// The month headers pin directly under the filter bar, which wraps to a second row on a
// narrow pane — so the offset is measured, never hard-coded.
const toolbar = ref<HTMLElement | null>(null)
const toolbarHeight = ref(58)
let observer: ResizeObserver | null = null
const onKey = (event: KeyboardEvent) => {
  if (event.key === 'Escape') open.value = new Set()
}
onMounted(() => {
  window.addEventListener('keydown', onKey)
  if (!toolbar.value) return
  observer = new ResizeObserver(() => {
    if (toolbar.value) toolbarHeight.value = Math.round(toolbar.value.offsetHeight)
  })
  observer.observe(toolbar.value)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  observer?.disconnect()
})
</script>

<template>
  <div class="mx-auto max-w-5xl px-4 pb-14 sm:px-12">
    <div class="flex flex-wrap items-end justify-between gap-6 pt-6">
      <div class="min-w-0">
        <h1 class="sk-page-title">
          공지사항
        </h1>
        <p class="mt-2 sk-body text-(--sk-ink-muted)">
          SKEWNONO 에 새로 추가되거나 바뀐 내용을 알려 드립니다.
        </p>
      </div>
      <div
        v-if="unreadCount > 0"
        class="flex flex-none items-center gap-2.5"
      >
        <span class="inline-flex items-center gap-1.5 text-[13px] text-(--sk-ink-muted)">
          <span class="notice-count">{{ unreadCount }}</span>
          건 읽지 않음
        </span>
        <UButton
          color="neutral"
          variant="outline"
          size="sm"
          label="모두 읽음 처리"
          @click="markAllSeen"
        />
      </div>
    </div>

    <div
      ref="toolbar"
      class="sticky top-0 z-30 mt-5 bg-(--sk-canvas) pt-3 pb-2.5"
    >
      <div class="flex flex-wrap items-center gap-2">
        <UInput
          v-model="query"
          type="search"
          icon="i-lucide-search"
          placeholder="제목·내용 검색"
          class="w-[260px] flex-none"
        />

        <div
          role="group"
          aria-label="카테고리 필터"
          class="flex gap-1"
        >
          <SkChip
            label="전체"
            :count="notices.length"
            :active="category === null"
            @click="category = null"
          />
          <SkChip
            v-for="chip in categoryChips"
            :key="chip.label"
            :label="chip.label"
            :count="chip.count"
            :active="category === chip.label"
            @click="category = chip.label"
          />
        </div>

        <SkChip
          label="읽지 않은 것만"
          :active="unreadOnly"
          @click="unreadOnly = !unreadOnly"
        />

        <SkChip
          v-if="area"
          :label="`영역 · ${area}`"
          icon="i-lucide-x"
          active
          @click="area = null"
        />

        <span class="min-w-2 flex-1" />

        <UButton
          color="neutral"
          variant="ghost"
          size="sm"
          :icon="allOpen ? 'i-lucide-chevrons-down-up' : 'i-lucide-chevrons-up-down'"
          :label="allOpen ? '모두 접기' : '모두 펼치기'"
          @click="toggleAll"
        />
        <UBadge
          color="neutral"
          variant="subtle"
          class="font-mono tabular-nums"
        >
          {{ timeline.length }} / {{ timelineTotal }}
        </UBadge>
      </div>
    </div>

    <article
      v-for="notice in pinned"
      :key="notice.date"
      class="notice-card notice-card--pinned mb-2.5"
    >
      <div class="notice-head">
        <button
          type="button"
          class="notice-toggle"
          :aria-expanded="open.has(notice.date)"
          @click="toggle(notice.date)"
        >
          <span class="notice-cat notice-cat--pinned">중요</span>
          <span class="notice-title font-semibold">{{ notice.title }}</span>
          <NoticeNewBadge v-if="isNew(notice)" />
        </button>
        <span class="flex flex-none gap-1.5 max-sm:hidden">
          <button
            v-for="name in noticeAreas(notice).slice(0, 2)"
            :key="name"
            type="button"
            class="notice-tag"
            :class="{ 'notice-tag--on': area === name }"
            :aria-pressed="area === name"
            title="이 영역만 보기"
            @click="area = area === name ? null : name"
          >{{ name }}</button>
        </span>
        <span class="sk-value-num flex-none text-[12px] text-(--sk-ink-muted)">{{ notice.date }}</span>
        <button
          type="button"
          tabindex="-1"
          aria-hidden="true"
          class="notice-chevron-btn"
          @click="toggle(notice.date)"
        >
          <UIcon
            name="i-lucide-chevron-down"
            class="notice-chevron"
            :class="{ 'rotate-180': open.has(notice.date) }"
          />
        </button>
      </div>
      <NoticeBody
        v-if="open.has(notice.date)"
        :notice="notice"
        stacked
      />
    </article>

    <section
      v-for="month in months"
      :key="month.label"
    >
      <div
        class="sticky z-20 flex items-center gap-3 bg-(--sk-canvas) pt-3.5 pb-2.5"
        :style="{ top: `${toolbarHeight}px` }"
      >
        <h2 class="w-[92px] flex-none text-right font-mono text-[13px] font-semibold text-(--sk-ink-muted)">
          {{ month.label }}
        </h2>
        <span class="h-px flex-1 bg-(--sk-border)" />
        <span class="text-[13px] font-semibold text-(--sk-ink-muted)">{{ month.notices.length }}건</span>
      </div>

      <div
        v-for="notice in month.notices"
        :key="notice.date"
        class="grid grid-cols-[104px_minmax(0,1fr)]"
      >
        <div class="pt-5 pr-4 text-right">
          <span class="sk-value-num text-[13px] text-(--sk-ink-muted)">{{ dayLabel(notice) }}</span>
        </div>
        <div class="relative border-l border-(--sk-border) pl-6">
          <span
            aria-hidden="true"
            class="notice-dot"
            :class="{ 'notice-dot--new': isNew(notice) }"
          />
          <article
            class="notice-card my-2"
            :class="{ 'notice-card--open': open.has(notice.date) }"
          >
            <div class="notice-head">
              <button
                type="button"
                class="notice-toggle"
                :aria-expanded="open.has(notice.date)"
                @click="toggle(notice.date)"
              >
                <span class="notice-cat">{{ notice.category }}</span>
                <span
                  class="notice-title"
                  :class="isNew(notice) ? 'font-semibold' : 'font-normal'"
                >{{ notice.title }}</span>
                <NoticeNewBadge v-if="isNew(notice)" />
              </button>
              <span class="flex flex-none items-center gap-1.5 max-md:hidden">
                <button
                  v-for="name in noticeAreas(notice).slice(0, 2)"
                  :key="name"
                  type="button"
                  class="notice-tag"
                  :class="{ 'notice-tag--on': area === name }"
                  :aria-pressed="area === name"
                  title="이 영역만 보기"
                  @click="area = area === name ? null : name"
                >{{ name }}</button>
                <span
                  v-if="notice.sections.length > 2"
                  class="px-1.5 text-[12px] font-semibold text-(--sk-ink-muted)"
                >+{{ notice.sections.length - 2 }}</span>
              </span>
              <span class="flex-none text-[12px] whitespace-nowrap text-(--sk-ink-muted) max-sm:hidden">변경 {{ changeCount(notice) }}건</span>
              <button
                type="button"
                tabindex="-1"
                aria-hidden="true"
                class="notice-chevron-btn"
                @click="toggle(notice.date)"
              >
                <UIcon
                  name="i-lucide-chevron-down"
                  class="notice-chevron"
                  :class="{ 'rotate-180': open.has(notice.date) }"
                />
              </button>
            </div>
            <NoticeBody
              v-if="open.has(notice.date)"
              :notice="notice"
            />
          </article>
        </div>
      </div>
    </section>

    <div
      v-if="timeline.length === 0 && pinned.length === 0"
      class="dashboard-surface mt-3 rounded-[var(--sk-r-card)] px-4 py-14 text-center"
    >
      <p class="sk-body text-(--sk-ink-muted)">
        조건에 맞는 공지가 없습니다.
      </p>
      <UButton
        class="mt-3"
        color="neutral"
        variant="outline"
        size="sm"
        label="필터 지우기"
        @click="resetFilters"
      />
    </div>

    <div
      v-if="pageCount > 1"
      class="flex justify-center pt-7 pb-2"
    >
      <UPagination
        v-model:page="page"
        :total="timeline.length"
        :items-per-page="PER_PAGE"
      />
    </div>

    <p
      v-if="timeline.length > 0"
      class="mt-3.5 text-center sk-caption"
    >
      전체 {{ timeline.length }}건 중 {{ pageStart + 1 }}–{{ pageStart + pageRows.length }}건<template v-if="pinned.length">
        · 중요 공지는 모든 페이지에 표시됩니다.
      </template>
    </p>
  </div>
</template>

<style scoped>
.notice-count {
  display: inline-flex;
  min-width: 16px;
  height: 16px;
  align-items: center;
  justify-content: center;
  padding: 0 3px;
  border-radius: var(--sk-r-sidebar);
  background: var(--sk-brand);
  color: var(--sk-brand-fg);
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.notice-card {
  overflow: hidden;
  border: 1px solid var(--sk-border);
  border-radius: var(--sk-r-card);
  background: var(--sk-surface);
  box-shadow: 0 1px 0 rgba(0, 0, 0, 0.02), 0 8px 22px -18px rgba(0, 0, 0, 0.18);
}
.notice-card--open {
  border-color: var(--sk-ink-subtle);
}
/* 중요: the accent tint with the crimson left edge the active nav rows use. */
.notice-card--pinned {
  border-color: var(--sk-accent-border);
  background: var(--sk-accent-tint);
  box-shadow: inset 3px 0 0 0 var(--sk-accent);
}

.notice-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-right: 14px;
}
.notice-toggle {
  display: flex;
  min-width: 0;
  flex: 1;
  align-items: center;
  gap: 10px;
  padding: 14px 18px;
  text-align: left;
  cursor: pointer;
}
.notice-title {
  overflow: hidden;
  font-size: 15px;
  line-height: 1.4;
  color: var(--sk-ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.notice-chevron-btn {
  display: inline-flex;
  width: 26px;
  height: 26px;
  flex: none;
  align-items: center;
  justify-content: center;
  border-radius: var(--sk-r-sidebar);
  cursor: pointer;
}
.notice-chevron-btn:hover {
  background: var(--sk-muted-surface);
}
.notice-chevron {
  width: 16px;
  height: 16px;
  flex: none;
  color: var(--sk-ink-subtle);
  transition: transform 0.15s ease;
}

.notice-cat {
  display: inline-flex;
  height: 22px;
  flex: none;
  align-items: center;
  padding: 0 7px;
  border: 1px solid var(--sk-border);
  border-radius: var(--sk-r-chip);
  background: var(--sk-muted-surface);
  font-size: 11px;
  font-weight: 600;
  color: var(--sk-ink);
}
/* 기능추가 · 수정 · 공지 are peers: told apart by the label, never by a colour
   (DESIGN.md §Tags — three or more values get no colour encoding). */
.notice-cat--pinned {
  border-color: var(--sk-accent-border);
  background: var(--sk-accent-soft);
}

.notice-tag {
  padding: 3px 7px;
  border: 1px solid var(--sk-border-soft);
  border-radius: var(--sk-r-chip);
  background: var(--sk-muted-surface);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--sk-ink-muted);
  white-space: nowrap;
  cursor: pointer;
}
.notice-tag:hover {
  border-color: var(--sk-brand);
  color: var(--sk-brand-ink);
}
.notice-tag--on {
  border-color: var(--sk-brand);
  background: var(--sk-brand-soft);
  color: var(--sk-brand-ink);
}

/* The rail's node. A 9px dot at the smallest radius step reads round without leaving
   the radius scale. */
.notice-dot {
  position: absolute;
  top: 25px;
  left: -5px;
  width: 9px;
  height: 9px;
  border: 2px solid var(--sk-canvas);
  border-radius: var(--sk-r-sidebar);
  background: var(--sk-border);
}
.notice-dot--new {
  background: var(--sk-brand);
}
</style>
