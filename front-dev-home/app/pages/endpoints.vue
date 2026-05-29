<script setup lang="ts">
definePageMeta({
  layout: 'hub'
})

useHead({
  title: 'API 리스트 | SKEWNONO'
})

type ApiMethod = 'GET' | 'POST' | 'DELETE'

type ApiEndpoint = {
  method: ApiMethod
  path: string
  summary: string
  params: string
  response: string
  auth: '토큰 가능' | '사람 세션만' | '관리자'
  example: string
}

type ApiGroup = {
  name: string
  description: string
  icon: string
  endpoints: ApiEndpoint[]
}

const baseUrlRows = [
  {
    label: '프론트엔드 내부 호출',
    value: '/api',
    detail: 'Nuxt 화면과 composable에서 사용하는 기본 경로입니다.'
  },
  {
    label: '로컬 Flask 직접 호출',
    value: 'http://localhost:5000/api',
    detail: '개인 개발 환경에서 백엔드만 띄워 확인할 때 사용합니다.'
  },
  {
    label: '회사/운영 환경',
    value: 'https://<skewnono-host>/api',
    detail: '회사망에서 개인 스크립트나 배치가 데이터를 가져갈 때 사용하는 기준입니다.'
  }
]

const tokenSteps = [
  {
    title: 'Settings에서 API Tokens 열기',
    detail: '우측 상단 설정 버튼으로 이동한 뒤 API Tokens 섹션에서 New token을 누릅니다.'
  },
  {
    title: '토큰 이름 입력',
    detail: 'nightly-script, jupyter-analysis처럼 나중에 용도를 구분할 수 있는 label을 입력합니다.'
  },
  {
    title: '토큰 원문 저장',
    detail: '발급된 plaintext token은 한 번만 보입니다. 닫기 전에 안전한 곳에 저장해야 합니다.'
  },
  {
    title: 'Bearer 헤더로 호출',
    detail: '외부 개발 환경에서는 Authorization: Bearer skn_... 헤더를 붙여 /api/* 읽기 endpoint를 호출합니다.'
  }
]

const authNotes = [
  '토큰은 계정과 같은 읽기 권한을 가집니다. 유출되면 Settings의 API Tokens에서 즉시 Revoke 하십시오.',
  '토큰 인증 요청은 사용자 활동 점수에는 반영되지 않지만, 운영 로그에는 api_token_id와 함께 남습니다.',
  'POST/DELETE /api/account/api-tokens는 사람 세션 전용입니다. 이미 발급된 토큰으로 새 토큰을 만들거나 폐기할 수 없습니다.'
]

const examples = [
  {
    title: 'curl',
    code: `BASE_URL="https://<skewnono-host>/api"
SKEWNONO_TOKEN="skn_your_token"

curl -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  "$BASE_URL/sem-list"`
  },
  {
    title: 'Python requests',
    code: `import requests

base_url = "https://<skewnono-host>/api"
headers = {"Authorization": "Bearer skn_your_token"}

response = requests.get(f"{base_url}/cdsem/storage", headers=headers, timeout=10)
response.raise_for_status()
rows = response.json()`
  },
  {
    title: 'Nuxt / Vue',
    code: `const rows = await $fetch('/api/cdsem/storage', {
  query: { fac_id: 'M11,M14' }
})`
  }
]

