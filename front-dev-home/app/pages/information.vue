<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

useHead({
  title: '프로젝트 정보 | SKEWNONO'
})

type TechStack = {
  group: string
  icon: string
  status: string
  description: string
  items: string[]
}

type ApiEndpoint = {
  method: 'GET'
  path: string
  purpose: string
  response: string
  example: string
}

const projectGoals = [
  'SKEWNONO v3는 E-Beam 계측 장비의 현황, Fab, 장비 타입, Online/Offline 상태를 한 화면에서 확인하기 위한 내부 대시보드입니다.',
  '프론트엔드는 동일한 API 계약을 사용하고, 백엔드는 Mock 데이터에서 회사 내부 데이터 소스로 자연스럽게 교체할 수 있도록 구성합니다.',
  '장비 리스트, 스토리지, Recipe 검색, 디바이스 통계처럼 엔지니어가 반복해서 확인하는 정보를 빠르게 탐색할 수 있게 만드는 것이 목적입니다.'
]

const techStacks: TechStack[] = [
  {
    group: 'Nuxt',
    icon: 'i-simple-icons-nuxt',
    status: '현재 사용',
    description: '프론트엔드 애플리케이션의 기본 프레임워크입니다.',
    items: [
      'Nuxt 4 기반 SPA로 구성되어 있으며 ssr: false 설정을 사용합니다.',
      'app/pages 디렉터리의 파일 기반 라우팅으로 화면 URL을 관리합니다.',
      'Nitro dev proxy가 /api 요청을 Flask 백엔드로 전달합니다.',
      'runtimeConfig를 통해 NUXT_PUBLIC_API_BASE 같은 공개 설정을 주입합니다.'
    ]
  },
  {
    group: 'Nuxt UI',
    icon: 'i-lucide-panels-top-left',
    status: '현재 사용',
    description: '버튼, 카드, 배지, 테이블 같은 공통 UI의 기준 컴포넌트입니다.',
    items: [
      '@nuxt/ui를 사용해 UButton, UCard, UBadge, UTable, UColorModeButton을 렌더링합니다.',
      'Tailwind CSS v4 유틸리티 클래스로 화면 간 간격, 색상, 반응형 레이아웃을 맞춥니다.',
      '@iconify-json/lucide와 @iconify-json/simple-icons를 통해 아이콘을 사용합니다.',
      'Public Sans와 Noto Sans KR 폰트를 self-hosted 방식으로 제공해 사내망/오프라인 환경에서도 글꼴이 유지됩니다.'
    ]
  },
  {
    group: 'Vite',
    icon: 'i-simple-icons-vite',
    status: '현재 사용',
    description: 'Nuxt 개발 서버와 프로덕션 번들의 빌드 엔진입니다.',
    items: [
      '개발 중에는 빠른 HMR과 모듈 변환을 담당합니다.',
      'nuxt build 실행 시 클라이언트 번들을 생성합니다.',
      'nuxt.config.ts의 vite.server.allowedHosts 설정으로 원격 터널 접속을 허용합니다.',
      'ESLint, vue-tsc와 함께 프론트엔드 품질 검증 흐름을 구성합니다.'
    ]
  },
  {
    group: 'Flask API',
    icon: 'i-lucide-server',
    status: '현재 사용',
    description: '프론트엔드가 호출하는 /api 엔드포인트를 제공하는 Python 백엔드입니다.',
    items: [
      'back_dev_home의 create_app() 팩터리에서 Flask 앱을 생성합니다.',
      '각 기능은 Blueprint로 분리하고 /api 아래에 등록합니다.',
      'routes.py는 응답 형태를 유지하고, data.py는 데이터 소스를 교체하는 경계로 사용합니다.',
      'wsgi.ini를 통해 uWSGI 실행 구성을 제공합니다.'
    ]
  },
  {
    group: 'OpenSearch',
    icon: 'i-lucide-search-code',
    status: '연동 대상',
    description: '회사 내부 장비/계측 검색 데이터를 가져올 때 사용할 검색 저장소입니다.',
    items: [
      '현재 홈/오프라인 개발에서는 Mock 데이터를 사용합니다.',
      '회사 환경에서는 data.py 내부 구현을 OpenSearch 조회로 교체하는 구조를 목표로 합니다.',
      '프론트엔드가 받는 JSON 응답 형태는 유지해야 합니다.',
      '장비 리스트, Recipe 검색, 계측 결과 검색처럼 조건 검색이 필요한 화면과 잘 맞습니다.'
    ]
  },
  {
    group: 'Redis',
    icon: 'i-lucide-database-zap',
    status: '연동 대상',
    description: '빠르게 바뀌는 상태, 캐시, 임시 집계 데이터를 다루기 위한 저장소입니다.',
    items: [
      '현재 requirements.txt에는 Redis 클라이언트가 직접 등록되어 있지 않습니다.',
      '회사 환경 연동 시 장비 상태, 최근 조회 결과, 캐시성 요약 데이터를 Redis로 분리할 수 있습니다.',
      'API 응답 형태를 바꾸지 않고 백엔드 data.py 계층에서만 연동 방식을 바꾸는 것이 원칙입니다.',
      '실시간성 또는 반복 조회가 많은 데이터에 우선 적용하기 좋습니다.'
    ]
  },
  {
    group: 'ECharts',
    icon: 'i-lucide-chart-no-axes-combined',
    status: '주요 시각화 패키지',
    description: '디바이스 통계, 추세, 분포 차트를 표현할 때 사용할 수 있는 차트 라이브러리입니다.',
    items: [
      '현재 package.json에는 echarts가 직접 의존성으로 등록되어 있지 않습니다.',
      '디바이스 통계, 장비 가동률 추이, Fab별 분포처럼 차트가 필요한 화면에서 도입할 수 있습니다.',
      'Vue 화면에서는 차트 옵션을 computed로 만들고 데이터 로딩 상태와 함께 관리하는 방식이 적합합니다.',
      '도입 시에는 echarts와 Vue 래퍼 사용 여부를 정한 뒤 package.json에 명시해야 합니다.'
    ]
  }
]

