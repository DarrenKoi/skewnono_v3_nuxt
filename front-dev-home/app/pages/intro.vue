<template>
  <div class="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8 lg:px-8">
    <div class="grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="lg:sticky lg:top-0 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
        <nav
          class="space-y-6 border-b border-(--sk-border) pb-5 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-6"
          aria-label="페이지 안내"
        >
          <div class="space-y-1">
            <p class="mb-2 sk-label">
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
            <button
              type="button"
              class="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition"
              :class="activePageId === 'history' ? 'bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-950' : 'text-zinc-600 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-900'"
              @click="activePageId = 'history'"
            >
              <UIcon
                name="i-lucide-history"
                class="h-4 w-4 shrink-0"
              />
              <span>History</span>
            </button>
          </div>

          <div
            v-for="section in guideSections"
            :key="section.key"
          >
            <p class="mb-2 flex items-center gap-1.5 sk-label">
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
                <span
                  v-if="page.hiddenOnCloud"
                  class="ml-auto intro-beta"
                >개발 중</span>
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
                측정값 하나만으로는 문제의 원인을 판단하기 어렵습니다. SKEWNONO는 관련 데이터를
                한곳에 모아 데이터의 맥락과 신뢰도를 함께 확인하는 Metrology Workspace입니다.
              </p>
            </div>
          </header>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <h2 class="sk-heading">
              함께 확인하는 데이터
            </h2>
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
            <h2 class="sk-heading">
              문제를 확인하는 흐름
            </h2>
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
            <h2 class="mb-4 sk-heading">
              주요 사용자
            </h2>
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

          <section>
            <h2 class="mb-4 sk-heading">
              E-Beam Metrology
            </h2>
            <div class="grid gap-4 md:grid-cols-3">
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
                  <h3 class="text-base font-semibold">
                    {{ area.title }}
                  </h3>
                </div>
                <p class="mt-3 sk-body leading-6">
                  {{ area.description }}
                </p>
              </div>
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
                화면의 데이터는 최종 판정이 아니라, 엔지니어가 직접 비교하고 판단하기 위한
                근거입니다.
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
                이상 징후 감지, 원인 후보 제시, 보고서 생성까지 함께하는 AI Agent로 발전하는 것을
                목표로 합니다.
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
                  왼쪽 목록에서 페이지별 안내를 확인하세요. 기능 탭에 없는 조회·계산 도구는
                  헤더의 실험실 메뉴에 모여 있으며, 장비군을 고른 뒤에 나타납니다. 데이터를
                  직접 가져가려는 개발자는 API 리스트를 참고하십시오.
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

        <IntroHistoryView v-else-if="activePageId === 'history'" />

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
                  <span
                    v-if="selectedPageGuide.hiddenOnCloud"
                    class="intro-beta"
                  >개발 중</span>
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
              <div class="sk-label">
                Route
              </div>
              <code class="mt-2 block break-words sk-value-num">
                {{ selectedPageGuide.path }}
              </code>
            </div>
            <div class="rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950">
              <div class="sk-label">
                주요 사용자
              </div>
              <p class="mt-2 sk-body leading-6">
                {{ selectedPageGuide.users }}
              </p>
            </div>
          </section>

          <section
            v-if="selectedPageGuide.hiddenOnCloud"
            class="intro-callout rounded-lg border p-5"
          >
            <div class="flex items-center gap-2">
              <UIcon
                name="i-lucide-flask-conical"
                class="h-5 w-5 shrink-0"
              />
              <h2 class="sk-heading">
                아직 개발 중인 화면입니다
              </h2>
            </div>
            <p class="mt-3 sk-body leading-7">
              계산 방식이 검증 단계라, 이 화면의 숫자는 판정 근거가 아니라 검토용 참고값입니다.
              같은 이유로 운영 환경에서는 실험실 메뉴와 이 안내 모두에 노출하지 않고, 만드는
              동안 URL을 아는 사람만 열어 봅니다.
            </p>
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

type GuideSection = 'common' | 'ebeam' | 'lab' | 'afm' | 'admin'

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
  // 실험실의 미검증 페이지는 헤더 메뉴와 같은 규칙으로 클라우드에서 안내에서도 빠집니다.
  // 헤더에서는 감춰 두고 소개 페이지에서만 소개하면, 열 수 없는 화면을 광고하는 셈이 됩니다.
  // 규칙의 원본은 utils/headerNav.ts 의 `hiddenOnCloud` 입니다.
  hiddenOnCloud?: boolean
}

