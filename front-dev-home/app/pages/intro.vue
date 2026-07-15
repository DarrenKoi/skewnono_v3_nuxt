<template>
  <div class="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8 lg:px-8">
    <div class="grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="lg:sticky lg:top-0 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
        <nav
          class="space-y-6 border-b border-(--sk-border) pb-5 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-6"
          aria-label="페이지 안내"
        >
          <div>
            <p class="mb-2 sk-eyebrow">
              시작하기
            </p>
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition"
              :class="activePageId === 'overview' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
              @click="activePageId = 'overview'"
            >
              <UIcon
                name="i-lucide-sparkles"
                class="h-4 w-4 shrink-0"
              />
              <span>SKEWNONO 소개</span>
            </button>
          </div>

          <div
            v-for="section in guideSections"
            :key="section.key"
          >
            <p class="mb-2 flex items-center gap-1.5 sk-eyebrow">
              <UIcon
                :name="section.icon"
                class="h-3.5 w-3.5 shrink-0"
              />
              <span>{{ section.label }}</span>
            </p>
            <div class="space-y-1">
              <button
                v-for="page in section.pages"
                :key="page.id"
                type="button"
                class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition"
                :class="activePageId === page.id ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
                @click="activePageId = page.id"
              >
                <UIcon
                  :name="page.icon"
                  class="h-4 w-4 shrink-0"
                />
                <span class="truncate">{{ page.title }}</span>
              </button>
            </div>
          </div>
        </nav>
      </aside>

      <main class="min-w-0">
        <section
          v-if="activePageId === 'overview'"
          class="space-y-6"
        >
          <header class="border-b border-(--sk-border) pb-6">
            <div class="flex items-center gap-2 text-sm font-semibold text-(--sk-ink-muted)">
              <UIcon
                name="i-lucide-sparkles"
                class="h-4 w-4"
              />
              <span>소개</span>
            </div>
            <div class="mt-3 max-w-3xl">
              <h1 class="sk-page-title md:text-4xl">
                SKEWNONO
              </h1>
              <p class="mt-3 text-lg font-medium text-zinc-900 dark:text-zinc-100 md:text-xl">
                흩어진 측정·장비 데이터를 연결해 더 신뢰할 수 있는 판단으로
              </p>
              <p class="mt-3 sk-body leading-7 md:text-base">
                측정값 하나만으로는 공정이 제대로 진행되었는지, 문제의 원인이 어디에 있는지
                판단하기 어렵습니다. SKEWNONO는 CD와 Recipe 이력뿐 아니라 FDC, Beam Calibration,
                Hardware 설정값, BM/PM 일정 등 여러 데이터를 한곳에서 함께 확인해 엔지니어가
                데이터의 맥락과 신뢰도를 판단하도록 돕는 Metrology Workspace입니다.
              </p>
            </div>
          </header>

          <section class="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(280px,0.55fr)]">
            <div class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-lightbulb"
                  class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
                />
                <h2 class="sk-heading">
                  왜 SKEWNONO인가요?
                </h2>
              </div>
              <p class="mt-3 sk-body leading-7">
                장비에서 이상이 관찰되면 최근 해당 Recipe에서 오측정이 반복되었는지와 장비의
                Hardware 상태를 함께 살펴야 합니다. SKEWNONO는 서로 떨어져 있던 정보를 연결해
                장비, Wafer 상태, 공정 영향 중 어디에서 차이가 시작되었는지 관찰할 수 있게 합니다.
              </p>
            </div>

            <div class="rounded-lg border border-(--sk-border) bg-zinc-950 p-5 text-white dark:bg-zinc-100 dark:text-zinc-950">
              <div class="flex items-start gap-4">
                <img
                  src="/favicon.svg"
                  alt="나란히 기울어진 두 개의 CD Bar로 SKEW를 표현한 SKEWNONO 마크"
                  class="h-14 w-14 shrink-0 rounded-lg"
                >
                <div>
                  <div class="text-xs font-semibold uppercase tracking-[0.18em] text-(--sk-ink-muted)">
                    Name Story
                  </div>
                  <div class="mt-2 text-xl font-semibold">
                    SKEW + NO-NO
                  </div>
                </div>
              </div>
              <p class="mt-4 text-sm leading-6 text-zinc-300 dark:text-zinc-700">
                SKEW는 데이터가 한쪽으로 치우치거나 기준에서 어긋나는 현상입니다. 원인을 알 수 없는
                SKEW는 판단을 흐리고 모두를 지치게 합니다. 그래서 SKEW는 있어서는 안 될 NO-NO입니다.
              </p>
              <p class="mt-3 text-sm leading-6 text-zinc-300 dark:text-zinc-700">
                SKEWNONO는 빠르고 정확한 분석으로 SKEW의 참원인을 찾아 없애고자 합니다.
                나란히 기울어진 채 살짝 벌어진 두 개의 바는 CD Bar 측정과 그 사이에서 드러나는 SKEW를
                함께 나타냅니다.
              </p>
            </div>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <div class="max-w-3xl">
              <h2 class="sk-heading">
                함께 확인하는 데이터
              </h2>
              <p class="mt-2 sk-body leading-6">
                하나의 수치만 보는 대신 서로 다른 신호를 같은 맥락에서 연결해 확인합니다.
              </p>
            </div>
            <div class="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
              <div
                v-for="source in dataSources"
                :key="source.title"
                class="rounded-md border border-(--sk-border) p-4"
              >
                <UIcon
                  :name="source.icon"
                  class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
                />
                <h3 class="mt-3 sk-title">
                  {{ source.title }}
                </h3>
                <p class="mt-1 sk-meta leading-5">
                  {{ source.description }}
                </p>
              </div>
            </div>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <div class="max-w-3xl">
              <h2 class="sk-heading">
                문제를 확인하는 흐름
              </h2>
              <p class="mt-2 sk-body leading-6">
                SKEWNONO는 하나의 결과를 단정하기보다, 엔지니어가 근거를 넓혀 가며 원인에
                접근하도록 돕습니다.
              </p>
            </div>
            <ol class="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <li
                v-for="(step, index) in diagnosisSteps"
                :key="step.title"
                class="relative rounded-md bg-zinc-50 p-4 dark:bg-zinc-900"
              >
                <div class="text-xs font-semibold text-(--sk-ink-muted)">
                  {{ String(index + 1).padStart(2, '0') }}
                </div>
                <h3 class="mt-2 sk-title">
                  {{ step.title }}
                </h3>
                <p class="mt-2 sk-meta leading-5">
                  {{ step.description }}
                </p>
              </li>
            </ol>
          </section>

          <section>
            <div class="mb-4 max-w-3xl">
              <h2 class="sk-heading">
                주요 사용자
              </h2>
              <p class="mt-2 sk-body leading-6">
                공정, 소자, MI Engineer가 같은 데이터를 각자의 업무 관점에서 확인할 수 있도록
                개발하고 있습니다.
              </p>
            </div>
            <div class="grid gap-4 md:grid-cols-2">
              <div
                v-for="audience in audiences"
                :key="audience.title"
                class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950"
              >
                <div class="flex items-center gap-2">
                  <UIcon
                    :name="audience.icon"
                    class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
                  />
                  <h3 class="text-base font-semibold">
                    {{ audience.title }}
                  </h3>
                </div>
                <p class="mt-3 sk-body leading-6">
                  {{ audience.description }}
                </p>
              </div>
            </div>
          </section>

          <section class="grid gap-4 md:grid-cols-3">
            <div
              v-for="area in overviewAreas"
              :key="area.title"
              class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950"
            >
              <div class="flex items-center gap-2">
                <UIcon
                  :name="area.icon"
                  class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
                />
                <h2 class="text-base font-semibold">
                  {{ area.title }}
                </h2>
              </div>
              <p class="mt-3 sk-body leading-6">
                {{ area.description }}
              </p>
            </div>
          </section>

          <section class="grid gap-4 lg:grid-cols-2">
            <div class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-user-round-check"
                  class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
                />
                <h2 class="sk-heading">
                  현재: 판단 지원
                </h2>
              </div>
              <p class="mt-3 sk-body leading-7">
                현재 SKEWNONO는 여러 근거를 한곳에 모아 엔지니어가 직접 비교하고 판단하도록
                지원합니다. 화면의 데이터는 최종 판정을 대신하는 결과가 아니라, 문제를 더 빠르고
                넓게 살펴보기 위한 근거입니다.
              </p>
            </div>

            <div class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-bot"
                  class="h-5 w-5 text-zinc-700 dark:text-zinc-200"
                />
                <h2 class="sk-heading">
                  방향: Metrology AI Agent
                </h2>
              </div>
              <p class="mt-3 sk-body leading-7">
                장기적으로는 이상 징후 감지, 원인 후보 제시, 점검 순서 추천, 보고서 생성을 수행하며
                엔지니어와 함께 문제를 해결하는 AI Agent로 발전하는 것을 목표로 합니다.
              </p>
            </div>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div class="max-w-2xl">
                <h2 class="sk-heading">
                  원하는 데이터부터 바로 확인하세요
                </h2>
                <p class="mt-2 sk-body leading-6">
                  왼쪽 목록에서 페이지를 선택해 목적과 화면 구성을 확인한 뒤, 원하는 Navigation Tab으로
                  이동하면 됩니다. 화면 없이 데이터를 직접 가져가려는 개발자는 API 리스트를 참고하십시오.
                </p>
                <div class="mt-4 flex items-center gap-2 sk-meta">
                  <UIcon
                    name="i-lucide-message-circle"
                    class="h-4 w-4 shrink-0"
                  />
                  <span>문의: 기반기술전략&amp;안전 AX Part 최대영 TL · 큐브 DM</span>
                </div>
              </div>
              <UButton
                to="/endpoints"
                icon="i-lucide-plug"
                color="neutral"
                variant="outline"
                class="shrink-0"
              >
                API 리스트 열기
              </UButton>
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
                name="i-lucide-panels-top-left"
                class="h-4 w-4"
              />
              <span>페이지 안내</span>
            </div>
            <div class="mt-3 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div class="max-w-3xl">
                <div class="flex items-center gap-3">
                  <UIcon
                    :name="selectedPageGuide.icon"
                    class="h-7 w-7 text-zinc-700 dark:text-zinc-200"
                  />
                  <h1 class="sk-page-title md:text-4xl">
                    {{ selectedPageGuide.title }}
                  </h1>
                </div>
                <p class="mt-3 sk-body leading-7 md:text-base">
                  {{ selectedPageGuide.purpose }}
                </p>
              </div>
              <UButton
                :to="canOpenPage(selectedPageGuide.path) ? selectedPageGuide.path : undefined"
                icon="i-lucide-arrow-up-right"
                color="neutral"
                variant="outline"
                :disabled="!canOpenPage(selectedPageGuide.path)"
              >
                페이지 열기
              </UButton>
            </div>
          </header>

          <section class="grid gap-4 md:grid-cols-2">
            <div class="rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950">
              <div class="sk-eyebrow">
                Route
              </div>
              <code class="mt-2 block break-words sk-value-num">
                {{ selectedPageGuide.path }}
              </code>
            </div>
            <div class="rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950">
              <div class="sk-eyebrow">
                주요 사용자
              </div>
              <p class="mt-2 sk-body leading-6">
                {{ selectedPageGuide.users }}
              </p>
            </div>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <h2 class="sk-heading">
              화면 설명
            </h2>
            <p class="mt-3 sk-body leading-7">
              {{ selectedPageGuide.description }}
            </p>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <h2 class="sk-heading">
              참고 사항
            </h2>
            <ul class="mt-4 space-y-3 sk-body leading-6">
              <li
                v-for="note in selectedPageGuide.notes"
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
          </section>
        </section>
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
useHead({
  title: '소개 | SKEWNONO'
})

