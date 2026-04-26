# DESIGN.md — SKEWNONO 디자인 시스템

> 본 문서는 SKEWNONO(스큐노노) 프런트엔드의 시각 언어를 정의합니다.
> 새로운 컴포넌트·페이지를 추가할 때 이 문서를 단일 기준으로 삼아 일관성을 유지합니다.
> 토큰 식별자는 Tailwind/NuxtUI 클래스와 일치하도록 영문을 유지하며, 설명은 한국어로 작성합니다.

토큰의 원본 정의는 다음 두 파일에 있으며, 본 문서가 두 파일과 어긋날 경우 코드를 따릅니다.

| 항목 | 위치 |
| --- | --- |
| Tailwind / NuxtUI 테마 | `front-dev-home/app/assets/css/main.css` |
| NuxtUI 색상 매핑 | `front-dev-home/app/app.config.ts` |
| 시각 검증용 정적 미리보기 | `preview.html`, `preview-dark.html` |

---

## 1. 디자인 원칙 (Principles)

1. **차분함 우선 (Calm-first).** 메트롤로지 데이터를 다루는 도구이므로 색·그림자·애니메이션은 최소한으로 사용합니다.
2. **중성 캔버스 + 크림슨 트림 (Neutral canvas, crimson trim).** Zinc 계열 회색을 기본으로 깔고, 활성 상태에만 크림슨 강조를 더합니다. 크림슨은 *절대* 채움 색으로 쓰지 않습니다.
3. **읽기 위한 표 (Tables that read well).** 표는 등폭 숫자, 1px 보더, 호버 강조만 사용해 데이터를 가립니다.
4. **오프라인 가능 (Offline-capable).** 폰트·아이콘·미리보기 모두 외부 CDN 없이 동작해야 합니다 (Phase 1 원칙).
5. **이중 언어 (Bilingual UI).** UI 라벨은 한국어, 토큰·식별자·코드 식별자는 영어를 유지합니다.

---

## 2. 브랜드 (Brand)

| 항목 | 값 | 비고 |
| --- | --- | --- |
| 제품명 | SKEWNONO (스큐노노) | `nuxt.config.ts` 의 `app.head.title` |
| 로고 | `app/components/AppLogo.vue` | 워드마크에 크림슨 슬래시 포함 |
| 파비콘 테마 컬러 | `#f0eee9` | `meta[name=theme-color]` |
| 액센트 컬러 | `#c8321f` (라이트), `#e0553f` (다크) | 파비콘 슬래시와 동일 |

---

## 3. 색상 (Color)

### 3.1 NuxtUI 매핑

`app.config.ts` 에서 NuxtUI 의 `primary`, `neutral` 모두 **`zinc`** 으로 지정합니다.
즉, `UButton color="primary"` 와 `color="neutral"` 은 동일한 회색 계열로 렌더되며, 강조는 색이 아닌 *대비*로 표현합니다.

### 3.2 Zinc 스케일 (Tailwind 기본)

| 토큰 | HEX | 주 용도 |
| --- | --- | --- |
| `zinc-50` | `#FAFAFA` | 표 행 호버 (라이트) |
| `zinc-100` | `#F4F4F5` | 보조 표면 |
| `zinc-200` | `#E4E4E7` | 보더, 디바이더 |
| `zinc-300` | `#D4D4D8` | 비활성 보더 |
| `zinc-400` | `#A1A1AA` | placeholder, 보조 텍스트 |
| `zinc-500` | `#71717A` | 보조 텍스트 |
| `zinc-600` | `#52525B` | 본문(라이트), 비활성 라벨 |
| `zinc-700` | `#3F3F46` | 다크 보더 |
| `zinc-800` | `#27272A` | 다크 표면 보더 / 호버 |
| `zinc-900` | `#18181B` | 표면(다크), 활성 버튼 배경 |
| `zinc-950` | `#09090B` | 캔버스(다크) |

### 3.3 시맨틱 토큰 (`--sk-*`)

테마에 따라 자동 전환되며, `:root` (라이트)와 `.dark` (다크)에서 정의됩니다.