const overviewAreas = [
  {
    title: '장비 현황',
    icon: 'i-lucide-microscope',
    description: 'Fab별 CD-SEM, HV-SEM 장비 목록과 storage, hardware 보조 서비스 상태를 확인합니다.'
  },
  {
    title: 'Recipe 분석',
    icon: 'i-lucide-search-code',
    description: 'Recipe 검색에서 open recipe 구조, lateral 보유 현황, 측정 이력까지 이어서 확인합니다.'
  },
  {
    title: '계측 데이터 분석',
    icon: 'i-lucide-chart-no-axes-combined',
    description: 'Recipe TAT와 fail 이슈, device 통계, MSR 기반 CD 분포와 wafer map을 함께 살펴봅니다.'
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
    description: '장비 목록, Storage, Hardware 화면에서 장비 상태와 유지보수 맥락을 확인합니다.'
  },
  {
    title: '공정·소자 Engineer',
    icon: 'i-lucide-chart-no-axes-combined',
    description: 'Recipe와 측정 데이터를 연결해 관찰된 차이가 Wafer나 공정 영향인지 살펴봅니다.'
  }
]

const sectionMeta: { key: GuideSection, label: string, icon: string }[] = [
  { key: 'common', label: '공통', icon: 'i-lucide-layout-grid' },
  { key: 'ebeam', label: 'E-Beam Metrology', icon: 'i-lucide-microscope' },
  { key: 'lab', label: '실험실', icon: 'i-lucide-flask-conical' },
  { key: 'afm', label: 'AFM Metrology', icon: 'i-lucide-ruler' },
  { key: 'admin', label: '관리자', icon: 'i-lucide-shield-check' }
]

// 안내에 싣는 section. 관리자 전용 화면은 일반 사용자에게 노출하지 않고,
// AFM Metrology는 다음 버전에 공개하므로 지금은 감춰 둡니다 (guide 정의는 그대로 둡니다).
const visibleSections: GuideSection[] = ['common', 'ebeam', 'lab']