const runtimeConfigRows = [
  {
    name: 'NUXT_API_TARGET',
    defaultValue: 'http://localhost:5000',
    detail: 'Nuxt 개발 서버가 /api 요청을 전달할 Flask 백엔드 주소입니다.'
  },
  {
    name: 'NUXT_PUBLIC_API_BASE',
    defaultValue: '/api',
    detail: '프론트엔드 composable이 사용하는 공개 API 기본 경로입니다.'
  },
  {
    name: 'NUXT_PORT',
    defaultValue: '3100',
    detail: 'Nuxt 개발 서버 포트입니다.'
  }
]

const apiEndpoints: ApiEndpoint[] = [
  {
    method: 'GET',
    path: '/api/health',
    purpose: 'Flask 백엔드가 정상적으로 응답하는지 확인합니다.',
    response: '{ "status": "ok" }',
    example: 'curl http://localhost:5000/api/health'
  },
  {
    method: 'GET',
    path: '/api/sem-list',
    purpose: '대시보드, 장비 타입별 목록, Fab별 요약에서 사용하는 E-Beam 장비 목록을 반환합니다.',
    response: 'SemListRow[]',
    example: 'curl http://localhost:5000/api/sem-list'
  }
]

const semListFields = [
  'fac_id',
  'eqp_id',
  'eqp_model_cd',
  'eqp_grp_id',
  'vendor_nm',
  'eqp_ip',
  'fab_name',
  'updt_dt',
  'available',
  'version'
]
</script>