| 토큰 | 라이트 | 다크 | 용도 |
| --- | --- | --- | --- |
| `--sk-canvas` | `#ececef` | `#09090b` | `body` 배경 |
| `--sk-surface` | `#ffffff` | `#18181b` | 카드·헤더 배경 |
| `--sk-border` | `#e4e4e7` | `#27272a` | 기본 보더 |
| `--sk-on-bg` | `#d9f5e8` | `#052e16` | "On" 상태 알약 배경 |
| `--sk-on-fg` | `#0f5132` | `#bbf7d0` | "On" 상태 알약 글자 |
| `--sk-off-bg` | `#f1f1f4` | `#27272a` | "Off" 상태 알약 배경 |
| `--sk-off-fg` | `#52525b` | `#d4d4d8` | "Off" 상태 알약 글자 |
| `--sk-accent` | `#c8321f` | `#e0553f` | 크림슨 강조 (트림 전용) |
| `--sk-accent-border` | `rgba(200,50,31,0.22)` | `rgba(224,85,63,0.28)` | 카드 강조 보더 |
| `--sk-accent-tint` | `rgba(200,50,31,0.08)` | `rgba(224,85,63,0.12)` | 카드 내부 미세 틴트 |

**크림슨 사용 규칙 (필독)**

- 크림슨은 다음 세 가지 형태로만 등장합니다.
  1. `.sk-nav-accent` — 활성 네비 알약의 2px 하단 언더라인
  2. `.sk-fab-active` — 선택된 FAB 행의 2px 좌측 엣지
  3. `.dashboard-surface` — 카드 1px 보더 + 내부 8% 틴트
- 절대 금지: 크림슨 채움 버튼, 크림슨 텍스트 본문, 큰 면적의 크림슨 배경.

### 3.4 상태 색 (Status)

NuxtUI 는 success/warning/error/info 색을 자체 키로 노출하지 않으므로, 상태 표현은 다음 토큰을 우선 사용합니다.

| 의미 | 토큰 / 클래스 | 비고 |
| --- | --- | --- |
| On / 활성 / 정상 | `.sk-pill-on` 또는 `--sk-on-*` | 초록 계열, 알약 형태 |
| Off / 비활성 | `.sk-pill-off` 또는 `--sk-off-*` | 회색 계열, 알약 형태 |
| Filtered / 강조 | `--sk-accent` 트림 | 절대 채움으로 쓰지 않음 |
| Loading | `i-lucide-loader-circle` + `animate-spin` | 색상 변경 없음 |
| Error 텍스트 | `text-rose-600 dark:text-rose-400` | 메시지 라인에서만 사용 |

---

## 4. 타이포그래피 (Typography)

### 4.1 패밀리

| 변수 | 값 | 용도 |
| --- | --- | --- |
| `--font-sans` | `Public Sans, Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, Segoe UI, sans-serif` | 본문 / UI |
| `--font-korean` | `Noto Sans KR, Apple SD Gothic Neo, Malgun Gothic, Segoe UI, sans-serif` | 한국어 강제 시 |
| `--font-mono` | `ui-monospace, Cascadia Code, Segoe UI Mono, SFMono-Regular, Menlo, Consolas, monospace` | 표의 숫자·코드 |

폰트는 `@fontsource/*` 에서 woff2 파일만 추출해 `front-dev-home/public/fonts/` 에 셀프호스팅합니다. CDN/구글폰트에 접속하지 않습니다.

### 4.2 웨이트

| 웨이트 | 사용처 |
| --- | --- |
| 400 | 본문, 표 셀 |
| 500 | 부제, 네비 라벨, 버튼 |
| 600 | 섹션 제목, 강조 텍스트, 알약 |
| 700 | 페이지 제목 (`<h1>`), 큰 숫자 |

### 4.3 스케일 (Tailwind 기본 사용)

| 클래스 | 크기 | 줄높이 | 권장 용도 |
| --- | --- | --- | --- |
| `text-xs` | 12px | 16px | 메타데이터, 알약, 보조 라벨 |
| `text-sm` | 14px | 20px | 표 셀, 입력 필드, 보조 본문 |
| `text-base` | 16px | 24px | 본문 기본값 |
| `text-lg` | 18px | 28px | 카드 제목 |
| `text-xl` | 20px | 28px | 섹션 제목 |
| `text-2xl` | 24px | 32px | 페이지 부제 |
| `text-3xl` | 30px | 36px | 페이지 제목 |

**규칙**

- 표 안의 숫자·ID 컬럼은 `font-mono tabular-nums` 를 사용합니다.
- 한국어 라벨은 띄어쓰기를 그대로 두되, `whitespace-nowrap` 을 헤더 셀에 적용합니다.
- 페이지 제목은 한국어, 그 위 빵부스러기는 영어(`CD-SEM`, `HV-SEM`)를 사용하는 패턴이 정착되어 있습니다.

---

## 5. 간격 (Spacing)