const apiGroups: ApiGroup[] = [
  {
    name: '공통',
    description: '서비스 상태, 공지, SEM 장비 기준 목록입니다.',
    icon: 'i-lucide-server',
    endpoints: [
      {
        method: 'GET',
        path: '/api/health/services',
        summary: 'OpenSearch, Redis, MinIO 같은 백엔드 의존 서비스 상태를 반환합니다.',
        params: '없음',
        response: 'ServicesHealthResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/health/services"'
      },
      {
        method: 'GET',
        path: '/api/sem-list',
        summary: 'E-Beam 장비 목록과 fab, model, vendor, IP, online/offline 기준 필드를 반환합니다.',
        params: '없음',
        response: 'SemListRow[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/sem-list"'
      },
      {
        method: 'GET',
        path: '/api/announcements',
        summary: '홈 화면 공지 목록을 반환합니다.',
        params: '없음',
        response: 'Announcement[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/announcements"'
      }
    ]
  },
  {
    name: 'E-Beam Storage / Hardware',
    description: 'CD-SEM/HV-SEM 장비 상태, storage, hardware 보조 서비스 데이터입니다.',
    icon: 'i-lucide-hard-drive',
    endpoints: [
      {
        method: 'GET',
        path: '/api/{tool_slug}/storage',
        summary: 'tool_slug가 cdsem 또는 hvsem일 때 storage 현황 row를 반환합니다.',
        params: 'fac_id=M11,M14 optional',
        response: 'StorageRow[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/storage?fac_id=M11,M14"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/ppid-unavailable',
        summary: 'PPID(레시피) 접근 불가 장비 목록을 반환합니다. (sem_list와 IP 매칭)',
        params: 'fac_id=M11,M14 optional',
        response: 'PpidUnavailableSnapshot',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/hvsem/ppid-unavailable"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/hardware/{service}',
        summary: 'BSM, FDC, BM/PM 같은 hardware 보조 서비스 payload를 반환합니다.',
        params: 'eqp_id optional, fab_id optional',
        response: 'HardwareServicePayload',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/hardware/bsm?fab_id=M11"'
      }
    ]
  },
  {
    name: 'Recipe Search',
    description: 'recipe catalog, open recipe, lateral recipe, measurement history, MSR file 데이터입니다.',
    icon: 'i-lucide-search-code',
    endpoints: [
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/recipes',
        summary: 'CD-SEM/HV-SEM recipe 목록을 fab 기준으로 조회합니다.',
        params: 'fab_name optional',
        response: 'RecipeCatalogRow[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/recipe-search/recipes?fab_name=M11"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/recipe-detail',
        summary: 'recipe_name에 해당하는 open recipe 상세 데이터를 반환합니다.',
        params: 'recipe_name required, fab_name optional',
        response: 'RecipeOpenPayload',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/recipe-search/recipe-detail?recipe_name=RCP_001"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/lateral',
        summary: 'recipe_name에 해당하는 lateral recipe 데이터를 반환합니다.',
        params: 'recipe_name required, fab_name optional',
        response: 'LateralRecipePayload',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/recipe-search/lateral?recipe_name=RCP_001"'
      },
      {
        method: 'GET',
        path: '/api/meas-hist',
        summary: 'tool_type, fab_name, recipe_name 기준 measurement history를 조회합니다.',
        params: 'tool_type optional, fab_name optional, recipe_name optional',
        response: 'MeasHistPayload',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/meas-hist?tool_type=cd-sem&fab_name=M11"'
      },
      {
        method: 'GET',
        path: '/api/msr-file',
        summary: 'MSR identifier로 raw measurement file 정보를 조회합니다.',
        params: 'msr required, class_name optional, total_images optional',
        response: 'MsrFilePayload',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/msr-file?msr=MSR_001"'
      }
    ]
  },
  {
    name: 'Recipe TAT',
    description: '기간, fab, lot 기준 recipe TAT ranking, summary, trend, device 목록입니다.',
    icon: 'i-lucide-timer',
    endpoints: [
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/ranking',
        summary: 'recipe TAT ranking row를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd, limit optional',
        response: 'RecipeTatRankingResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/recipe-tat/ranking?fab_id=M11&limit=100"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/summary',
        summary: 'recipe TAT summary 지표를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd optional',
        response: 'RecipeTatSummaryResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/recipe-tat/summary?lot_cd=LOT001"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/daily-trend',
        summary: 'recipe TAT 일자별 trend point를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd optional',
        response: 'RecipeTatTrendResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/hvsem/recipe-tat/daily-trend?fab_id=M14"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/devices',
        summary: 'recipe TAT 화면에서 선택할 device 목록을 반환합니다.',
        params: 'fab_id, start_date, end_date optional',
        response: 'RecipeTatDeviceResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/recipe-tat/devices?fab_id=M11"'
      }
    ]
  },
  {
    name: 'Fail Issue',
    description: '기간, fab, lot 기준 fail issue summary, trend, ranking, device 목록입니다.',
    icon: 'i-lucide-triangle-alert',
    endpoints: [
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/summary',
        summary: 'fail issue summary 지표를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd optional',
        response: 'FailIssueSummaryResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/fail-issue/summary?fab_id=M11"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/daily-trend',
        summary: 'fail issue 일자별 trend point를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd optional',
        response: 'FailIssueTrendResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/fail-issue/daily-trend?lot_cd=LOT001"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/align-ranking',
        summary: 'align fail ranking row를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd, limit optional',
        response: 'FailIssueRankingResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/hvsem/fail-issue/align-ranking?limit=50"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/meas-ranking',
        summary: 'measurement fail ranking row를 반환합니다.',
        params: 'fab_id, start_date, end_date, lot_cd, limit optional',
        response: 'FailIssueRankingResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/fail-issue/meas-ranking?fab_id=M11"'
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/devices',
        summary: 'fail issue 화면에서 선택할 device 목록을 반환합니다.',
        params: 'fab_id, start_date, end_date optional',
        response: 'FailIssueDeviceResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/fail-issue/devices"'
      }
    ]
  },
  {
    name: 'CD-SEM Device Statistics',
    description: 'CD-SEM device 통계와 lot별 recipe statistics/trend 데이터입니다.',
    icon: 'i-lucide-table-properties',
    endpoints: [
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/r3-device-grp',
        summary: 'R3 device group 기준 row를 반환합니다.',
        params: '없음',
        response: 'R3DeviceGroupRow[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/device-statistics/r3-device-grp"'
      },
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/device-desc',
        summary: 'fac_id 기준 device description row를 반환합니다.',
        params: 'fac_id=M11,M14 optional',
        response: 'DeviceDescRow[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/device-statistics/device-desc?fac_id=M11,M14"'
      },
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/recipe-statistics',
        summary: 'lot_cds 기준 최신 주차 recipe statistics bucket을 반환합니다.',
        params: 'lot_cds comma-separated optional',
        response: 'RecipeStatisticsResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/device-statistics/recipe-statistics?lot_cds=R001,R002"'
      },
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/recipe-trend',
        summary: 'lot_cds와 기간 기준 주차별 recipe statistics trend를 반환합니다.',
        params: 'lot_cds, start_date, end_date optional',
        response: 'RecipeTrendResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/cdsem/device-statistics/recipe-trend?lot_cds=R001"'
      }
    ]
  },
  {
    name: 'AFM',
    description: 'AFM tool, file, profile, image, activity 데이터입니다.',
    icon: 'i-lucide-ruler',
    endpoints: [
      {
        method: 'GET',
        path: '/api/afm/tools',
        summary: 'AFM tool 목록을 반환합니다.',
        params: '없음',
        response: 'AfmTool[]',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/tools"'
      },
      {
        method: 'GET',
        path: '/api/afm/files',
        summary: 'AFM measurement file 목록을 반환합니다.',
        params: 'tool optional',
        response: 'AfmFileListResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/files?tool=AFM01"'
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}',
        summary: 'AFM measurement file 상세 정보를 반환합니다.',
        params: 'tool optional',
        response: 'AfmFileDetailResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/files/sample.dat"'
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}/profile/{point}',
        summary: 'AFM profile point 데이터를 반환합니다.',
        params: 'tool, site_id, site_x, site_y, point_no optional',
        response: 'AfmProfileResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/files/sample.dat/profile/P1"'
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}/image/{point}',
        summary: 'AFM image metadata와 image-file URL을 반환합니다.',
        params: 'tool optional',
        response: 'AfmImageResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/files/sample.dat/image/P1"'
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}/image-file/{point}',
        summary: 'AFM profile image file을 SVG로 반환합니다.',
        params: 'tool optional',
        response: 'image/svg+xml',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/files/sample.dat/image-file/P1"'
      },
      {
        method: 'GET',
        path: '/api/afm/activities',
        summary: 'AFM 사용자 활동 목록을 반환합니다.',
        params: 'user, limit optional',
        response: 'AfmActivityResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/activities?limit=50"'
      },
      {
        method: 'GET',
        path: '/api/afm/analytics',
        summary: 'AFM activity analytics를 반환합니다.',
        params: 'days optional',
        response: 'AfmAnalyticsResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/afm/analytics?days=7"'
      }
    ]
  },
  {
    name: '계정, 활동, 운영',
    description: 'API token 관리, 사용자 활동 통계, 운영 로그 조회 endpoint입니다.',
    icon: 'i-lucide-shield-check',
    endpoints: [
      {
        method: 'GET',
        path: '/api/account/api-tokens',
        summary: '내 API token 목록을 반환합니다.',
        params: '없음',
        response: '{ tokens: ApiTokenView[] }',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/account/api-tokens"'
      },
      {
        method: 'POST',
        path: '/api/account/api-tokens',
        summary: '새 API token을 발급합니다. 토큰 인증으로는 호출할 수 없습니다.',
        params: 'JSON body: { label: string }',
        response: '{ token: ApiTokenView, plaintext: string }',
        auth: '사람 세션만',
        example: 'curl -X POST -H "Content-Type: application/json" -d "{\\"label\\":\\"my-script\\"}" "$BASE_URL/account/api-tokens"'
      },
      {
        method: 'DELETE',
        path: '/api/account/api-tokens/{token_id}',
        summary: '내 API token을 폐기합니다. 토큰 인증으로는 호출할 수 없습니다.',
        params: 'token_id path parameter',
        response: '{ revoked: string }',
        auth: '사람 세션만',
        example: 'curl -X DELETE "$BASE_URL/account/api-tokens/<token_id>"'
      },
      {
        method: 'GET',
        path: '/api/activity/me',
        summary: '현재 사용자 활동 요약을 반환합니다.',
        params: '없음',
        response: 'ActivityMeResponse',
        auth: '토큰 가능',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/activity/me"'
      },
      {
        method: 'GET',
        path: '/api/activity/summary',
        summary: '전체 사용자 활동 summary를 반환합니다.',
        params: '없음',
        response: 'ActivitySummaryResponse',
        auth: '관리자',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/activity/summary"'
      },
      {
        method: 'GET',
        path: '/api/admin/logs',
        summary: '운영 로그를 조건별로 조회합니다.',
        params: 'level, path, user_id, limit optional',
        response: 'AdminLogQueryResponse',
        auth: '관리자',
        example: 'curl -H "Authorization: Bearer $SKEWNONO_TOKEN" "$BASE_URL/admin/logs?level=ERROR&limit=50"'
      }
    ]
  }
]

