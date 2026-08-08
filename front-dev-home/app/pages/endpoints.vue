<script setup lang="ts">
import { apiGroups, authNotes, BASE_URL, examples, tokenSteps } from '~/data/apiCatalog'
import type { ApiGroup } from '~/data/apiCatalog'
import { curlExample, methodColor, pythonExample } from '~/utils/apiSnippets'

useHead({
  title: 'API 리스트 | SKEWNONO'
})

const totalEndpoints = computed(() =>
  apiGroups.reduce((count, group) => count + group.endpoints.length, 0)
)

const activePanel = ref('tokens')
const selectedApiGroup = computed<ApiGroup>(() =>
  apiGroups.find(group => group.name === activePanel.value) ?? apiGroups[0]!
)
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8 lg:px-8">
    <div class="grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="lg:sticky lg:top-0 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
        <nav
          class="space-y-6 border-b border-(--sk-border) pb-5 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-6"
          aria-label="Information sections"
        >
          <div>
            <p class="mb-2 sk-eyebrow">
              시작하기
            </p>
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition"
              :class="activePanel === 'tokens' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
              @click="activePanel = 'tokens'"
            >
              <UIcon
                name="i-lucide-key-round"
                class="h-4 w-4 shrink-0"
              />
              <span>API Token 사용법</span>
            </button>
          </div>

          <div>
            <p class="mb-2 sk-eyebrow">
              API 카탈로그
            </p>
            <div class="space-y-1">
              <button
                v-for="group in apiGroups"
                :key="group.name"
                type="button"
                class="flex w-full items-center justify-between gap-2 rounded-md px-3 py-2 text-left text-sm transition"
                :class="activePanel === group.name ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
                @click="activePanel = group.name"
              >
                <span class="flex min-w-0 items-center gap-2">
                  <UIcon
                    :name="group.icon"
                    class="h-4 w-4 shrink-0"
                  />
                  <span class="truncate">{{ group.name }}</span>
                </span>
                <span
                  class="rounded-full px-2 py-0.5 text-[11px]"
                  :class="activePanel === group.name ? 'bg-white/15 dark:bg-zinc-950/10' : 'bg-zinc-100 text-(--sk-ink-muted) dark:bg-zinc-900 dark:text-zinc-400'"
                >
                  {{ group.endpoints.length }}
                </span>
              </button>
            </div>
          </div>
        </nav>
      </aside>

      <main class="min-w-0">
        <section
          v-if="activePanel === 'tokens'"
          class="space-y-8"
        >
          <header class="border-b border-(--sk-border) pb-6">
            <div class="flex items-center gap-2 text-sm font-semibold text-(--sk-ink-muted)">
              <UIcon
                name="i-lucide-plug"
                class="h-4 w-4"
              />
              <span>Developer API</span>
            </div>
            <div class="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div class="max-w-3xl">
                <h1 class="sk-page-title md:text-4xl">
                  API Token 사용법
                </h1>
                <p class="mt-3 sk-body leading-7 md:text-base">
                  Settings에서 개인 API token을 발급하면 SKEWNONO 화면을 열지 않고도 각자 개발 환경, 분석 노트북, 배치 스크립트에서 필요한 데이터를 직접 가져갈 수 있습니다.
                </p>
              </div>
              <UButton
                to="/settings#api-tokens"
                icon="i-lucide-settings"
                color="neutral"
                variant="outline"
              >
                Settings에서 발급
              </UButton>
            </div>
          </header>

          <section class="grid gap-6 xl:grid-cols-[1fr_1.1fr]">
            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-link"
                  class="h-5 w-5 text-zinc-600 dark:text-zinc-300"
                />
                <h2 class="sk-heading">
                  Base URL
                </h2>
              </div>
              <div class="rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950">
                <code class="sk-value-num text-base">{{ BASE_URL }}</code>
                <p class="mt-3 sk-body leading-6">
                  모든 endpoint는 이 base URL 뒤에 경로를 붙여 호출합니다. 발급받은 토큰을 Authorization: Bearer 헤더에 넣으면 사내망 어느 개발 환경에서든 동일하게 동작합니다.
                </p>
              </div>
            </div>

            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-list-checks"
                  class="h-5 w-5 text-zinc-600 dark:text-zinc-300"
                />
                <h2 class="sk-heading">
                  발급 순서
                </h2>
              </div>
              <ol class="grid gap-3">
                <li
                  v-for="(step, index) in tokenSteps"
                  :key="step.title"
                  class="flex gap-3 rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950"
                >
                  <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-zinc-900 text-sm font-semibold text-white dark:bg-zinc-100 dark:text-zinc-950">
                    {{ index + 1 }}
                  </span>
                  <span>
                    <span class="block sk-title">{{ step.title }}</span>
                    <span class="mt-1 block sk-body leading-6">{{ step.detail }}</span>
                  </span>
                </li>
              </ol>
            </div>
          </section>

          <section class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <div>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-shield-check"
                  class="h-5 w-5 text-zinc-600 dark:text-zinc-300"
                />
                <h2 class="sk-heading">
                  토큰 주의사항
                </h2>
              </div>
              <ul class="mt-4 space-y-3 sk-body leading-6">
                <li
                  v-for="note in authNotes"
                  :key="note"
                  class="flex gap-2"
                >
                  <UIcon
                    name="i-lucide-check"
                    class="mt-1 h-4 w-4 shrink-0 text-zinc-900 dark:text-zinc-100"
                  />
                  <span>{{ note }}</span>
                </li>
              </ul>
            </div>

            <div>
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-terminal"
                  class="h-5 w-5 text-zinc-600 dark:text-zinc-300"
                />
                <h2 class="sk-heading">
                  호출 예시
                </h2>
              </div>
              <div class="mt-4 grid gap-4">
                <div
                  v-for="example in examples"
                  :key="example.title"
                  class="overflow-hidden rounded-lg border border-(--sk-border) bg-white dark:bg-zinc-950"
                >
                  <div class="border-b border-(--sk-border) px-4 py-3 sk-title">
                    {{ example.title }}
                  </div>
                  <pre class="whitespace-pre-wrap break-words p-4 text-xs leading-6"><code>{{ example.code }}</code></pre>
                </div>
              </div>
            </div>
          </section>
        </section>

        <section
          v-else
          class="space-y-6"
        >
          <header class="border-b border-(--sk-border) pb-6">
            <div class="flex items-center gap-2 text-sm font-semibold text-(--sk-ink-muted)">
              <UIcon
                name="i-lucide-list-tree"
                class="h-4 w-4"
              />
              <span>API 카탈로그</span>
            </div>
            <div class="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div class="max-w-3xl">
                <div class="flex items-center gap-3">
                  <UIcon
                    :name="selectedApiGroup.icon"
                    class="h-7 w-7 text-zinc-700 dark:text-zinc-200"
                  />
                  <h1 class="sk-page-title md:text-4xl">
                    {{ selectedApiGroup.name }}
                  </h1>
                </div>
                <p class="mt-3 sk-body leading-7 md:text-base">
                  {{ selectedApiGroup.description }}
                </p>
                <p class="mt-2 text-xs text-(--sk-ink-muted)">
                  Python 예시는 'API Token 사용법' 탭의 공통 준비 코드(BASE_URL, HEADERS)를 먼저 선언한 뒤 실행합니다.
                </p>
              </div>
              <div class="grid grid-cols-2 gap-3 sm:flex">
                <div class="rounded-lg border border-(--sk-border) bg-white px-4 py-3 dark:bg-zinc-950">
                  <div class="sk-meta">
                    선택 항목
                  </div>
                  <div class="mt-1 text-xl font-semibold">
                    {{ selectedApiGroup.endpoints.length }}
                  </div>
                </div>
                <div class="rounded-lg border border-(--sk-border) bg-white px-4 py-3 dark:bg-zinc-950">
                  <div class="sk-meta">
                    전체 Endpoint
                  </div>
                  <div class="mt-1 text-xl font-semibold">
                    {{ totalEndpoints }}
                  </div>
                </div>
              </div>
            </div>
          </header>

          <div class="grid gap-4">
            <article
              v-for="endpoint in selectedApiGroup.endpoints"
              :key="`${endpoint.method}:${endpoint.path}`"
              class="rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950"
            >
              <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div class="min-w-0 space-y-2">
                  <div class="flex flex-wrap items-center gap-2">
                    <UBadge
                      :label="endpoint.method"
                      :color="methodColor(endpoint.method)"
                      variant="subtle"
                    />
                    <code class="break-all sk-value-num">{{ endpoint.path }}</code>
                  </div>
                  <p class="sk-body leading-6">
                    {{ endpoint.summary }}
                  </p>
                </div>
                <div class="shrink-0">
                  <UBadge
                    :label="endpoint.auth"
                    color="neutral"
                    variant="outline"
                  />
                </div>
              </div>

              <dl class="mt-4 grid gap-3">
                <div class="rounded-md bg-zinc-50 p-3 dark:bg-zinc-900">
                  <dt class="sk-label">
                    Parameters
                  </dt>
                  <dd class="mt-2">
                    <p
                      v-if="endpoint.args.length === 0"
                      class="sk-body"
                    >
                      없음
                    </p>
                    <ul
                      v-else
                      class="space-y-1.5"
                    >
                      <li
                        v-for="arg in endpoint.args"
                        :key="`${arg.kind}:${arg.name}`"
                        class="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-sm"
                      >
                        <code class="sk-value-num">{{ arg.name }}</code>
                        <span class="rounded bg-zinc-200 px-1.5 py-0.5 text-[10px] font-medium text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">{{ arg.kind }}</span>
                        <span
                          class="text-[10px] font-semibold"
                          :class="arg.required ? 'text-zinc-900 dark:text-zinc-100' : 'text-(--sk-ink-muted)'"
                        >{{ arg.required ? 'required' : 'optional' }}</span>
                        <span class="sk-body">{{ arg.note }}</span>
                      </li>
                    </ul>
                  </dd>
                </div>
                <div class="rounded-md bg-zinc-50 p-3 dark:bg-zinc-900">
                  <dt class="sk-label">
                    Response
                  </dt>
                  <dd class="mt-1">
                    <code class="break-words sk-value-num">{{ endpoint.response }}</code>
                  </dd>
                </div>
              </dl>

              <div
                v-if="endpoint.auth !== '사람 세션만'"
                class="mt-4 grid gap-3"
              >
                <div class="overflow-hidden rounded-md bg-zinc-50 dark:bg-zinc-900">
                  <div class="border-b border-(--sk-border) px-3 py-2 sk-label">
                    curl
                  </div>
                  <pre class="whitespace-pre-wrap break-words p-3 text-[11px] leading-5 text-zinc-600 dark:text-zinc-300"><code>{{ curlExample(endpoint) }}</code></pre>
                </div>
                <div class="overflow-hidden rounded-md bg-zinc-50 dark:bg-zinc-900">
                  <div class="border-b border-(--sk-border) px-3 py-2 sk-label">
                    Python
                  </div>
                  <pre class="whitespace-pre-wrap break-words p-3 text-[11px] leading-5 text-zinc-600 dark:text-zinc-300"><code>{{ pythonExample(endpoint) }}</code></pre>
                </div>
              </div>
              <p
                v-else
                class="mt-4 rounded-md bg-zinc-50 p-3 text-sm text-(--sk-ink-muted) dark:bg-zinc-900"
              >
                이 endpoint는 브라우저 세션 전용입니다. Settings의 API Tokens 화면에서 발급/폐기를 수행하십시오.
              </p>
            </article>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>