Tailwind 의 기본 스페이싱 스케일(4px 단위)을 사용합니다. 자주 등장하는 사용 패턴은 다음과 같습니다.

| 단위 | 값 | 사용 패턴 |
| --- | --- | --- |
| `gap-1` / `p-1` | 4px | 알약 그룹의 좁은 간격 |
| `gap-2` / `p-2` | 8px | 입력 필드 안쪽, 버튼 그룹 |
| `gap-3` / `p-3` | 12px | 카드 헤더, 필터 바 컨트롤 사이 |
| `p-4` | 16px | 카드 기본 패딩 |
| `gap-6` | 24px | 카드 간 수직 간격 |
| `py-2.5` | 10px | 버튼 수직 패딩 |

**레이아웃**

- 콘텐츠 최대 폭은 `max-w-7xl mx-auto` (1280px) 를 표준으로 사용합니다.
- 사이드바가 있는 페이지는 `flex` + `min-w-0` 을 본문에 적용해 가로 스크롤을 방지합니다.
- 카드 간 수직 간격은 `space-y-6` 입니다.

---

## 6. 모서리·테두리·그림자 (Radius, Border, Shadow)

### 6.1 라운드

| 클래스 | 값 | 용도 |
| --- | --- | --- |
| `rounded` | 4px | 표 셀, 미세 알림 |
| `rounded-lg` | 8px | 버튼, 입력, 보조 컨트롤 |
| `rounded-2xl` | 16px | 카드 (기본) |
| `rounded-3xl` | 24px | 큰 대시보드 표면 |
| `rounded-full` | 9999px | 알약, 네비 토글 버튼 |

### 6.2 보더

- 기본 보더: `border border-(--sk-border)` — `--sk-border` 변수를 통해 라이트/다크 자동 전환.
- 강조 카드 보더: `.dashboard-surface` 클래스 — 1px 크림슨 보더 + 내부 미세 틴트.
- 버튼/입력 보더는 NuxtUI 기본값을 따르고, 직접 색을 지정하지 않습니다.

### 6.3 그림자

전반적으로 **그림자 없음** 또는 `0 1px 0 rgba(9,9,11,0.03)` 수준의 매우 얕은 라인만 사용합니다. 다이얼로그·드롭다운 등 NuxtUI 가 직접 관리하는 그림자는 NuxtUI 의 기본값을 사용합니다.

| 토큰 (커스텀) | 값 | 용도 |
| --- | --- | --- |
| header shadow | `0 1px 0 rgba(9,9,11,0.03)` | 헤더 / 카드 하단 미세 라인 |
| `.dashboard-surface` (라이트) | `0 1px 0 rgba(9,9,11,0.03), inset 0 0 0 1px var(--sk-accent-tint)` | 강조 카드 |
| `.dashboard-surface` (다크) | `0 1px 0 rgba(0,0,0,0.35), inset 0 0 0 1px var(--sk-accent-tint)` | 강조 카드 (다크) |
| `.sk-nav-accent` | `inset 0 -2px 0 0 var(--sk-accent)` | 활성 네비 언더라인 |
| `.sk-fab-active` | `inset 2px 0 0 0 var(--sk-accent), 0 1px 2px 0 rgba(0,0,0,0.05)` | 선택된 FAB 행 |

---

## 7. 컴포넌트 컨벤션 (Components)

### 7.1 버튼 (UButton)

| 상황 | 권장 사용 |
| --- | --- |
| 기본 (1차/2차 구분 없음) | `color="neutral" variant="solid"` |
| 부수적 동작 (정보, 설정, 다크모드 토글) | `color="neutral" variant="ghost"` |
| 파괴적 동작 (현재까지 없음) | 별도 등장 시 `text-rose-600` 텍스트 + 명시적 확인 다이얼로그 |
| 아이콘 전용 | `aria-label` 필수, `icon` prop 사용 |

- 모든 버튼은 `lucide` 아이콘을 사용합니다 (`icon="i-lucide-*"`).
- 한국어 라벨은 명사형보다 동사형을 우선합니다 (예: `다운로드` 대신 `CSV 다운로드`).
- 비활성화 시에도 `cursor-not-allowed` 를 명시해 사용자에게 시각적 피드백을 줍니다.

### 7.2 카드 (UCard)

- 일반 컨텐츠 그룹은 NuxtUI 기본 `UCard` 를 그대로 사용합니다.
- 대시보드 톤으로 보여야 하는 표·통계 카드는 외곽에 `class="dashboard-surface"` 를 적용해 크림슨 보더 + 내부 틴트를 입힙니다.
- 카드 헤더는 다음 패턴을 따릅니다.