const totalEndpoints = computed(() =>
  apiGroups.reduce((count, group) => count + group.endpoints.length, 0)
)

const activePanel = ref('tokens')
const selectedApiGroup = computed<ApiGroup>(() =>
  apiGroups.find(group => group.name === activePanel.value) ?? apiGroups[0]!
)

const methodColor = (method: ApiMethod): 'primary' | 'success' | 'error' => {
  if (method === 'POST') return 'success'
  if (method === 'DELETE') return 'error'
  return 'primary'
}
</script>

<template>
  <div class="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8 lg:px-8">
    <div class="grid gap-8 lg:grid-cols-[260px_minmax(0,1fr)]">
      <aside class="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
        <nav
          class="space-y-6 border-b border-(--sk-border) pb-5 lg:border-b-0 lg:border-r lg:pb-0 lg:pr-6"
          aria-label="Information sections"
        >
          <div>
            <p class="mb-2 text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
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
            <p class="mb-2 text-xs font-semibold uppercase text-zinc-500 dark:text-zinc-400">
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
                  :class="activePanel === group.name ? 'bg-white/15 dark:bg-zinc-950/10' : 'bg-zinc-100 text-zinc-500 dark:bg-zinc-900 dark:text-zinc-400'"
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
            <div class="flex items-center gap-2 text-sm font-semibold text-zinc-500 dark:text-zinc-400">
              <UIcon
                name="i-lucide-plug"
                class="h-4 w-4"
              />
              <span>Developer API</span>
            </div>
            <div class="mt-3 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div class="max-w-3xl">
                <h1 class="text-2xl font-semibold text-zinc-950 dark:text-white md:text-4xl">
                  API Token 사용법
                </h1>
                <p class="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300 md:text-base">
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
                <h2 class="text-lg font-semibold">
                  Base URL
                </h2>
              </div>
              <div class="overflow-hidden rounded-lg border border-(--sk-border)">
                <table class="min-w-full divide-y divide-(--sk-border) text-sm">
                  <tbody class="divide-y divide-(--sk-border)">
                    <tr
                      v-for="row in baseUrlRows"
                      :key="row.label"
                      class="bg-white dark:bg-zinc-950"
                    >
                      <th class="w-44 px-4 py-4 text-left align-top font-semibold">
                        {{ row.label }}
                      </th>
                      <td class="px-4 py-4 align-top">
                        <code class="font-mono text-xs text-zinc-950 dark:text-white">{{ row.value }}</code>
                        <p class="mt-2 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
                          {{ row.detail }}
                        </p>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="space-y-4">
              <div class="flex items-center gap-2">
                <UIcon
                  name="i-lucide-list-checks"
                  class="h-5 w-5 text-zinc-600 dark:text-zinc-300"
                />
                <h2 class="text-lg font-semibold">
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
                    <span class="block font-semibold">{{ step.title }}</span>
                    <span class="mt-1 block text-sm leading-6 text-zinc-600 dark:text-zinc-300">{{ step.detail }}</span>
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
                <h2 class="text-lg font-semibold">
                  토큰 주의사항
                </h2>
              </div>
              <ul class="mt-4 space-y-3 text-sm leading-6 text-zinc-600 dark:text-zinc-300">
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
                <h2 class="text-lg font-semibold">
                  호출 예시
                </h2>
              </div>
              <div class="mt-4 grid gap-4">
                <div
                  v-for="example in examples"
                  :key="example.title"
                  class="overflow-hidden rounded-lg border border-(--sk-border) bg-white dark:bg-zinc-950"
                >
                  <div class="border-b border-(--sk-border) px-4 py-3 text-sm font-semibold">
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
            <div class="flex items-center gap-2 text-sm font-semibold text-zinc-500 dark:text-zinc-400">
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
                  <h1 class="text-2xl font-semibold text-zinc-950 dark:text-white md:text-4xl">
                    {{ selectedApiGroup.name }}
                  </h1>
                </div>
                <p class="mt-3 text-sm leading-7 text-zinc-600 dark:text-zinc-300 md:text-base">
                  {{ selectedApiGroup.description }}
                </p>
              </div>
              <div class="grid grid-cols-2 gap-3 sm:flex">
                <div class="rounded-lg border border-(--sk-border) bg-white px-4 py-3 dark:bg-zinc-950">
                  <div class="text-xs text-zinc-500 dark:text-zinc-400">
                    선택 항목
                  </div>
                  <div class="mt-1 text-xl font-semibold">
                    {{ selectedApiGroup.endpoints.length }}
                  </div>
                </div>
                <div class="rounded-lg border border-(--sk-border) bg-white px-4 py-3 dark:bg-zinc-950">
                  <div class="text-xs text-zinc-500 dark:text-zinc-400">
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
                    <code class="break-all font-mono text-xs text-zinc-950 dark:text-white">{{ endpoint.path }}</code>
                  </div>
                  <p class="text-sm leading-6 text-zinc-600 dark:text-zinc-300">
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

              <dl class="mt-4 grid gap-3 md:grid-cols-2">
                <div class="rounded-md bg-zinc-50 p-3 dark:bg-zinc-900">
                  <dt class="text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                    Parameter
                  </dt>
                  <dd class="mt-1">
                    <code class="break-words font-mono text-xs text-zinc-800 dark:text-zinc-200">{{ endpoint.params }}</code>
                  </dd>
                </div>
                <div class="rounded-md bg-zinc-50 p-3 dark:bg-zinc-900">
                  <dt class="text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                    Response
                  </dt>
                  <dd class="mt-1">
                    <code class="break-words font-mono text-xs text-zinc-800 dark:text-zinc-200">{{ endpoint.response }}</code>
                  </dd>
                </div>
              </dl>

              <div class="mt-4 overflow-hidden rounded-md bg-zinc-50 dark:bg-zinc-900">
                <div class="border-b border-(--sk-border) px-3 py-2 text-xs font-semibold text-zinc-500 dark:text-zinc-400">
                  Example
                </div>
                <pre class="whitespace-pre-wrap break-words p-3 text-[11px] leading-5 text-zinc-600 dark:text-zinc-300"><code>{{ endpoint.example }}</code></pre>
              </div>
            </article>
          </div>
        </section>
      </main>
    </div>
  </div>
</template>
