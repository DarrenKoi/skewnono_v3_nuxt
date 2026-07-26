# SKEWNONO Progress Bento Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:subagent-driven-development (recommended) or
> superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** `f03c2d9`에 고정한 완료 작업과 저장소 지표를 기존 15장 SKEWNONO
Bento 진행 보고에 반영합니다.

**Architecture:** 자체 포함 HTML의 런타임은 건드리지 않고
`#bento-doc`의 `bento/slides` JSON만 수정합니다. 기존 슬라이드 ID, element ID,
`morph` 전환, 테마, chart와 count-up 효과를 보존하면서 숫자·상태·발표자 노트를
함께 갱신합니다.

**Tech Stack:** Bento Slides v1 JSON, self-contained HTML, `jq`, Git, root
Markdown tooling

## Global Constraints

- 보고 기준은 `f03c2d9` (`2026-07-26 14:30:08 +0900`, 995 commits)입니다.
- `f03c2d9` 이후 완료된 커밋과 작업 중 변경은 보고 내용에 넣지 않습니다.
- `docs/progress_report/SKEWNONO_Progress.bento.html`에서는 `#bento-doc` JSON만
  수정합니다.
- 15장 구성, 슬라이드·element ID, `morph`, 흰색 테마, 파란색 강조색, 글꼴을
  유지합니다.
- office 어댑터 구현 수와 사내 실데이터 검증 수를 같은 분모로 합치지
  않습니다.
- 실제 사내 28개 대표 계약 실행과 첫 클라우드 배포를 완료로 표현하지
  않습니다.
- JSON의 모든 `<`는 `\u003c`로 이스케이프합니다.
- 사용자 또는 다른 작업의 frontend 변경은 stage하거나 commit하지 않습니다.

---

### Task 1: 15장 Bento 진행 보고 갱신

**Files:**

- Modify: `docs/progress_report/SKEWNONO_Progress.bento.html`

**Interfaces:**

- Consumes: `#bento-doc`의 `format: "bento/slides"`, 15개 기존 slide ID,
  기존 element ID와 `transition`
- Produces: 같은 구조를 유지하면서 `f03c2d9` 지표와 완료 성과를 담은
  파싱 가능한 Bento Slides v1 JSON

- [ ] **Step 1: 편집 전 문서 불변식을 확인합니다.**

Run:

```bash
sed -n \
  '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/p' \
  docs/progress_report/SKEWNONO_Progress.bento.html \
  | sed '1d;$d' \
  | jq -e '
      .format == "bento/slides"
      and .version == 1
      and .size == {"width":1280,"height":720}
      and (.slides | length) == 15
      and ([.slides[].id] | unique | length) == 15
    '
```

Expected: `true`

- [ ] **Step 2: 표지·규모 지표를 갱신합니다.**

`s1`, `s2`, `s5`에서 아래 값을 사용합니다.

| 위치 | 이전 | 변경 |
| --- | --- | --- |
| `s1` 커밋 | 808 | 995 |
| `s1` 백엔드 기능 | 20 | 22 |
| `s1` 사내 상태 | 6 연결 완료 | 2 실데이터 검증 완료 |
| `s2` 화면 | 53 | 54 |
| `s2` 컴포넌트 | 179 | 186 |
| `s2` API | 75 | 74 |
| `s2` 자동 테스트 | 1,036 | 2,106 |

`s5`의 규모 설명도 `화면 54개, 컴포넌트 186개, 자동 테스트 2,106개`로
맞춥니다. 해당 슬라이드의 notes에서도 이전 숫자를 제거합니다.

- [ ] **Step 3: Phase 3와 provider 교체 설명을 갱신합니다.**

`s7`의 Phase 3 status를 `패키징 준비 완료 · 첫 배포 대기`로 바꾸고, 본문에
번들 allowlist, office/cloud preflight, manifest, 배포 runbook이 완료됐지만
첫 클라우드 배포는 남았다고 적습니다.

`s8`에는 다음 완료 내용을 반영합니다.

- `office_example.py` 템플릿 30개
- 구현된 템플릿만 복사하는 `setup_office_adapters.py`
- `SYNCED`/`STALE`/`EDITED`를 구분하는 `sync_office_adapters.py`
- route와 response contract는 환경 전환과 무관하게 고정

기존 파일 복사 방식과 `contracts.py` 설명은 유지합니다.

- [ ] **Step 4: 개발 속도와 화면 구성을 갱신합니다.**

`s10`의 bar chart series는 plain number 배열
`[8, 48, 117, 151, 673]`을 사용합니다. tooltip과 chart element는
그대로 둡니다.

`s11`의 공통 화면 설명에 `CD-SEM Mag/Pixel 가이드`를 추가하고 전체 화면 수를
54개로 표현합니다.

- [ ] **Step 5: office 현황 슬라이드를 구현/실검증 분리 구조로 바꿉니다.**

`s12` 제목은 `사내 연결 현황 — 구현과 실검증 분리`로 사용합니다.

상단 bar의 분모는 30개 template로만 고정합니다.

- 구현 완료: 18개, 파란색 또는 초록색 segment, 너비 653px
- stub: 12개, 회색 segment, 너비 435px
- 22개 runtime registry 기능 중 ledger의 live-office 검증은 2개라는 문장을
  bar 아래 별도 callout으로 둡니다.

하단 table은 다음 네 행을 사용합니다.

