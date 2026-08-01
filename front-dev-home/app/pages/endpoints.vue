<script setup lang="ts">
useHead({
  title: 'API 리스트 | SKEWNONO'
})

const BASE_URL = 'http://sknn.skhynix.com/api'

type ApiMethod = 'GET' | 'POST' | 'DELETE'

type ApiArg = {
  name: string
  kind: 'path' | 'query' | 'body'
  required: boolean
  note: string
}

type ApiExample = {
  path: string
  query?: Record<string, string>
  body?: unknown
}

type ApiEndpoint = {
  method: ApiMethod
  path: string
  summary: string
  args: ApiArg[]
  response: string
  auth: '토큰 가능' | '사람 세션만' | '관리자'
  example: ApiExample
}

type ApiGroup = {
  name: string
  description: string
  icon: string
  endpoints: ApiEndpoint[]
}

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
  'API는 사용자당 5초에 20회로 rate limit이 걸려 있습니다. 배치 스크립트에서 반복 호출할 때는 호출 사이에 간격을 두십시오.',
  '토큰 인증 요청은 사용자 활동 점수에는 반영되지 않지만, 운영 로그에는 api_token_id와 함께 남습니다.',
  'POST/DELETE /api/account/api-tokens는 사람 세션 전용입니다. 이미 발급된 토큰으로 새 토큰을 만들거나 폐기할 수 없습니다.'
]

const examples = [
  {
    title: 'Python — 공통 준비 코드',
    code: `import requests

BASE_URL = "${BASE_URL}"
HEADERS = {"Authorization": "Bearer skn_your_token"}`
  },
  {
    title: 'Python — 데이터 조회',
    code: `resp = requests.get(
    f"{BASE_URL}/cdsem/storage",
    headers=HEADERS,
    params={"fab_name": "M16A,R3"},
    timeout=10,
)
resp.raise_for_status()
rows = resp.json()`
  },
  {
    title: 'Python — pandas DataFrame으로 변환',
    code: `import pandas as pd

df = pd.DataFrame(rows)
print(df.head())`
  },
  {
    title: 'curl',
    code: `BASE_URL="${BASE_URL}"
SKEWNONO_TOKEN="skn_your_token"

curl -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  "$BASE_URL/sem-list"`
  }
]

const TOOL_SLUG_ARG: ApiArg = {
  name: 'tool_slug',
  kind: 'path',
  required: true,
  note: 'cdsem 또는 hvsem'
}

const FAB_NAME_ARG: ApiArg = {
  name: 'fab_name',
  kind: 'query',
  required: false,
  note: '쉼표로 여러 fab 지정 (예: M16A,R3). 생략하면 전체 fab'
}

const PERIOD_ARGS: ApiArg[] = [
  { name: 'start_date', kind: 'query', required: false, note: 'YYYY-MM-DD. 생략 시 기본 조회 기간' },
  { name: 'end_date', kind: 'query', required: false, note: 'YYYY-MM-DD. 생략 시 오늘' }
]

const LOT_CD_ARG: ApiArg = {
  name: 'lot_cd',
  kind: 'query',
  required: false,
  note: 'lot 코드로 필터'
}