const pageGuides: PageGuide[] = [
  {
    id: 'home',
    title: '홈',
    path: '/',
    icon: 'i-lucide-house',
    section: 'common',
    purpose: 'SKEWNONO의 첫 진입 화면입니다.',
    description: 'FAB을 고르면 그 선택이 다른 화면까지 따라갑니다. CD-SEM·HV-SEM 같은 작업 영역이 장비 대수와 함께 나열됩니다. 오른쪽 시스템 상태 카드에서 검색·저장소·캐시가 살아 있는지 한눈에 확인하고 펼치면 각 서비스의 응답 시간까지 봅니다. 장비군별 online/total 요약과 미연결 장비 목록으로 가는 입구도 여기 있습니다.',
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
    description: '색상 모드와 ECharts 테마를 고르고 /api/* 호출에 쓰는 API Token을 만들고 폐기합니다. 토큰 표에는 라벨과 생성일, 마지막 사용 시각이 남아 어떤 토큰이 실제로 쓰이는지 알 수 있습니다. 발급 직후 모달에 뜨는 평문 토큰은 그때 한 번만 보입니다.',
    users: '개인 개발 환경에서 API를 호출하려는 사용자',
    notes: ['Token plaintext는 발급 직후 한 번만 보여주므로 바로 저장해야 합니다.']
  },
  {
    id: 'activity',
    title: '사용 통계',
    path: '/activity',
    icon: 'i-lucide-bar-chart-3',
    section: 'common',
    purpose: 'SKEWNONO가 어떻게 쓰이고 있는지 확인하는 화면입니다.',
    description: '맨 위는 내 사용 패턴입니다. 이번 달 요청 수와 활동일, 자주 쓰는 기능 Top 5, 30일 스파크라인이 놓입니다. 그 아래로 DAU·WAU·MAU 같은 전체 지표와 인기 기능 Top 10, FAB별 페이지 사용량이 7일·30일 기준으로 이어집니다. 관리자는 사용자별 사용 현황 표를 검색·정렬하고 CSV로 내려받을 수 있습니다.',
    users: '전체 사용자',
    notes: ['개인 활동과 전체 집계를 나란히 두어 내 사용 패턴을 전체 흐름과 비교할 수 있습니다.']
  },
  {
    id: 'admin-logs',
    title: '운영 로그',
    path: '/admin/logs',
    icon: 'i-lucide-file-search',
    section: 'admin',
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
    section: 'admin',
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
    description: '화면이 따로 없는 갈아타는 지점입니다. 마지막으로 보던 FAB, 처음이라면 R3의 장비 목록으로 곧장 옮겨 가므로 사용자는 CD-SEM인지 HV-SEM인지만 고르면 됩니다.',
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
    description: '장비 ID, Model, Vendor, IP, Version을 한 표에서 보고 Available과 Offline 상태를 우선 정렬로 확인합니다. 상단의 Available·Offline 칩은 눌러서 그대로 필터가 되고 검색과 Model 셀렉트로 범위를 좁힙니다. 각 행에서 H/W 상태 화면으로 바로 넘어가거나 IP를 복사할 수 있습니다. 화면에 없는 Fac까지 담은 CSV도 내려받습니다.',
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
    description: '장비별로 Total·Used·Available·Usage와 Recipe 수, 마지막 보고 시각이 늘어서고 사용률은 색 막대로 나타납니다. 위험 98% 이상, 주의 90~97% 같은 구간 필터와 20종 정렬 프리셋이 있습니다. Recipe 수가 장비 상한 50,000에 가까워지면 따로 경고합니다. 아래쪽 PPID 미접속 장비 패널에서 며칠째 응답이 없는 장비도 함께 확인합니다.',
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
    description: '왼쪽 레일에서 장비를 고르고 오른쪽에서 FDC·Sharpness 두 데일리 서비스와 BM/PM·BSM·Reso Center·MDC·SCE 다섯 분기 서비스를 탭으로 오갑니다. 서비스마다 전용 패널이 있어 추세와 비교 차트를 보고 BM/PM 표시를 켜면 정비 이벤트가 차트 위 마커로 겹쳐 보입니다. 비교 장비를 붙이면 같은 축에서 두 장비를 나란히 놓을 수 있습니다.',
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
    description: '세 글자 이상 입력하면 공백과 밑줄로 나눈 조각을 모두 포함하는 recipe를 찾습니다. Redis 카탈로그를 먼저 뒤지고 없으면 OpenSearch로 다시 찾는데, 이때는 배너와 행 태그로 출처가 드러나고 Redis로 다시 시도할 수도 있습니다. 결과를 체크해 작업 세트에 담으면 열어 보기·횡전개·측정 이력·비교하기로 한꺼번에 넘어갑니다.',
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
    description: '왼쪽 파라미터 목록에서 하나를 고르면 오른쪽이 그 파라미터의 상세로 바뀝니다. 이미지와 설정 탭에서 Addressing·Measurement SEM 이미지와 AF/PR 조건을 보고, 나머지 탭에서 AMP 설정과 Sequence 구성, 해당 파라미터의 측정 위치를 확인합니다. Align 정보는 별도 모달에 좌표 표와 정렬 이미지로 있습니다. 필요하면 이미지까지 포함해 Excel로 내려받습니다.',
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
    description: '고른 recipe가 FAB 안 장비에 있는지를 보유와 미보유 탭으로 나눠 보이고 보유 비율을 함께 표시합니다. 보유 탭은 recipe_version별로 표를 갈라 최신 버전부터 세우므로 버전이 섞여 있으면 어느 장비가 옛 버전에 남아 있는지 바로 보입니다.',
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
    description: '최근 30일 측정 row를 최신순으로 놓고 msr_check·align_fail·fail_ratio로 상태를 판단합니다. MSR 없음과 Align Fail, 평균 fail 비율은 상단에 따로 세어 둡니다. 표에서는 fail 비율이 15%를 넘으면 붉게 표시합니다. align 정렬은 알파벳순이 아니라 Fail·NA·Pass 순으로 나쁜 것부터 올라옵니다.',
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
    description: 'Recipe TAT 탭에서는 총 TAT와 실행 수, Top N 막대와 일별 추세로 어떤 recipe가 시간을 먹는지 봅니다. Align Fail과 Meas Fail 탭은 같은 기간을 기준으로 fail 건수와 비율을 Bar·Line·Ratio로 바꿔 가며 나타냅니다. 세 탭 모두 전체 요약, 디바이스별, 장비별로 시야를 바꿀 수 있고 랭킹 표의 각 행에서 열어 보기·횡전개·측정 이력으로 바로 이어집니다.',
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
    description: 'Fab을 고르고 측정 상위와 카테고리, Lot/Tech 칩으로 범위를 좁힌 다음 디바이스 표에서 볼 lot을 체크해 담습니다. 담은 조합은 프리셋으로 저장해 두었다가 다시 꺼낼 수 있습니다. 비교 화면에서는 파라미터 분포와 운용 레시피 수를 차트로 견주고, Lot 요약 표의 행을 열면 recipe 상세와 추세, 중앙값을 넘은 파라미터까지 모달로 확인합니다.',
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
    description: '장비·Recipe·Lot·날짜·MSR을 한 검색창에 섞어 넣으면 토큰으로 갈라 찾습니다. 결과에서 측정을 골라 워크벤치에 쌓고, 분석 화면의 여섯 관점인 측정 개요, 위치 비교, FDC, Time-Series, 상관·분포, 이미지 갤러리를 단축키로 오갑니다. 선택과 축, baseline까지 URL에 실리므로 링크를 건네면 상대도 같은 화면을 봅니다.',
    users: '계측 데이터 분석자',
    notes: ['현재 CD-SEM과 HV-SEM 진입 route가 모두 있습니다.']
  },
  {
    id: 'mag-pixel',
    title: 'Mag/Pixel 가이드',
    path: '/mag-pixel',
    icon: 'i-lucide-scan-search',
    section: 'lab',
    purpose: '측정하려는 패턴이 화면에 들어오는 한도에서 가장 높은 배율을 계산합니다.',
    description: 'CD와 Pitch, 패턴 수, 여유 마진을 넣으면 필요한 FOV를 계산하는데, 이어서 그 안에 들어오는 최대 배율과 그때의 픽셀 크기, CD당 픽셀 수까지 나옵니다. 추천 조합 카드가 기준 통과 여부와 스캔 시간까지 알려 주고, 마진 민감도 표는 마진을 조금 바꿨을 때 배율이 어떻게 계단식으로 움직이는지 나타냅니다. 오른쪽 미리보기 그림과 참조표로 패턴이 FOV에 들어오는 모습과 배율별 픽셀 값을 확인합니다.',
    users: 'Recipe 조건을 잡는 계측 엔지니어',
    notes: ['장비 데이터를 조회하지 않고 입력값만으로 계산하는 화면입니다.']
  },
  {
    id: 'live-alarm',
    title: '라이브 알람',
    path: '/ebeam/{tool}/{fab}/live-alarm',
    icon: 'i-lucide-radio',
    section: 'lab',
    purpose: 'Fab의 E-Beam 장비에서 지금 올라오는 알람을 한 보드에서 확인합니다.',
    description: '최근 20분 사이의 Align 실패와 측정 실패를 15초마다 새로 받아 장비별로 늘어놓습니다. 알람마다 lot과 FOUP, step, alid와 경과 시간이 붙고 recipe_id를 누르면 그 recipe 검색으로 넘어갑니다. 측정 실패만 볼 때는 장비와 ppid가 같은 건을 묶어 접어 둡니다. 아직 읽지 않은 알람 수는 브라우저 탭 제목에도 표시합니다.',
    users: '장비 담당자, 당직 대응자',
    notes: [
      '헤더 실험실 메뉴에서 최근에 보던 장비군과 Fab 기준으로 열립니다.',
      'CD-SEM과 HV-SEM 모두에서 사용할 수 있습니다.'
    ]
  },
  {
    id: 'tttm',
    title: '장비간 스큐(TTTM)',
    path: '/ebeam/cd-sem/{fab}/tttm',
    icon: 'i-lucide-git-compare',
    section: 'lab',
    purpose: '같은 조건에서 장비끼리 측정값이 얼마나 맞는지 비교합니다.',
    description: 'recipe와 parameter, 볼 장비를 고르면 장비 쌍마다 측정값 차이를 행렬로 계산해 허용 범위를 넘은 조합을 짚습니다. 배치도에서 어느 장비가 그룹 밖으로 벗어났는지 보고, 셀별 심각도와 추세, BM/PM·MDC 이력을 함께 놓아 언제부터 벌어졌는지 따라갑니다. 허용 범위는 슬라이더로 바꿔 가며 결과가 어떻게 달라지는지 볼 수 있습니다.',
    users: '장비 정합성 검토자',
    notes: ['CD-SEM 전용이며 Fab 하나를 기준으로 봅니다.'],
    hiddenOnCloud: true
  },
  {
    id: 'pm-planning',
    title: 'PM 플래닝(PM-Planning)',
    path: '/ebeam/cd-sem/{fab}/pm-planning',
    icon: 'i-lucide-wrench',
    section: 'lab',
    purpose: 'PM 창에서 장비를 어느 목표로 맞춰야 그룹에 들어오는지 제시합니다.',
    description: 'TTTM이 계산한 장비간 스큐를 그대로 받습니다. 튜닝할 장비를 고르면 그 장비가 그룹에 들어가려면 셀마다 몇 nm를 움직여야 하는지 제시합니다. 게이트 카드에서 Up 가능인지 Hold인지와 최근 PM 완료일, PM 전후 변화를 확인하고 다음 PM 후보 랭킹으로 기준선을 넘은 장비들을 훑습니다. recipe와 parameter, 장비 선택은 TTTM과 같은 설정을 쓰므로 한쪽에서 바꾸면 다른 쪽에도 반영됩니다.',
    users: 'PM 계획 담당자, 장비 담당자',
    notes: [
      'TTTM과 같은 payload를 사용하므로 두 화면은 함께 열리고 함께 닫힙니다.',
      'TTTM과 마찬가지로 CD-SEM 전용입니다.'
    ],
    hiddenOnCloud: true
  },
  {
    id: 'chat',
    title: '채팅',
    path: '/chat',
    icon: 'i-lucide-message-square',
    section: 'lab',
    purpose: '데이터에 대해 자연어로 물어봅니다.',
    description: '왼쪽에 대화 목록, 가운데에 주고받은 메시지가 놓이고 모델과 시스템 프롬프트는 첫 메시지를 보내기 전까지만 바꿀 수 있습니다. 답변에는 응답 시간과 토큰 수, 참고한 출처가 함께 붙고 좋아요와 싫어요로 평가를 남길 수 있습니다. 백엔드가 준비되지 않은 환경에서는 화면 대신 준비 중 안내가 뜹니다.',
    users: '전체 사용자',
    notes: ['실험실의 다른 화면이 조회·계산이라면 이 화면은 대화이므로, 메뉴에서도 구분선 아래에 둡니다.']
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
    path: '/thickness, /ebeam/veritysem, /ebeam/provision',
    icon: 'i-lucide-construction',
    section: 'common',
    purpose: '아직 기능이 확정되지 않은 영역을 표시합니다.',
    description: '사용자가 해당 기능이 준비 중임을 알 수 있게 하되, 완성되지 않은 기능으로 유도하지 않습니다.',
    users: '전체 사용자',
    notes: ['준비되지 않은 기능은 활성 탭처럼 보이지 않도록 관리합니다.']
  }
]