type GuideSection = 'common' | 'ebeam' | 'afm'

type PageGuide = {
  id: string
  title: string
  path: string
  icon: string
  section: GuideSection
  purpose: string
  description: string
  users: string
  notes: string[]
}

const overviewAreas = [
  {
    title: '공통',
    icon: 'i-lucide-layout-grid',
    description: '홈에서 작업 영역을 선택하고, 개인 설정과 사용 통계를 관리합니다. 운영자는 요청 로그를 추적합니다.'
  },
  {
    title: 'E-Beam Metrology',
    icon: 'i-lucide-microscope',
    description: 'CD-SEM, HV-SEM 장비 현황과 storage, hardware 상태를 확인하고 recipe 검색, TAT, fail issue, 측정 데이터 분석을 수행합니다.'
  },
  {
    title: 'AFM Metrology',
    icon: 'i-lucide-ruler',
    description: 'Fab별 AFM tool을 선택해 measurement file을 검색하고, 상세 profile 분석과 여러 측정의 비교를 수행합니다.'
  }
]

const dataSources = [
  {
    title: 'CD',
    icon: 'i-lucide-ruler',
    description: '측정 결과와 분포'
  },
  {
    title: 'FDC',
    icon: 'i-lucide-activity',
    description: '장비 상태 신호와 변화'
  },
  {
    title: 'Beam Calibration',
    icon: 'i-lucide-crosshair',
    description: 'Beam 보정 상태'
  },
  {
    title: 'Hardware Settings',
    icon: 'i-lucide-sliders-horizontal',
    description: '장비 설정값과 조건'
  },
  {
    title: 'BM/PM Schedule',
    icon: 'i-lucide-calendar-clock',
    description: '정비 일정과 전후 맥락'
  }
]

