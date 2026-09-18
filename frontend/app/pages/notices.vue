<script setup lang="ts">
const { notices, isNew, markAllSeen } = useNotices()

// Snapshot before marking: opening the page clears the header badge at once, but the
// notices that were new on arrival keep their N for this visit, so the reader can still
// see what they came for.
const newOnArrival = new Set(notices.filter(isNew).map(notice => notice.date))
markAllSeen()
</script>

<template>
  <div class="mx-auto max-w-4xl px-4 py-8">
    <h1 class="sk-page-title">
      공지사항
    </h1>
    <p class="mt-2 mb-6 sk-body text-(--sk-ink-muted)">
      SKEWNONO 에 새로 추가되거나 바뀐 내용을 알려 드립니다.
    </p>

    <ol class="space-y-5">
      <li
        v-for="notice in notices"
        :key="notice.date"
      >
        <UCard class="dashboard-surface">
          <template #header>
            <div class="flex items-center gap-2">
              <span class="sk-value-num text-(--sk-ink-muted)">{{ notice.date }}</span>
              <NoticeNewBadge v-if="newOnArrival.has(notice.date)" />
            </div>
            <h2 class="mt-1 sk-title">
              {{ notice.title }}
            </h2>
          </template>

          <div class="space-y-4">
            <section
              v-for="section in notice.sections"
              :key="section.area"
            >
              <h3 class="sk-label">
                {{ section.area }}
              </h3>
              <ul class="mt-1.5 list-disc space-y-1 pl-5 marker:text-(--sk-ink-subtle)">
                <li
                  v-for="(item, index) in section.items"
                  :key="index"
                  class="sk-body"
                >
                  {{ item }}
                </li>
              </ul>
            </section>
          </div>
        </UCard>
      </li>
    </ol>
  </div>
</template>