<template>
  <div class="max-w-7xl mx-auto px-4 md:px-6 lg:px-8 py-6 md:py-8 space-y-6">
    <section class="dashboard-surface rounded-3xl p-6 md:p-8">
      <div class="flex flex-col lg:flex-row lg:items-end lg:justify-between gap-5">
        <div class="max-w-3xl space-y-3">
          <p class="text-xs uppercase tracking-[0.18em] text-zinc-500 dark:text-zinc-400 font-semibold">
            SKEWNONO v3
          </p>
          <h1 class="text-2xl md:text-4xl font-semibold tracking-tight">
            프로젝트 정보
          </h1>
          <p class="text-sm md:text-base leading-7 text-zinc-600 dark:text-zinc-300">
            이 페이지는 SKEWNONO v3의 목적, 주요 기술 스택, 공개 API 목록을 사내 엔지니어가 빠르게 이해하고
            재사용할 수 있도록 정리한 안내 화면입니다.
          </p>
        </div>
        <div class="flex flex-wrap gap-2">
          <UBadge
            label="Nuxt 4"
            color="neutral"
            variant="subtle"
            class="rounded-full"
          />
          <UBadge
            label="Flask API"
            color="neutral"
            variant="subtle"
            class="rounded-full"
          />
          <UBadge
            label="OpenSearch / Redis"
            color="neutral"
            variant="subtle"
            class="rounded-full"
          />
        </div>
      </div>
    </section>

    <UCard
      class="dashboard-surface rounded-3xl"
      :ui="{ body: 'p-6' }"
    >
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-target"
            class="w-5 h-5 text-zinc-600 dark:text-zinc-300"
          />
          <h2 class="text-lg font-semibold">
            프로젝트 목적
          </h2>
        </div>
      </template>

      <ul class="grid lg:grid-cols-3 gap-4 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
        <li
          v-for="goal in projectGoals"
          :key="goal"
          class="flex gap-3 rounded-2xl border border-(--sk-border) bg-zinc-50/70 p-4 dark:bg-zinc-900/40"
        >
          <UIcon
            name="i-lucide-check"
            class="w-4 h-4 mt-1 text-zinc-900 dark:text-zinc-100 shrink-0"
          />
          <span>{{ goal }}</span>
        </li>
      </ul>
    </UCard>

    <section class="space-y-3">
      <div class="flex items-center gap-2">
        <UIcon
          name="i-lucide-layers"
          class="w-5 h-5 text-zinc-600 dark:text-zinc-300"
        />
        <h2 class="text-lg font-semibold">
          기술 스택
        </h2>
      </div>

      <div class="grid lg:grid-cols-2 xl:grid-cols-3 gap-6">
        <UCard
          v-for="stack in techStacks"
          :key="stack.group"
          class="dashboard-surface rounded-3xl"
          :ui="{ body: 'p-6' }"
        >
          <template #header>
            <div class="flex items-start justify-between gap-3">
              <div class="flex items-center gap-2">
                <UIcon
                  :name="stack.icon"
                  class="w-5 h-5 text-zinc-600 dark:text-zinc-300"
                />
                <h3 class="text-lg font-semibold">
                  {{ stack.group }}
                </h3>
              </div>
              <UBadge
                :label="stack.status"
                color="neutral"
                variant="outline"
                size="xs"
                class="shrink-0"
              />
            </div>
          </template>

          <p class="mb-4 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
            {{ stack.description }}
          </p>
          <ul class="space-y-2 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
            <li
              v-for="item in stack.items"
              :key="item"
              class="flex gap-2"
            >
              <span class="mt-2 h-1.5 w-1.5 rounded-full bg-zinc-400 dark:bg-zinc-500 shrink-0" />
              <span>{{ item }}</span>
            </li>
          </ul>
        </UCard>
      </div>
    </section>

    <section class="dashboard-surface rounded-3xl p-6 md:p-8 space-y-5">
      <div class="flex flex-col md:flex-row md:items-end md:justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <UIcon
              name="i-lucide-plug"
              class="w-5 h-5 text-zinc-600 dark:text-zinc-300"
            />
            <h2 class="text-lg font-semibold">
              공개 API 목록
            </h2>
          </div>
          <p class="mt-2 text-sm text-zinc-600 dark:text-zinc-300">
            프론트엔드에서는 <code class="font-mono text-xs">/api</code> 경로로 호출하고,
            Flask 백엔드를 직접 확인할 때는 <code class="font-mono text-xs">http://localhost:5000/api</code>를 사용합니다.
          </p>
        </div>
        <UBadge
          label="현재 제공 중"
          color="neutral"
          variant="outline"
          class="w-fit"
        />
      </div>

      <div class="overflow-x-auto rounded-2xl border border-(--sk-border)">
        <table class="min-w-full divide-y divide-(--sk-border) text-sm">
          <thead class="bg-zinc-50 dark:bg-zinc-900/60">
            <tr class="text-left text-zinc-500 dark:text-zinc-400">
              <th class="px-4 py-3 font-semibold">
                Method
              </th>
              <th class="px-4 py-3 font-semibold">
                Path
              </th>
              <th class="px-4 py-3 font-semibold">
                용도
              </th>
              <th class="px-4 py-3 font-semibold">
                응답
              </th>
            </tr>
          </thead>
          <tbody class="divide-y divide-(--sk-border)">
            <tr
              v-for="endpoint in apiEndpoints"
              :key="endpoint.path"
            >
              <td class="px-4 py-4 align-top">
                <UBadge
                  :label="endpoint.method"
                  color="neutral"
                  variant="subtle"
                />
              </td>
              <td class="px-4 py-4 align-top">
                <code class="font-mono text-xs text-zinc-900 dark:text-zinc-100">{{ endpoint.path }}</code>
                <div class="mt-2 text-xs text-zinc-500 dark:text-zinc-400">
                  {{ endpoint.example }}
                </div>
              </td>
              <td class="px-4 py-4 align-top text-zinc-600 dark:text-zinc-300">
                {{ endpoint.purpose }}
              </td>
              <td class="px-4 py-4 align-top">
                <code class="font-mono text-xs text-zinc-900 dark:text-zinc-100">{{ endpoint.response }}</code>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="grid lg:grid-cols-[1fr_1.2fr] gap-6">
        <div>
          <h3 class="font-semibold">
            SemListRow 주요 필드
          </h3>
          <div class="mt-3 flex flex-wrap gap-2">
            <code
              v-for="field in semListFields"
              :key="field"
              class="rounded-full border border-(--sk-border) bg-zinc-50 px-3 py-1 text-xs text-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
            >
              {{ field }}
            </code>
          </div>
        </div>

        <div>
          <h3 class="font-semibold">
            런타임 설정
          </h3>
          <div class="mt-3 space-y-3">
            <div
              v-for="config in runtimeConfigRows"
              :key="config.name"
              class="rounded-2xl border border-(--sk-border) bg-zinc-50/70 p-4 dark:bg-zinc-900/40"
            >
              <div class="flex flex-wrap items-center gap-2">
                <code class="font-mono text-xs text-zinc-900 dark:text-zinc-100">{{ config.name }}</code>
                <span class="text-xs text-zinc-500 dark:text-zinc-400">기본값: {{ config.defaultValue }}</span>
              </div>
              <p class="mt-2 text-sm text-zinc-600 dark:text-zinc-300">
                {{ config.detail }}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
