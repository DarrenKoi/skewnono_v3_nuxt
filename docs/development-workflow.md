# Development Workflow — Contract-First, Two-Location Architecture

## The Problem

- **Home**: Frontend-only development (Nuxt 4), no backend access. Can push to GitHub.
- **Work**: Backend development (Flask + Elasticsearch 7.14 + Redis). Can pull from GitHub but **cannot push** code to internet.
- **Goal**: Seamless switching between mock data (home) and real Flask backend (work) with zero code changes.

## Architecture Overview

```text
Home (Phase 1)                          Work (Phase 2/3)
┌──────────────────┐                    ┌──────────────────────────┐
│ nuxt dev         │                    │ nuxt dev + flask run     │
│                  │                    │                          │
│ Page → $fetch    │                    │ Page → $fetch            │
│   → server/api/  │ ── git push ──>   │   → devProxy             │
│   → mock data    │                    │   → Flask :5000          │
│                  │                    │   → ES / Redis           │
└──────────────────┘                    └──────────────────────────┘

                                        Phase 3 (Production)
                                        ┌──────────────────────────┐
                                        │ Flask serves dist/       │
                                        │ + handles /api routes    │
                                        └──────────────────────────┘
```

**Switching mechanism**: `NUXT_USE_MOCK` env var controls Nitro's devProxy.

| Environment | NUXT_USE_MOCK | What happens to `/api` requests |
| --- | --- | --- |
| Home | `true` (default) | Nuxt server routes return mock data |
| Work (dev) | `false` | devProxy forwards to Flask at :5000 |
| Work (prod) | N/A | Flask serves static dist + handles /api directly |

## The Bridge: API Contracts

The `docs/api-contracts/` directory is the shared language between frontend and backend. Each YAML file defines one resource's endpoints — paths, methods, query params, response shapes, and examples.

**Data schema workflow:**

1. **At work**: See real data from Elasticsearch, note the schema and example values
2. **At home**: Provide schema to Claude → generates TypeScript types + mock server routes + contract YAML
3. **At work**: Pull from GitHub, Flask implements endpoints matching the same contracts

## Target Directory Structure

```text
skewnono_v3_nuxt/
├── docs/
│   ├── development-workflow.md        ← this file
│   └── api-contracts/
│       ├── README.md                  # How to read/write contracts
│       └── equipment.yaml             # First contract example
│
└── front-dev-home/
    ├── .env.example                   # Env var template
    ├── nuxt.config.ts                 # Conditional devProxy
    │
    ├── shared/types/                  # Nuxt 4 shared types (app + server)
    │   ├── api.ts                     # Generic response wrappers
    │   └── equipment.ts               # Equipment interface
    │
    ├── server/                        # Mock backend (Nuxt server routes)
    │   ├── api/equipment/
    │   │   ├── index.get.ts           # GET /api/equipment?fac_id=&vendor_nm=
    │   │   └── [id].get.ts            # GET /api/equipment/:id
    │   └── mock-data/
    │       └── equipment.ts           # Mock data arrays
    │
    └── app/
        └── composables/
            └── useEquipmentData.ts    # $fetch-based (no inline mock data)
```

## Implementation Steps

### Step 1: Shared Types (`shared/types/`)

Move the `Equipment` interface out of the composable into `shared/types/equipment.ts`. Nuxt 4 auto-imports from `shared/` into both `app/` and `server/` via the `#shared` alias.

```typescript
// shared/types/equipment.ts
export interface Equipment {
  fac_id: string
  eqp_id: string
  eqp_model_cd: string
  eqp_grp_id: string
  vendor_nm: 'HITACHI' | 'AMAT'
  eqp_ip: string
  fab_name: string
  updt_dt: string
  available: 'On' | 'Off'
  version: number
}
```

```typescript
// shared/types/api.ts
export interface ApiListResponse<T> {
  data: T[]
  total: number
}

export interface ApiDetailResponse<T> {
  data: T
}
```

### Step 2: Mock Server Routes (`server/`)

Move mock data from the composable to `server/mock-data/equipment.ts`. Create Nitro server routes that return this data.

```typescript
// server/api/equipment/index.get.ts
import { mockEquipmentData } from '~/server/mock-data/equipment'

export default defineEventHandler((event) => {
  const query = getQuery(event)
  let results = [...mockEquipmentData]

  if (query.fac_id && typeof query.fac_id === 'string') {
    results = results.filter(e => e.fac_id === query.fac_id)
  }
  if (query.vendor_nm && typeof query.vendor_nm === 'string') {
    results = results.filter(e => e.vendor_nm === query.vendor_nm)
  }

  return { data: results, total: results.length }
})
```

```typescript
// server/api/equipment/[id].get.ts
import { mockEquipmentData } from '~/server/mock-data/equipment'

export default defineEventHandler((event) => {
  const id = getRouterParam(event, 'id')
  const equipment = mockEquipmentData.find(e => e.eqp_id === id)

  if (!equipment) {
    throw createError({ statusCode: 404, statusMessage: `Equipment ${id} not found` })
  }
  return { data: equipment }
})
```

