<template>
  <div class="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8 lg:px-8">
    <div class="grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
        <nav
          class="space-y-6 border-b border-(--sk-border) pb-5 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-6"
          aria-label="페이지 안내"
        >
          <div>
            <p class="mb-2 text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
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
            <p class="mb-2 flex items-center gap-1.5 text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
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
            <div class="flex items-center gap-2 text-sm font-semibold text-zinc-500 dark:text-zinc-400">
              <UIcon
                name="i-lucide-sparkles"
                class="h-4 w-4"
              />
              <span>소개</span>
            </div>
            <div class="mt-3 max-w-3xl">
              <h1 class="text-2xl font-semibold text-zinc-950 dark:text-white md:text-4xl">
                SKEWNONO
              </h1>
              <p class="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300 md:text-base">
                SKEWNONO는 계측(metrology) 장비 관리와 데이터 분석을 위한 웹 애플리케이션입니다.
                CD-SEM, HV-SEM 같은 E-Beam 장비군과 AFM 장비군의 상태 확인, recipe 관리,
                측정 데이터 분석을 한 곳에서 제공합니다.
              </p>
            </div>
          </header>

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
              <p class="mt-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                {{ area.description }}
              </p>
            </div>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <div class="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div class="max-w-2xl">
                <h2 class="text-lg font-semibold">
                  페이지 안내 보는 법
                </h2>
                <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                  왼쪽 목록에서 페이지를 선택하면 각 페이지의 목적, 주요 사용자, 화면 구성을 확인할 수 있습니다.
                  화면 없이 데이터를 직접 가져가려는 개발자는 API 리스트 페이지를 참고하십시오.
                </p>
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
            <div class="flex items-center gap-2 text-sm font-semibold text-zinc-500 dark:text-zinc-400">
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
                  <h1 class="text-2xl font-semibold text-zinc-950 dark:text-white md:text-4xl">
                    {{ selectedPageGuide.title }}
                  </h1>
                </div>
                <p class="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300 md:text-base">
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
              <div class="text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
                Route
              </div>
              <code class="mt-2 block break-words font-mono text-sm text-zinc-950 dark:text-white">
                {{ selectedPageGuide.path }}
              </code>
            </div>
            <div class="rounded-lg border border-(--sk-border) bg-white p-4 dark:bg-zinc-950">
              <div class="text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
                주요 사용자
              </div>
              <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                {{ selectedPageGuide.users }}
              </p>
            </div>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <h2 class="text-lg font-semibold">
              화면 설명
            </h2>
            <p class="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300">
              {{ selectedPageGuide.description }}
            </p>
          </section>

          <section class="rounded-lg border border-(--sk-border) bg-white p-5 dark:bg-zinc-950">
            <h2 class="text-lg font-semibold">
              참고 사항
            </h2>
            <ul class="mt-4 space-y-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
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
definePageMeta({
  layout: 'hub'
})

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
    id: 'recipe-tat',
    title: 'Recipe TAT',
    path: '/ebeam/{tool}/{fab}/recipe-tat',
    icon: 'i-lucide-timer',
    section: 'ebeam',
    purpose: 'Recipe 수행 시간과 병목을 확인합니다.',
    description: 'ranking, summary, daily trend, device 목록을 통해 기간/lot/Fab 기준 TAT를 분석합니다.',
    users: '공정/계측 효율 분석자',
    notes: ['기본 기간은 mock data anchor date 기준으로 계산됩니다.']
  },
  {
    id: 'fail-issue',
    title: 'Fail Issue',
    path: '/ebeam/{tool}/{fab}/fail-issue',
    icon: 'i-lucide-triangle-alert',
    section: 'ebeam',
    purpose: 'Align fail과 measurement fail 이슈를 추적합니다.',
    description: 'summary, daily trend, align ranking, meas ranking을 통해 lot 또는 장비 단위의 fail 이슈를 좁혀 봅니다.',
    users: '장비/계측 품질 담당자',
    notes: ['CD-SEM과 HV-SEM이 같은 화면 구성을 사용합니다.']
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