const LIMIT_ARG: ApiArg = {
  name: 'limit',
  kind: 'query',
  required: false,
  note: '반환 row 수 제한'
}

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
        args: [],
        response: 'ServicesHealthResponse',
        auth: '토큰 가능',
        example: { path: '/health/services' }
      },
      {
        method: 'GET',
        path: '/api/sem-list',
        summary: 'E-Beam 장비 목록과 fab, model, vendor, IP, online/offline 기준 필드를 반환합니다.',
        args: [],
        response: 'SemListRow[]',
        auth: '토큰 가능',
        example: { path: '/sem-list' }
      },
      {
        method: 'GET',
        path: '/api/announcements',
        summary: '홈 화면 공지 목록을 반환합니다.',
        args: [],
        response: 'Announcement[]',
        auth: '토큰 가능',
        example: { path: '/announcements' }
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
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG],
        response: 'StorageRow[]',
        auth: '토큰 가능',
        example: { path: '/cdsem/storage', query: { fab_name: 'M16A,R3' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/ppid-unavailable',
        summary: 'PPID(레시피) 접근 불가 장비 목록을 반환합니다. (sem_list와 IP 매칭)',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG],
        response: 'PpidUnavailableSnapshot',
        auth: '토큰 가능',
        example: { path: '/hvsem/ppid-unavailable' }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/hardware/{eqp_id}/{service}',
        summary: 'BSM, FDC, BM/PM 같은 hardware 보조 서비스 payload를 반환합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'eqp_id', kind: 'path', required: true, note: '장비 ID (sem-list의 eqp_id)' },
          { name: 'service', kind: 'path', required: true, note: 'bsm, reso-center, fdc, mdc, sce, bm-pm, sharpness 중 하나' },
          FAB_NAME_ARG,
          { name: 'start', kind: 'query', required: false, note: 'ISO-8601 시각. 생략 시 기본 조회 기간' },
          { name: 'end', kind: 'query', required: false, note: 'ISO-8601 시각. 생략 시 현재 시각' }
        ],
        response: 'HardwareServicePayload',
        auth: '토큰 가능',
        example: { path: '/cdsem/hardware/EQP01/bsm', query: { fab_name: 'M11' } }
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
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG],
        response: 'RecipeCatalogRow[]',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-search/recipes', query: { fab_name: 'M11' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/recipe-detail',
        summary: 'recipe_name에 해당하는 open recipe 상세 데이터를 반환합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          FAB_NAME_ARG
        ],
        response: 'RecipeOpenPayload',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-search/recipe-detail', query: { recipe_name: 'RCP_001' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/parameters',
        summary: 'recipe의 parameter(idp_image_info) row 목록과 row·parameter 개수를 반환합니다. 장비에 접속하지 않으므로 가볍게 반복 호출할 수 있습니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          FAB_NAME_ARG
        ],
        response: 'ParameterListResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-search/parameters', query: { recipe_name: 'RCP_001' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/measurement-points',
        summary: '해당 parameter의 측정 위치(wafer_mp_info) row만 필터링해 반환합니다. 장비에 접속하지 않습니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          { name: 'parameter', kind: 'query', required: true, note: 'parameters 응답의 Parameter 값' },
          FAB_NAME_ARG
        ],
        response: 'MeasurementPointsResponse',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/measurement-points',
          query: { recipe_name: 'RCP_001', parameter: 'Para_13' }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/param-info',
        summary: 'parameter의 AMP, AF/PR, 이미지별 빔 조건을 반환합니다. 같은 parameter가 여러 row에 걸쳐 있으면 occurrences 배열로 모두 내려갑니다. 장비 FTP를 읽으므로 occurrence당 최대 5개 파일을 조회합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          { name: 'parameter', kind: 'query', required: true, note: 'parameters 응답의 Parameter 값' },
          {
            name: 'include',
            kind: 'query',
            required: false,
            note: 'amp, af_pr, images 중 쉼표로 지정. 생략하면 전체입니다. 제외한 항목은 장비 파일을 읽지 않으므로 호출이 가벼워집니다'
          },
          FAB_NAME_ARG
        ],
        response: 'ParamInfoResponse',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/param-info',
          query: { recipe_name: 'RCP_001', parameter: 'Para_13', include: 'amp' }
        }
      },
      {
        method: 'POST',
        path: '/api/{tool_slug}/recipe-search/param-detail',
        summary: '여러 (recipe, parameter) 조합의 원본 폴더 설정을 한 번에 조회합니다. locator와 img_* slot 값을 직접 넘겨야 하므로, 단건 조회는 param-info가 더 간단합니다.',
        args: [
          TOOL_SLUG_ARG,
          {
            name: 'items',
            kind: 'body',
            required: true,
            note: '[{ locator, parameter, slots }] — 최대 200건. locator와 slots는 parameters 응답에서 얻습니다'
          }
        ],
        response: 'ParamDetailResponse[]',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/param-detail',
          body: {
            items: [{
              locator: { eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B' },
              parameter: 'Para_13',
              slots: { img_meas2: 'PRMS0000' }
            }]
          }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/align-detail',
        summary: 'wafer align point별 이미지, 빔 조건, AF/PR 설정을 한 번에 반환합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'eqp_ip', kind: 'query', required: true, note: 'recipe-detail 응답 locator의 eqp_ip' },
          { name: 'class_name', kind: 'query', required: true, note: 'locator의 class_name' },
          { name: 'idw', kind: 'query', required: true, note: 'locator의 idw' },
          { name: 'idp', kind: 'query', required: true, note: 'locator의 idp' },
          { name: 'p_numbers', kind: 'query', required: true, note: '쉼표로 구분한 P.No 정수 목록 (최대 200개)' }
        ],
        response: 'AlignDetailResponse',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/align-detail',
          query: {
            eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B', p_numbers: '1,2'
          }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/recipe-image',
        summary: '원본 recipe 이미지 1장을 바이트로 반환합니다. JSON이 아니라 이미지 응답이며, 파일명은 param-info나 param-detail의 images에서 얻습니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'eqp_ip', kind: 'query', required: true, note: 'locator의 eqp_ip' },
          { name: 'class_name', kind: 'query', required: true, note: 'locator의 class_name' },
          { name: 'idw', kind: 'query', required: true, note: 'locator의 idw' },
          { name: 'idp', kind: 'query', required: true, note: 'locator의 idp' },
          { name: 'name', kind: 'query', required: true, note: '이미지 파일명 (최대 256자)' }
        ],
        response: 'image/jpeg',
        auth: '토큰 가능',
        example: {
          path: '/cdsem/recipe-search/recipe-image',
          query: {
            eqp_ip: '10.1.2.3', class_name: 'CLS', idw: 'IDW_A', idp: 'IDP_B', name: 'IMMP0004.jpeg'
          }
        }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-search/lateral',
        summary: 'recipe_name에 해당하는 lateral recipe 데이터를 반환합니다.',
        args: [
          TOOL_SLUG_ARG,
          { name: 'recipe_name', kind: 'query', required: true, note: '조회할 recipe 이름' },
          FAB_NAME_ARG
        ],
        response: 'LateralRecipePayload',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-search/lateral', query: { recipe_name: 'RCP_001' } }
      },
      {
        method: 'GET',
        path: '/api/meas-hist',
        summary: 'tool_type, fab_name, recipe_name 기준 measurement history를 조회합니다.',
        args: [
          { name: 'tool_type', kind: 'query', required: false, note: 'cd-sem 또는 hv-sem' },
          { name: 'fab_name', kind: 'query', required: false, note: 'fab 이름 하나 (예: M11)' },
          { name: 'recipe_name', kind: 'query', required: false, note: 'recipe 이름으로 필터' }
        ],
        response: 'MeasHistPayload',
        auth: '토큰 가능',
        example: { path: '/meas-hist', query: { tool_type: 'cd-sem', fab_name: 'M11' } }
      },
      {
        method: 'GET',
        path: '/api/msr-file',
        summary: 'MSR identifier로 raw measurement file 정보를 조회합니다.',
        args: [
          { name: 'msr', kind: 'query', required: true, note: 'MSR identifier' },
          { name: 'class_name', kind: 'query', required: false, note: 'measurement class 이름' },
          { name: 'total_images', kind: 'query', required: false, note: '이미지 수 힌트 (정수)' }
        ],
        response: 'MsrFilePayload',
        auth: '토큰 가능',
        example: { path: '/msr-file', query: { msr: 'MSR_001' } }
      },
      {
        method: 'POST',
        path: '/api/msr-files',
        summary: '여러 MSR의 raw measurement file 정보를 한 번에 조회합니다 (스큐보아 다중 선택).',
        args: [
          { name: 'items', kind: 'body', required: true, note: '[{ msr, class_name?, total_images? }] — 최대 200건' }
        ],
        response: '{ results: MsrFilePayload[] }',
        auth: '토큰 가능',
        example: { path: '/msr-files', body: { items: [{ msr: 'MSR_001' }, { msr: 'MSR_002' }] } }
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
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG, LIMIT_ARG],
        response: 'RecipeTatRankingResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-tat/ranking', query: { fab_name: 'M11', limit: '100' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/summary',
        summary: 'recipe TAT summary 지표를 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG],
        response: 'RecipeTatSummaryResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-tat/summary', query: { lot_cd: 'LOT001' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/daily-trend',
        summary: 'recipe TAT 일자별 trend point를 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG],
        response: 'RecipeTatTrendResponse',
        auth: '토큰 가능',
        example: { path: '/hvsem/recipe-tat/daily-trend', query: { fab_name: 'M14' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/recipe-tat/devices',
        summary: 'recipe TAT 화면에서 선택할 device 목록을 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS],
        response: 'RecipeTatDeviceResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/recipe-tat/devices', query: { fab_name: 'M11' } }
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
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG],
        response: 'FailIssueSummaryResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/fail-issue/summary', query: { fab_name: 'M11' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/daily-trend',
        summary: 'fail issue 일자별 trend point를 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG],
        response: 'FailIssueTrendResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/fail-issue/daily-trend', query: { lot_cd: 'LOT001' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/align-ranking',
        summary: 'align fail ranking row를 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG, LIMIT_ARG],
        response: 'FailIssueRankingResponse',
        auth: '토큰 가능',
        example: { path: '/hvsem/fail-issue/align-ranking', query: { limit: '50' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/meas-ranking',
        summary: 'measurement fail ranking row를 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS, LOT_CD_ARG, LIMIT_ARG],
        response: 'FailIssueRankingResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/fail-issue/meas-ranking', query: { fab_name: 'M11' } }
      },
      {
        method: 'GET',
        path: '/api/{tool_slug}/fail-issue/devices',
        summary: 'fail issue 화면에서 선택할 device 목록을 반환합니다.',
        args: [TOOL_SLUG_ARG, FAB_NAME_ARG, ...PERIOD_ARGS],
        response: 'FailIssueDeviceResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/fail-issue/devices' }
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
        args: [],
        response: 'R3DeviceGroupRow[]',
        auth: '토큰 가능',
        example: { path: '/cdsem/device-statistics/r3-device-grp' }
      },
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/device-desc',
        summary: 'fac_id 기준 device description row를 반환합니다.',
        args: [
          { name: 'fac_id', kind: 'query', required: false, note: '쉼표로 여러 fac 지정 (예: M11,M14). 생략하면 전체' }
        ],
        response: 'DeviceDescRow[]',
        auth: '토큰 가능',
        example: { path: '/cdsem/device-statistics/device-desc', query: { fac_id: 'M11,M14' } }
      },
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/recipe-statistics',
        summary: 'lot_cds 기준 최신 주차 recipe statistics bucket을 반환합니다.',
        args: [
          { name: 'lot_cds', kind: 'query', required: false, note: '쉼표로 lot 코드 여러 개 (예: R001,R002)' }
        ],
        response: 'RecipeStatisticsResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/device-statistics/recipe-statistics', query: { lot_cds: 'R001,R002' } }
      },
      {
        method: 'GET',
        path: '/api/cdsem/device-statistics/recipe-trend',
        summary: 'lot_cds와 기간 기준 주차별 recipe statistics trend를 반환합니다.',
        args: [
          { name: 'lot_cds', kind: 'query', required: false, note: '쉼표로 lot 코드 여러 개' },
          ...PERIOD_ARGS
        ],
        response: 'RecipeTrendResponse',
        auth: '토큰 가능',
        example: { path: '/cdsem/device-statistics/recipe-trend', query: { lot_cds: 'R001' } }
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
        args: [],
        response: 'AfmTool[]',
        auth: '토큰 가능',
        example: { path: '/afm/tools' }
      },
      {
        method: 'GET',
        path: '/api/afm/files',
        summary: 'AFM measurement file 목록을 반환합니다.',
        args: [
          { name: 'tool', kind: 'query', required: false, note: 'AFM tool 이름 (/afm/tools 참조). 생략 시 기본 tool' }
        ],
        response: 'AfmFileListResponse',
        auth: '토큰 가능',
        example: { path: '/afm/files', query: { tool: 'AFM01' } }
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}',
        summary: 'AFM measurement file 상세 정보를 반환합니다.',
        args: [
          { name: 'filename', kind: 'path', required: true, note: 'AFM measurement file 이름' },
          { name: 'tool', kind: 'query', required: false, note: 'AFM tool 이름' }
        ],
        response: 'AfmFileDetailResponse',
        auth: '토큰 가능',
        example: { path: '/afm/files/sample.dat' }
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}/profile/{point}',
        summary: 'AFM profile point 데이터를 반환합니다.',
        args: [
          { name: 'filename', kind: 'path', required: true, note: 'AFM measurement file 이름' },
          { name: 'point', kind: 'path', required: true, note: 'profile point 라벨 (예: P1)' },
          { name: 'tool', kind: 'query', required: false, note: 'AFM tool 이름' },
          { name: 'site_id', kind: 'query', required: false, note: '측정 site ID' },
          { name: 'site_x', kind: 'query', required: false, note: 'site X 좌표' },
          { name: 'site_y', kind: 'query', required: false, note: 'site Y 좌표' },
          { name: 'point_no', kind: 'query', required: false, note: 'point 번호 (정수)' }
        ],
        response: 'AfmProfileResponse',
        auth: '토큰 가능',
        example: { path: '/afm/files/sample.dat/profile/P1' }
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}/image/{point}',
        summary: 'AFM image metadata와 image-file URL을 반환합니다.',
        args: [
          { name: 'filename', kind: 'path', required: true, note: 'AFM measurement file 이름' },
          { name: 'point', kind: 'path', required: true, note: 'profile point 라벨' },
          { name: 'tool', kind: 'query', required: false, note: 'AFM tool 이름' }
        ],
        response: 'AfmImageResponse',
        auth: '토큰 가능',
        example: { path: '/afm/files/sample.dat/image/P1' }
      },
      {
        method: 'GET',
        path: '/api/afm/files/{filename}/image-file/{point}',
        summary: 'AFM profile image file을 SVG로 반환합니다.',
        args: [
          { name: 'filename', kind: 'path', required: true, note: 'AFM measurement file 이름' },
          { name: 'point', kind: 'path', required: true, note: 'profile point 라벨' },
          { name: 'tool', kind: 'query', required: false, note: 'AFM tool 이름' }
        ],
        response: 'image/svg+xml',
        auth: '토큰 가능',
        example: { path: '/afm/files/sample.dat/image-file/P1' }
      },
      {
        method: 'GET',
        path: '/api/afm/activities',
        summary: 'AFM 사용자 활동 목록을 반환합니다.',
        args: [
          { name: 'user', kind: 'query', required: false, note: '특정 사용자로 필터' },
          { name: 'limit', kind: 'query', required: false, note: '반환 건수 (기본 100)' }
        ],
        response: 'AfmActivityResponse',
        auth: '토큰 가능',
        example: { path: '/afm/activities', query: { limit: '50' } }
      },
      {
        method: 'GET',
        path: '/api/afm/analytics',
        summary: 'AFM activity analytics를 반환합니다.',
        args: [
          { name: 'days', kind: 'query', required: false, note: '조회 기간 일수 (기본 7)' }
        ],
        response: 'AfmAnalyticsResponse',
        auth: '토큰 가능',
        example: { path: '/afm/analytics', query: { days: '7' } }
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
        args: [],
        response: '{ tokens: ApiTokenView[] }',
        auth: '토큰 가능',
        example: { path: '/account/api-tokens' }
      },
      {
        method: 'POST',
        path: '/api/account/api-tokens',
        summary: '새 API token을 발급합니다. 토큰 인증으로는 호출할 수 없습니다.',
        args: [
          { name: 'label', kind: 'body', required: true, note: '토큰 용도를 구분할 이름' }
        ],
        response: '{ token: ApiTokenView, plaintext: string }',
        auth: '사람 세션만',
        example: { path: '/account/api-tokens', body: { label: 'my-script' } }
      },
      {
        method: 'DELETE',
        path: '/api/account/api-tokens/{token_id}',
        summary: '내 API token을 폐기합니다. 토큰 인증으로는 호출할 수 없습니다.',
        args: [
          { name: 'token_id', kind: 'path', required: true, note: '폐기할 token의 ID (GET 목록의 id)' }
        ],
        response: '{ revoked: string }',
        auth: '사람 세션만',
        example: { path: '/account/api-tokens/<token_id>' }
      },
      {
        method: 'GET',
        path: '/api/activity/me',
        summary: '현재 사용자 활동 요약을 반환합니다.',
        args: [],
        response: 'ActivityMeResponse',
        auth: '토큰 가능',
        example: { path: '/activity/me' }
      },
      {
        method: 'GET',
        path: '/api/activity/summary',
        summary: '전체 사용자 활동 summary를 반환합니다.',
        args: [],
        response: 'ActivitySummaryResponse',
        auth: '관리자',
        example: { path: '/activity/summary' }
      },
      {
        method: 'GET',
        path: '/api/admin/logs',
        summary: '운영 로그를 조건별로 조회합니다.',
        args: [
          { name: 'level', kind: 'query', required: false, note: '쉼표로 여러 level (예: ERROR,WARNING)' },
          { name: 'path', kind: 'query', required: false, note: '요청 경로 부분 일치' },
          { name: 'user_id', kind: 'query', required: false, note: '사용자 ID 정확히 일치' },
          { name: 'q', kind: 'query', required: false, note: '메시지, 경로, 예외 내용 전문 검색' },
          { name: 'from', kind: 'query', required: false, note: 'ISO-8601 시각 이후 로그만' },
          { name: 'to', kind: 'query', required: false, note: 'ISO-8601 시각 이전 로그만' },
          { name: 'limit', kind: 'query', required: false, note: '반환 건수 제한' }
        ],
        response: 'AdminLogQueryResponse',
        auth: '관리자',
        example: { path: '/admin/logs', query: { level: 'ERROR', limit: '50' } }
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

const toQueryString = (query?: Record<string, string>): string => {
  if (!query) return ''
  const parts = Object.entries(query).map(([key, value]) => `${key}=${value}`)
  return parts.length ? `?${parts.join('&')}` : ''
}

const curlExample = (endpoint: ApiEndpoint): string => {
  const url = `$BASE_URL${endpoint.example.path}${toQueryString(endpoint.example.query)}`
  if (endpoint.method === 'POST') {
    return `curl -X POST \\
  -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '${JSON.stringify(endpoint.example.body)}' \\
  "${url}"`
  }
  if (endpoint.method === 'DELETE') {
    return `curl -X DELETE -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  "${url}"`
  }
  return `curl -H "Authorization: Bearer $SKEWNONO_TOKEN" \\
  "${url}"`
}

const pythonExample = (endpoint: ApiEndpoint): string => {
  const lines = [
    `resp = requests.${endpoint.method.toLowerCase()}(`,
    `    f"{BASE_URL}${endpoint.example.path}",`,
    '    headers=HEADERS,'
  ]
  if (endpoint.example.query) {
    lines.push(`    params=${JSON.stringify(endpoint.example.query)},`)
  }
  if (endpoint.example.body !== undefined) {
    lines.push(`    json=${JSON.stringify(endpoint.example.body)},`)
  }
  lines.push('    timeout=10,', ')', 'resp.raise_for_status()', 'data = resp.json()')
  return lines.join('\n')
}
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