```vue
<template #header>
  <div class="flex items-center justify-between gap-3">
    <h2 class="text-lg font-semibold">디바이스 목록</h2>
    <UBadge color="neutral" variant="subtle">{{ filteredCount }}건</UBadge>
  </div>
</template>
```

### 7.3 배지 / 알약 (UBadge / `.sk-pill-*`)

| 변종 | 클래스 | 용도 |
| --- | --- | --- |
| 카운트 배지 | `<UBadge color="neutral" variant="subtle">` | 표 행 수, 필터 개수 |
| On 상태 알약 | `<span class="sk-pill-on">` | 정상 가동 |
| Off 상태 알약 | `<span class="sk-pill-off">` | 비가동, 점검 |

알약은 12px (`text-xs`) + `font-weight: 600` + 9999px 라운드를 고정 사용합니다.

### 7.4 입력·셀렉트

- 검색 입력: `<UInput icon="i-lucide-search" placeholder="검색" />`
- 셀렉트: NuxtUI `<USelectMenu>` 기본값 사용. 옵션 라벨 한국어, value 영어.
- 다중 선택 필터(카테고리·Lot·Tech 등)는 칩 버튼 패턴을 사용합니다 — `device-statistics.vue` 참고.

### 7.5 표 (UTable)

| 항목 | 컨벤션 |
| --- | --- |
| 헤더 | `sticky top-0 bg-(--sk-surface)` 로 스크롤 시 고정 |
| 정렬 표시 | `i-lucide-arrow-up-narrow-wide` / `arrow-down-wide-narrow` / `arrow-up-down` |
| 숫자 컬럼 | `font-mono tabular-nums text-right` |
| ID 컬럼 | `font-mono` |
| 호버 | `hover:bg-zinc-50 dark:hover:bg-zinc-800/50` |
| 빈 상태 | `:empty` 슬롯에 `text-zinc-500` 메시지 |
| 페이지네이션 | 카드 푸터에 `이전 / 페이지 N/M / 다음` 레이아웃 |

### 7.6 필터 바 / 통계 바

- 필터 바와 통계 바는 카드 형태(`dashboard-surface`)로 표시하고, 내부를 `flex flex-wrap gap-3` 로 배치합니다.
- 통계 카드 한 줄에 여러 지표가 들어갈 때는 셀 사이를 `divide-x divide-(--sk-border)` 로 구분합니다 (border 가 아닌 divide 를 사용해 양 끝 보더 중복을 피함).

### 7.7 네비게이션

| 영역 | 컴포넌트 | 패턴 |
| --- | --- | --- |
| 상단 카테고리 | `nav/AppHeader.vue` | 알약 토글 버튼, 활성 시 `bg-zinc-900 text-zinc-100 + sk-nav-accent` |
| 도구 종류 탭 | `nav/ToolTypeTabs.vue` | 가로 스크롤 가능한 알약 그룹, 카운트 배지 포함 |
| FAB 사이드바 | `nav/FabSidebar.vue` | 좁히기/펼치기 가능, 즐겨찾기 별, 활성 행에 `.sk-fab-active` |
| 기능 탭 | `nav/FeatureTabs.vue` | 도구 종류별 4–7개 기능 탭, 비활성 시 `aria-disabled` |

라벨은 한국어, 키보드 접근성을 위해 `aria-pressed`, `aria-disabled` 를 반드시 사용합니다.

---

## 8. 다크 모드 (Dark mode)

- NuxtUI 의 `colorMode` 시스템을 사용합니다 (`UColorModeButton` 헤더에 배치).
- 모든 색은 `--sk-*` 변수를 거쳐 자동 전환합니다. 컴포넌트에서 직접 `dark:` 변종을 사용하는 경우는 보더(`dark:border-zinc-800`)·호버 (`dark:hover:bg-zinc-800/50`)에 한정합니다.
- 새 컴포넌트를 만들 때, *다크 변종을 잊지 않는 가장 간단한 방법*은 `--sk-*` 변수를 직접 쓰는 것입니다. `bg-(--sk-surface)`, `border-(--sk-border)`, `text-(--sk-on-fg)` 형태.
- 다크 모드에서 크림슨은 `#e0553f` 로 약간 더 따뜻하게 떠올라 가독성을 보존합니다.

---

## 9. 아이콘 (Iconography)

- 단일 아이콘 세트: **Lucide** (`@iconify-json/lucide`).
- 사용 형태: `icon="i-lucide-<name>"` (NuxtUI / UIcon 모두 동일).
- 자주 등장하는 아이콘:

| 아이콘 | 용도 |
| --- | --- |
| `i-lucide-search` | 검색 입력 |
| `i-lucide-rotate-ccw` | 초기화 |
| `i-lucide-download` | 내보내기 (CSV 등) |
| `i-lucide-info` | 정보 페이지 |
| `i-lucide-settings` | 설정 페이지 |
| `i-lucide-loader-circle` + `animate-spin` | 로딩 |
| `i-lucide-star` / `star-off` | 즐겨찾기 |
| `i-lucide-arrow-up-narrow-wide` / `arrow-down-wide-narrow` / `arrow-up-down` | 정렬 상태 |
| `i-lucide-construction` | 준비중 페이지 |

`@iconify-json/simple-icons` 도 의존성에 있지만 브랜드 로고 등 매우 한정된 경우에만 사용합니다.

---

## 10. 모션 (Motion)

- 기본 트랜지션: `transition-colors duration-200` — 호버·활성 토글에 사용합니다.
- 길이가 긴 전환(슬라이드, 페이드)은 사용하지 않습니다. 데이터 도구의 응답성을 해치기 때문입니다.
- 로딩 애니메이션은 `animate-spin` 외에 사용하지 않습니다. 스켈레톤·셔머 등은 도입하지 않은 상태입니다.
- `prefers-reduced-motion` 을 도입하면 `animate-spin` 을 멈춰야 하지만, 스피너만 영향받으므로 현재는 별도 처리하지 않습니다.

---

## 11. 보이스 & 톤 (Voice & Tone)

| 상황 | 톤 | 예시 |
| --- | --- | --- |
| 페이지 제목 | 명사형, 한국어 | `디바이스 통계` |
| 버튼 라벨 | 동사 또는 명사+동사, 한국어 | `CSV 다운로드`, `초기화` |
| 빈 상태 메시지 | `~없습니다.` 종결 | `조건에 맞는 디바이스가 없습니다.` |
| 에러 메시지 | `~못했습니다.` 종결 | `데이터를 불러오지 못했습니다.` |
| 도움말 / 본문 | `~입니다.`, `~합니다.` 종결 | `현재 선택된 Fab 입니다.` |
| 토큰·키·식별자 | 영어 | `prod_catg_cd`, `lot_cd` |

---

## 12. 접근성 (Accessibility)

- 색만으로 상태를 전달하지 않습니다. On/Off 알약은 글자 라벨과 함께 사용합니다.
- 모든 토글 버튼은 `aria-pressed` 를 사용해 활성 상태를 노출합니다.
- 비활성 컨트롤은 `disabled` 와 `aria-disabled="true"` 를 같이 부여합니다.
- 아이콘 전용 버튼은 반드시 `aria-label` 을 가집니다.
- 명도 대비: 본문 텍스트는 `zinc-900`(라이트)·`zinc-100`(다크)을 기본으로 하여 WCAG AA 를 충족합니다. 보조 텍스트는 `zinc-500` 이상을 유지합니다.
- 테이블의 정렬 상태는 아이콘 + `aria-sort` 로 함께 전달합니다.

---

## 13. 토큰이 어디에 정의되어 있는가 (Source of Truth)

| 영역 | 파일 | 비고 |
| --- | --- | --- |
| 색·폰트·`@theme` 변수 | `front-dev-home/app/assets/css/main.css` | Tailwind v4 `@theme static` 블록 |
| `--sk-*` 시맨틱 변수 | `front-dev-home/app/assets/css/main.css` (`:root` / `.dark`) | 라이트/다크 페어로 정의 |
| NuxtUI 색 매핑 | `front-dev-home/app/app.config.ts` | `primary: 'zinc'`, `neutral: 'zinc'` |
| 폰트 파일 | `front-dev-home/public/fonts/` | woff2, latin / korean 서브셋 |
| 아이콘 패키지 | `front-dev-home/package.json` | `@iconify-json/lucide` |
| 시각 미리보기 | `preview.html`, `preview-dark.html` | 본 문서와 함께 갱신 |

본 문서를 수정하면 위 파일들과 미리보기 HTML 도 같이 점검합니다. 코드와 문서가 어긋나면 *코드가 정답*이며, 본 문서를 코드에 맞춰 갱신합니다.

---

## 14. 변경 이력 (Changelog)

- 2026-04-26: 초기 작성. 기존 `main.css`, `app.config.ts`, 컴포넌트에서 추출한 디자인 토큰을 정리하고 미리보기 HTML 을 함께 추가했습니다.