**Naming convention for future endpoints:**
- `server/api/{resource}/index.get.ts` — list with query filters
- `server/api/{resource}/[id].get.ts` — single item by ID
- `server/api/{resource}/index.post.ts` — create
- Response envelope: always `{ data: T | T[], total?: number }`

### Step 3: Conditional devProxy (`nuxt.config.ts`)

```typescript
const useMock = process.env.NUXT_USE_MOCK !== 'false'
const apiTarget = process.env.NUXT_API_TARGET || 'http://127.0.0.1:5000'
const portFromEnv = Number.parseInt(process.env.NUXT_PORT || '', 10)

export default defineNuxtConfig({
  // ...
  nitro: {
    devProxy: useMock
      ? undefined                    // no proxy → Nuxt server routes handle /api
      : {
          '/api': {
            target: apiTarget,
            changeOrigin: true,
            prependPath: true
          }
        }
  }
})
```

**Why this works**: When `devProxy` is `undefined`, Nitro processes `server/api/` routes normally. When the proxy is active, it intercepts `/api` requests before they reach server routes.

### Step 4: Rewrite Composable

```typescript
// app/composables/useEquipmentData.ts
import type { Equipment } from '#shared/types/equipment'
import type { ApiListResponse, ApiDetailResponse } from '#shared/types/api'

export const useEquipmentData = () => {
  const fetchEquipmentList = () =>
    $fetch<ApiListResponse<Equipment>>('/api/equipment')

  const fetchEquipmentByFacility = (facId: string) =>
    $fetch<ApiListResponse<Equipment>>('/api/equipment', { query: { fac_id: facId } })

  const fetchEquipmentByVendor = (vendor: string) =>
    $fetch<ApiListResponse<Equipment>>('/api/equipment', { query: { vendor_nm: vendor } })

  const fetchEquipmentById = (eqpId: string) =>
    $fetch<ApiDetailResponse<Equipment>>(`/api/equipment/${eqpId}`)

  return { fetchEquipmentList, fetchEquipmentByFacility, fetchEquipmentByVendor, fetchEquipmentById }
}
```

Same function signatures — no page changes needed.

### Step 5: Cached reads with `useAsyncData`

Use Nuxt's built-in `useAsyncData(key, fn)` for cached, deduplicated fetches. Wrap the API call in a tiny composable that pins the cache key, so every consumer reuses the same fetch.

```typescript
// app/composables/useEquipmentList.ts
export const useEquipmentList = () => {
  const { fetchEquipmentList } = useEquipmentData()
  return useAsyncData('equipment-list', fetchEquipmentList, {
    default: () => ({ data: [], total: 0 })
  })
}
```

Pages and components call the composable and derive views with `computed`:

```typescript
const { data, pending, error } = await useEquipmentList()
const onlineCount = computed(() => data.value.data.filter(e => e.available === 'On').length)
```

When you need filtered subsets, fetch the full list once and filter in `computed` — do not create a second `useAsyncData` with a different key for the same endpoint. Multiple keys = multiple network requests.

TanStack Query (Vue Query) is **not** used in this project. Adopt it only if a future feature needs TTL (`staleTime`), background refetch on focus, polling, mutations with optimistic updates, or key-prefix invalidation.

### Step 6: Environment Files

```bash
# .env.example (commit to git)
NUXT_USE_MOCK=true
NUXT_API_TARGET=http://127.0.0.1:5000
NUXT_PORT=3100
```

- **Home**: No `.env` needed. Defaults = mock mode.
- **Work**: Create `.env` with `NUXT_USE_MOCK=false`

### Step 7: Update generate-mock Skill

Rewrite `.claude/skills/generate-mock/SKILL.md` to generate:
- `shared/types/{resource}.ts` (interface)
- `server/mock-data/{resource}.ts` (mock data array)
- `server/api/{resource}/index.get.ts` (list route)
- `server/api/{resource}/[id].get.ts` (detail route)
- `docs/api-contracts/{resource}.yaml` (contract)

## Production Build (Phase 3)

```bash
cd front-dev-home && npm run generate
# Output: .output/public/ (static HTML + JS + CSS)
```

Transfer the built `public/` folder to work. Flask serves it:

```python
# Simplified Flask pattern
@app.route('/_nuxt/<path:filename>')
def nuxt_assets(filename):
    return send_from_directory(os.path.join(DIST_DIR, '_nuxt'), filename)

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    file_path = os.path.join(DIST_DIR, path)
    if os.path.isfile(file_path):
        return send_from_directory(DIST_DIR, path)
    return send_from_directory(DIST_DIR, 'index.html')  # SPA fallback
```

API blueprints handle `/api/*` routes against Elasticsearch and Redis.

## Verification Checklist

- [ ] `npm run dev` (no .env) → `http://localhost:3100/api/equipment` returns mock JSON
- [ ] `npm run typecheck` passes (shared types resolve in both app/ and server/)
- [ ] Pages load equipment data from server routes
- [ ] At work: `NUXT_USE_MOCK=false` + Flask running → same pages load real data
- [ ] `npm run generate` produces static build that Flask can serve