const diagnosisSteps = [
  {
    title: '차이 발견',
    description: '측정값이나 장비 동작에서 평소와 다른 SKEW를 발견합니다.'
  },
  {
    title: 'Recipe 이력 확인',
    description: '최근 같은 Recipe에서 오측정이나 Fail이 반복되었는지 확인합니다.'
  },
  {
    title: '장비 상태 연결',
    description: 'FDC, Calibration, Hardware 설정, BM/PM 이력을 함께 살펴봅니다.'
  },
  {
    title: '원인 범위 판단',
    description: '장비, Wafer 상태, 공정 영향 가운데 확인할 원인 범위를 좁힙니다.'
  }
]

const audiences = [
  {
    title: 'MI Engineer',
    icon: 'i-lucide-microscope',
    description: '장비 관리가 우선인 사용자는 장비 목록, Storage 상태, Hardware 화면에서 장비의 현재 상태와 유지보수 맥락을 자주 확인합니다.'
  },
  {
    title: '공정·소자 Engineer',
    icon: 'i-lucide-chart-no-axes-combined',
    description: 'Recipe와 측정 데이터, 분석 화면을 연결해 관찰된 차이가 Wafer 상태나 공정 영향과 관련되는지 살펴봅니다.'
  }
]

const sectionMeta: { key: GuideSection, label: string, icon: string }[] = [
  { key: 'common', label: '공통', icon: 'i-lucide-layout-grid' },
  { key: 'ebeam', label: 'E-Beam Metrology', icon: 'i-lucide-microscope' },
  { key: 'afm', label: 'AFM Metrology', icon: 'i-lucide-ruler' }
]