| 구분 | 완료 내용 | 남은 gate |
| --- | --- | --- |
| 계약 baseline | 대표 28개 shape·28/28 로컬 정리 | 사내 office 실행 |
| 이미지 전달 | MSR image async job, FTP→MinIO, TIFF 원본 | 사내 운영 부하 확인 |
| Hardware | BM/PM·BSM·SCE·Sharpness adapter | 탭별 office 검증 |
| 배포 기반 | preflight·manifest·runbook·bundle | 첫 cloud deploy |

notes에는 `18 implemented`와 `2 live-office verified`가 서로 다른 상태라는
설명을 포함합니다.

- [ ] **Step 6: 7월 성과·다음 목표·최종 요약을 갱신합니다.**

`s13`의 7월 항목은 아래 완료 작업을 압축해 반영합니다.

- Skewvoir FDC sparkline matrix, keyboard navigation, multi-select,
  point identity colors
- CD-SEM Mag/Pixel 계산·추천·시각화 가이드
- backend 1,328개와 frontend 778개 테스트, provider-honest contract gate,
  CI
- cloud bundle과 preflight

`s14`의 MCP와 장비 매뉴얼 RAG 목표는 유지하고, 구현된 provider/chat 골격 위에
이어지는 다음 단계라고 설명합니다.

`s15`는 다음 세 문장으로 정리합니다.

1. `화면 54개·백엔드 기능 22개·테스트 2,106개 — 제품 골격과 회귀 방어선을
   함께 세웠습니다.`
2. `office 템플릿 30개 중 18개 구현, 실데이터 검증 2개 — 구현과 현장 검증을
   분리해 이어갑니다.`
3. `배포 패키징을 준비했고, 다음은 첫 cloud deploy와 MCP·매뉴얼 RAG입니다.`

notes도 같은 수치와 상태로 갱신합니다.

- [ ] **Step 7: 문서 JSON을 파싱하고 내용 불변식을 확인합니다.**

Run:

```bash
sed -n \
  '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/p' \
  docs/progress_report/SKEWNONO_Progress.bento.html \
  | sed '1d;$d' \
  | jq -e '
      .format == "bento/slides"
      and .version == 1
      and .size == {"width":1280,"height":720}
      and (.slides | length) == 15
      and ([.slides[].id] | unique | length) == 15
      and ([.slides[] | select((.notes // "") == "")] | length) == 0
      and (
        .slides[]
        | select(.id == "s10")
        | .elements[]
        | select(.id == "chart")
        | .option.series[0].data
      ) == [8,48,117,151,673]
    '
```

Expected: `true`

- [ ] **Step 8: Bento 런타임과 구조가 바뀌지 않았는지 확인합니다.**

Run:

```bash
diff \
  <(git show HEAD:docs/progress_report/SKEWNONO_Progress.bento.html \
    | sed '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/d') \
  <(sed '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/d' \
    docs/progress_report/SKEWNONO_Progress.bento.html)
```

Expected: no output

Run:

```bash
diff \
  <(git show HEAD:docs/progress_report/SKEWNONO_Progress.bento.html \
    | sed -n \
      '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/p' \
    | sed '1d;$d' \
    | jq -r '.slides[] | .id, (.elements[].id)') \
  <(sed -n \
      '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/p' \
      docs/progress_report/SKEWNONO_Progress.bento.html \
    | sed '1d;$d' \
    | jq -r '.slides[] | .id, (.elements[].id)')
```

Expected: no output

- [ ] **Step 9: stale 수치와 Bento guardrail을 확인합니다.**

Run:

```bash
sed -n \
  '/<script type="application\/bento+json" id="bento-doc">/,/<\/script>/p' \
  docs/progress_report/SKEWNONO_Progress.bento.html \
  | rg '808|1036|1,036|486|53개|179개|75 API|6개 · 사내 데이터 연결 완료'
```

Expected: exit 1 with no output

Run:

```bash
git diff --check
npm run lint:md
```

Expected: both commands pass

- [ ] **Step 10: 의도한 파일만 commit합니다.**

Run:

```bash
git add \
  docs/progress_report/SKEWNONO_Progress.bento.html \
  docs/superpowers/plans/2026-07-26-skewnono-progress-bento-refresh.md
git diff --cached --check
git diff --cached --stat
git commit -m "docs(progress): refresh the SKEWNONO Bento report"
```

Expected: only the Bento HTML and this implementation plan are committed.

### Task 2: 검증된 report commit을 `origin/main`에 publish

**Files:**

- Publish: the commits containing
  `docs/superpowers/specs/2026-07-26-skewnono-progress-bento-refresh-design.md`,
  `docs/superpowers/plans/2026-07-26-skewnono-progress-bento-refresh.md`, and
  `docs/progress_report/SKEWNONO_Progress.bento.html`

**Interfaces:**

- Consumes: validated local commits on `main`
- Produces: the same commits as ancestors of `origin/main`, with unrelated
  working-tree files unstaged

- [ ] **Step 1: push 범위를 확인합니다.**

Run:

```bash
git status -sb
git log --oneline origin/main..HEAD
```

Expected: report commits are visible. If unrelated local commits are also
ahead, use a clean temporary worktree from `origin/main` and cherry-pick only
the report commits before pushing.

- [ ] **Step 2: main을 push합니다.**

Run:

```bash
git push origin main
```

Expected: the remote accepts the update.

- [ ] **Step 3: remote ancestry와 작업 트리를 확인합니다.**

Run:

```bash
git fetch origin main
git merge-base --is-ancestor HEAD origin/main
git status -sb
```

Expected: the ancestry command exits 0. Any unrelated user changes remain
uncommitted and unstaged.