// 클라우드 여부는 요청으로 도착하므로 목록도 computed 입니다. 답이 오기 전에는 false —
// 미검증 화면이 잠깐 더 보이는 쪽이, 만드는 사람에게 안내가 사라지는 쪽보다 낫습니다
// (같은 판단이 useDeployment 에 적혀 있습니다).
const { isCloud } = useDeployment()

const visiblePageGuides = computed(() =>
  pageGuides.filter(page =>
    visibleSections.includes(page.section) && !(isCloud.value && page.hiddenOnCloud)
  )
)

const activePageId = ref('overview')
const selectedPageGuide = computed<PageGuide>(() =>
  visiblePageGuides.value.find(page => page.id === activePageId.value) ?? visiblePageGuides.value[0]!
)

const guideSections = computed(() =>
  sectionMeta
    .filter(section => visibleSections.includes(section.key))
    .map(section => ({
      ...section,
      pages: visiblePageGuides.value.filter(page => page.section === section.key)
    }))
    .filter(section => section.pages.length > 0)
)

const canOpenPage = (path: string) => !path.includes(',') && !path.includes('{')
</script>

<style scoped>
/* 헤더 실험실 메뉴의 BETA 칩과 같은 토큰 - 같은 사실을 알리는 표시가 두 곳에서
   다르게 보이면 다른 뜻으로 읽힙니다. 라벨이지 버튼이 아니므로 chip radius이고,
   rounded-full 은 쓰지 않습니다 (DESIGN.md §Tags / Badges). */
.intro-beta {
  display: inline-flex;
  align-items: center;
  flex-shrink: 0;
  padding: 1px 6px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--sk-r-chip);
  background: var(--sk-warn-soft);
  border: 1px solid var(--sk-warn-border);
  color: var(--sk-ink);
}

.intro-callout {
  background: var(--sk-warn-soft);
  border-color: var(--sk-warn-border);
  color: var(--sk-ink);
}
</style>