const pageGuides: PageGuide[] = [
  {
    id: 'home',
    title: '홈',
    path: '/',
    icon: 'i-lucide-house',
    section: 'common',
    purpose: 'SKEWNONO의 첫 진입 화면입니다.',
    description: '사용자가 CD-SEM, HV-SEM, AFM 같은 작업 영역을 선택하고 각 장비군의 대표 상태를 빠르게 확인하는 허브 역할을 합니다.',
    users: '일반 엔지니어, 장비 담당자, 신규 사용자',
    notes: ['장비군 선택은 사용자의 의도가 강하므로 상단에서 과도한 교차 전환을 강요하지 않습니다.']
  },
  {
    id: 'settings',
    title: 'Settings',
    path: '/settings',
    icon: 'i-lucide-settings',
    section: 'common',
    purpose: '개인 설정과 API Token을 관리하는 화면입니다.',
    description: '색상 모드, ECharts theme, API Token 발급/복사/폐기 기능을 제공합니다.',
    users: '개인 개발 환경에서 API를 호출하려는 사용자',
    notes: ['Token plaintext는 발급 직후 한 번만 보여주므로 바로 저장해야 합니다.']
  },
  {
    id: 'activity',
    title: '사용 통계',
    path: '/activity',
    icon: 'i-lucide-bar-chart-3',
    section: 'common',
    purpose: '사용자가 SKEWNONO를 어떻게 쓰고 있는지 확인하는 화면입니다.',
    description: '내 활동 요약과 관리자용 사용자 활동 통계를 보여줍니다.',
    users: '일반 사용자, 관리자',
    notes: ['관리자용 전체 사용자 통계는 권한이 필요합니다.']
  },
  {
    id: 'admin-logs',
    title: '운영 로그',
    path: '/admin/logs',
    icon: 'i-lucide-file-search',
    section: 'common',
    purpose: '운영자가 요청 로그와 오류를 추적하는 URL-only 화면입니다.',
    description: 'OpenSearch 기반 로그를 level, path, user_id 등으로 필터링해 장애나 사용자 요청 흐름을 확인합니다.',
    users: '관리자, 운영 담당자',
    notes: ['일반 내비게이션에는 노출하지 않고 URL 직접 입력으로 접근합니다.']
  },
  {
    id: 'admin-access',
    title: '접근 권한 관리',
    path: '/admin/access',
    icon: 'i-lucide-shield-check',
    section: 'common',
    purpose: 'X-사번 차단 규칙의 예외 허용 목록을 관리하는 관리자 전용 화면입니다.',
    description: 'X로 시작하는 사번은 기본 차단되며, 이 화면에서 예외로 허용하거나 최근 차단 시도를 확인해 원클릭으로 허용합니다.',
    users: '관리자',
    notes: ['일반 내비게이션에는 노출하지 않고 URL 직접 입력으로 접근합니다.']
  },
  {
    id: 'ebeam-entry',
    title: 'E-Beam 진입',
    path: '/ebeam/cd-sem, /ebeam/hv-sem',
    icon: 'i-lucide-microscope',
    section: 'ebeam',
    purpose: 'E-Beam 장비군별 Fab 진입점을 제공합니다.',
    description: 'CD-SEM 또는 HV-SEM을 선택한 뒤 Fab별 장비 목록, storage, recipe, 통계 기능으로 이동합니다.',
    users: 'E-Beam 엔지니어',
    notes: ['VeritySEM, Provision은 준비 중 화면으로 유지됩니다.']
  },
  {
    id: 'tool-inventory',
    title: '장비 목록',
    path: '/ebeam/{tool}/{fab}',
    icon: 'i-lucide-list-checks',
    section: 'ebeam',
    purpose: 'Fab별 E-Beam 장비 현황을 확인하는 기본 작업 화면입니다.',
    description: '장비 ID, model, vendor, IP, online/offline 상태를 탐색하고 필요한 장비의 상세 기능으로 이동합니다.',
    users: 'Fab 담당 엔지니어, 장비 담당자',
    notes: ['CSV 다운로드와 filtering은 장비 현황 확인을 빠르게 하기 위한 보조 기능입니다.']
  },
  {
    id: 'storage',
    title: 'Storage',
    path: '/ebeam/{tool}/{fab}/storage',
    icon: 'i-lucide-hard-drive',
    section: 'ebeam',
    purpose: '장비별 storage 사용량과 unavailable 상태를 확인합니다.',
    description: 'Fab, 장비, 사용률, capacity, recipe count 기준으로 storage 상태를 비교합니다.',
    users: '장비 storage 관리 담당자',
    notes: ['tool_slug는 cdsem 또는 hvsem입니다.']
  },
  {
    id: 'hardware',
    title: 'Hardware',
    path: '/ebeam/{tool}/{fab}/hardware',
    icon: 'i-lucide-cpu',
    section: 'ebeam',
    purpose: '장비별 hardware 보조 서비스 상태를 확인합니다.',
    description: 'BSM, FDC, BM/PM 같은 service를 선택하고 장비 또는 Fab 기준으로 payload를 조회합니다.',
    users: '장비 hardware 담당자',
    notes: ['같은 화면 컴포넌트를 CD-SEM과 HV-SEM에서 공유합니다.']
  },
  {
    id: 'recipe-search',
    title: 'Recipe Search',
    path: '/ebeam/{tool}/{fab}/recipe-search',
    icon: 'i-lucide-search-code',
    section: 'ebeam',
    purpose: 'Recipe catalog를 검색하고 상세 분석 화면으로 이동합니다.',
    description: 'recipe_name, Fab, tool type 기준으로 recipe를 찾고 open, lateral, meas history 화면으로 이어집니다.',
    users: 'Recipe 담당 엔지니어, 계측 조건 분석자',
    notes: ['행 전체 클릭보다 명시적인 action 버튼으로 상세 화면에 진입합니다.']
  },
  {
    id: 'recipe-open',
    title: 'Recipe Open',
    path: '/ebeam/{tool}/{fab}/recipe-search/open',
    icon: 'i-lucide-file-code',
    section: 'ebeam',
    purpose: '선택한 recipe의 open recipe 상세 구조를 확인합니다.',
    description: 'wafer measurement point, align point, image 정의, AMP 관련 정보를 확인합니다.',
    users: 'Recipe 분석자',
    notes: ['recipe_name query parameter가 필요합니다.']
  },
  {
    id: 'lateral',
    title: 'Lateral Recipe',
    path: '/ebeam/{tool}/{fab}/recipe-search/lateral',
    icon: 'i-lucide-git-compare',
    section: 'ebeam',
    purpose: '장비별 lateral recipe 보유 여부를 확인합니다.',
    description: '선택 recipe가 각 장비에서 준비되어 있는지 비교하고 미보유 장비를 파악합니다.',
    users: 'Recipe 배포 담당자',
    notes: ['Recipe Search에서 선택한 recipe context로 이동합니다.']
  },
  {
    id: 'meas-hist',
    title: 'Measurement History',
    path: '/ebeam/{tool}/{fab}/recipe-search/meas-hist',
    icon: 'i-lucide-history',
    section: 'ebeam',
    purpose: '선택 recipe의 측정 이력을 확인합니다.',
    description: 'MSR 존재 여부, align fail, measurement fail 같은 이력 정보를 recipe 기준으로 조회합니다.',
    users: '계측 결과 확인자',
    notes: ['필요 시 MSR file 상세 조회로 이어집니다.']
  },
  {
    id: 'recipe-status',
    title: 'Recipe 현황',
    path: '/ebeam/{tool}/{fab}/recipe-status',
    icon: 'i-lucide-timer',
    section: 'ebeam',
    purpose: 'Recipe TAT와 Align/Meas fail 이슈를 한 화면에서 확인합니다.',
    description: 'Recipe TAT · Align Fail · Meas Fail 세 개의 내부 탭으로 recipe 수행 시간, 병목, fail 이슈를 기간/lot/Fab 기준으로 분석합니다.',
    users: '공정/계측 효율 분석자, 장비/계측 품질 담당자',
    notes: [
      '기존 Recipe TAT · Fail 이슈 페이지가 이 화면으로 통합되었습니다 (이전 URL은 자동 redirect).',
      'CD-SEM과 HV-SEM이 같은 화면 구성을 사용합니다.'
    ]
  },
  {
    id: 'device-statistics',
    title: 'CD-SEM Device Statistics',
    path: '/ebeam/cd-sem/device-statistics',
    icon: 'i-lucide-table-properties',
    section: 'ebeam',
    purpose: 'CD-SEM device와 lot 기준 recipe 통계를 비교합니다.',
    description: 'R3 device group, M-fab device description, lot별 recipe statistics와 trend를 조합해 분석합니다.',
    users: 'CD-SEM device 분석자',
    notes: ['선택한 lot은 comparison 화면으로 이어집니다.']
  },
  {
    id: 'skewvoir',
    title: 'Skewvoir',
    path: '/ebeam/{tool}/skewvoir',
    icon: 'i-lucide-scan-search',
    section: 'ebeam',
    purpose: 'MSR 기반 CD 분포와 wafer 위치 분석을 수행합니다.',
    description: 'MSR 목록을 선택하고 시간 흐름, CD 분포, wafer map, sequence trend를 함께 봅니다.',
    users: '계측 데이터 분석자',
    notes: ['현재 CD-SEM과 HV-SEM 진입 route가 모두 있습니다.']
  },
  {
    id: 'afm-tools',
    title: 'AFM Tool 선택',
    path: '/afm',
    icon: 'i-lucide-ruler',
    section: 'afm',
    purpose: 'AFM 장비군의 진입점으로, Fab별 tool을 선택합니다.',
    description: 'Fab 그룹별로 AFM tool 목록을 보여 주고, 선택한 tool의 measurement 검색 화면으로 이동합니다.',
    users: 'AFM 담당 엔지니어, 신규 사용자',
    notes: ['Fab 단위로 tool을 묶어 보여 줍니다.']
  },
  {
    id: 'afm-search',
    title: 'AFM Measurement 검색',
    path: '/afm/{tool}',
    icon: 'i-lucide-search',
    section: 'afm',
    purpose: '선택한 AFM tool의 measurement file을 검색합니다.',
    description: 'tool별 file 목록을 검색하고, 비교 그룹에 담거나 상세 화면으로 이동합니다.',
    users: 'AFM 담당 엔지니어',
    notes: ['행의 명시적인 action으로 상세(filename) 화면에 진입합니다.']
  },
  {
    id: 'afm-detail',
    title: 'AFM Measurement 상세',
    path: '/afm/{tool}/{filename}',
    icon: 'i-lucide-file-chart-column',
    section: 'afm',
    purpose: '선택한 AFM measurement file의 상세 분석 결과를 확인합니다.',
    description: 'recipe/lot 정보, measurement point 목록, summary scatter, profile data와 profile image를 함께 조회합니다.',
    users: 'AFM 결과 분석자',
    notes: ['filename route로 진입하며, 검색 화면에서 선택한 file context를 사용합니다.']
  },
  {
    id: 'afm-see-together',
    title: 'AFM See Together',
    path: '/afm/{tool}/see-together',
    icon: 'i-lucide-chart-line',
    section: 'afm',
    purpose: '여러 AFM measurement를 함께 비교합니다.',
    description: '저장한 그룹이나 선택 항목을 기반으로 time-series 형태의 비교 관점을 제공합니다.',
    users: 'AFM 비교 분석자',
    notes: ['AFM 검색 결과의 명시적인 action에서 이동합니다.']
  },
  {
    id: 'coming-soon',
    title: '준비 중 페이지',
    path: '/thickness, /ebeam/verity-sem, /ebeam/provision',
    icon: 'i-lucide-construction',
    section: 'common',
    purpose: '아직 기능이 확정되지 않은 영역을 표시합니다.',
    description: '사용자가 해당 기능이 준비 중임을 알 수 있게 하되, 완성되지 않은 기능으로 유도하지 않습니다.',
    users: '전체 사용자',
    notes: ['준비되지 않은 기능은 활성 탭처럼 보이지 않도록 관리합니다.']
  }
]

const activePageId = ref('overview')
const selectedPageGuide = computed<PageGuide>(() =>
  pageGuides.find(page => page.id === activePageId.value) ?? pageGuides[0]!
)

const guideSections = computed(() =>
  sectionMeta
    .map(section => ({
      ...section,
      pages: pageGuides.filter(page => page.section === section.key)
    }))
    .filter(section => section.pages.length > 0)
)

const canOpenPage = (path: string) => !path.includes(',') && !path.includes('{')
</script>
