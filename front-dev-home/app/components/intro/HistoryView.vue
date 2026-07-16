<template>
  <section
    class="space-y-6"
    aria-labelledby="history-title"
  >
    <header class="border-b border-(--sk-border) pb-6">
      <div class="flex items-center gap-2 text-sm font-semibold text-(--sk-ink-muted)">
        <UIcon
          name="i-lucide-history"
          class="h-4 w-4"
        />
        <span>History</span>
      </div>
      <div class="mt-3 max-w-3xl">
        <h1
          id="history-title"
          class="sk-page-title md:text-4xl"
        >
          SKEWNONO History
        </h1>
        <p class="mt-3 sk-body leading-7 md:text-base">
          2024년 첫 버전부터 현재 v3까지, SKEWNONO가 장비 조회 도구에서
          통합 Metrology Workspace로 발전해 온 과정입니다.
        </p>
      </div>
    </header>

    <ol class="space-y-5">
      <li
        v-for="release in skewnonoHistory"
        :key="release.version"
        class="grid gap-3 md:grid-cols-[7rem_minmax(0,1fr)] md:gap-5"
      >
        <div class="pt-1">
          <div class="sk-eyebrow">
            {{ release.releasedAt }}
          </div>
          <div class="mt-1 text-xl font-semibold text-zinc-950 dark:text-white">
            {{ release.version }}
          </div>
        </div>

        <article
          class="rounded-lg border bg-white p-5 dark:bg-zinc-950"
          :class="release.current ? 'border-zinc-900 dark:border-zinc-100' : 'border-(--sk-border)'"
        >
          <div class="flex flex-wrap items-start justify-between gap-3">
            <h2 class="sk-heading">
              {{ release.version }} 주요 변화
            </h2>
            <span
              v-if="release.current"
              class="rounded-full bg-zinc-900 px-2.5 py-1 text-xs font-semibold text-white dark:bg-zinc-100 dark:text-zinc-950"
            >
              현재 버전
            </span>
          </div>
          <p class="mt-3 sk-body leading-7">
            {{ release.summary }}
          </p>

          <div
            v-if="release.current"
            class="mt-5 grid gap-3 sm:grid-cols-2"
          >
            <section
              v-for="feature in release.features"
              :key="feature.title"
              class="rounded-md bg-zinc-50 p-4 dark:bg-zinc-900"
            >
              <UIcon
                :name="feature.icon"
                class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
              />
              <h3 class="mt-3 sk-title">
                {{ feature.title }}
              </h3>
              <p
                v-if="feature.description"
                class="mt-2 sk-meta leading-5"
              >
                {{ feature.description }}
              </p>
            </section>
          </div>

          <ul
            v-else
            class="mt-4 flex flex-wrap gap-2"
            aria-label="주요 기능"
          >
            <li
              v-for="feature in release.features"
              :key="feature.title"
              class="flex items-center gap-1.5 rounded-md border border-(--sk-border) px-3 py-2 sk-meta"
            >
              <UIcon
                :name="feature.icon"
                class="h-4 w-4"
              />
              <span>{{ feature.title }}</span>
            </li>
          </ul>
        </article>
      </li>
    </ol>
  </section>
</template>

<script setup lang="ts">
import { skewnonoHistory } from '~/data/skewnonoHistory'
</script>
