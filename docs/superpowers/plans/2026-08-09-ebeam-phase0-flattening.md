# E-Beam Phase 0 (평탄화 + tool_type 도메인 확장) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `ebeam/` 을 평탄화하고 tool_type 도메인을 4계열로 확장해, 이후 AMAT feature 추가가 기계적인 반복이 되도록 기반을 정리합니다.

**Architecture:** 백엔드 `ebeam/hitachi/<feature>` 와 `ebeam/cdsem/device_statistics` 를 `ebeam/<feature>` 로 평탄화합니다. `_tool_specs.py` 를 `ebeam/` 로 승격해 슬러그·tool_type·벤더·어댑터 폴더의 단일 레지스트리로 만들고, 프론트 `utils/toolType.ts` 를 그 거울로 삼아 흩어진 union 5벌을 흡수합니다. 미지 tool_type 이 조용히 "전체"로 떨어지던 경로를 400 으로 바꿉니다.

**Tech Stack:** Flask (Blueprint 자동 발견), pytest, Nuxt 4 SPA, `node --test`

## Global Constraints

- 설계 근거는 `docs/superpowers/specs/2026-08-09-ebeam-vendor-onboarding-design.md` 입니다. 충돌하면 spec 이 우선합니다.
- **AMAT tool_type 은 하이픈이 없습니다**: `veritysem`, `provision`. Hitachi 만 이중 표기(`cdsem` ↔ `cd-sem`)를 유지합니다.
- **활동 로그 슬러그는 append-only** 입니다. `activity.ts` 의 `FEATURE_LABELS` 에서 기존 `verity_sem` 항목을 **삭제하지 않습니다**.
- **이 Plan 은 `providers/<family>/` 하위 폴더를 만들지 않습니다.** 그것은 Phase 1(feature × 계열)의 일이며, AMAT 오피스 소스가 확인된 뒤에 시작합니다.
- pytest 는 반드시 저장소 루트에서 `.venv/bin/python -m pytest` 로 실행합니다. `-m` 이 루트를 `sys.path` 에 넣습니다.
- 프론트 명령은 `front-dev-home/` 에서 실행합니다.
- 커밋은 **직접 편집한 파일 경로만** 명시적으로 지정합니다. `git add -A`, `git add .`, `git commit -a` 는 금지입니다.
- 이 작업은 다중 파일이므로 **worktree 에서 수행**합니다.

## 사전 준비 (Task 0)

- [ ] **Step 1: worktree 생성**

```bash
git worktree add ../skewnono-ebeam-phase0 -b work/ebeam-phase0
cd ../skewnono-ebeam-phase0
```

- [ ] **Step 2: 프론트 의존성 연결**

```bash
ln -s ../../skewnono_v3_nuxt/front-dev-home/node_modules front-dev-home/node_modules
```

- [ ] **Step 3: 기준선 측정**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -3
```

기대: `NNNN passed, MM skipped` 형태. **이 두 숫자의 합을 적어 둡니다.**
worktree 에는 gitignored `office.py` 가 없으므로 메인 체크아웃과 skipped
수가 다릅니다. 이후 모든 검증은 **passed + skipped 합계**로 비교합니다.

```bash
cd front-dev-home && npm test 2>&1 | tail -3 && npm run typecheck 2>&1 | tail -3 && cd ..
```

기대: 프론트 테스트 통과, typecheck 0 errors. 숫자를 적어 둡니다.

---

## File Structure

| 파일 | 책임 |
| --- | --- |
| `back_dev_home/ebeam/_tool_specs.py` | 슬러그·tool_type·벤더·어댑터 폴더의 단일 레지스트리 (이동 + 확장) |
| `back_dev_home/ebeam/<feature>/` | 9개 feature + device_statistics (이동) |
| `back_dev_home/meas_hist/routes.py` | 미지 tool_type 을 400 으로 거절 |
| `back_dev_home/meas_hist/providers/mock.py` | AMAT 제외를 명시적으로 표현 |
| `front-dev-home/app/utils/toolType.ts` | 프론트 tool_type 단일 레지스트리 (승격) |
| `front-dev-home/app/composables/*.ts` | 지역 union 제거, 레지스트리 참조 |
| `back_dev_home/ebeam/__fixtures__/tool_type_cases.json` | 프론트·백 분류기 일치 계약 fixture |

---

### Task 1: 백엔드 평탄화 (순수 이동)

동작 변경이 없어야 합니다. URL, 응답, 환경변수 이름 모두 그대로입니다.

**Files:**

- Move: `back_dev_home/ebeam/hitachi/{fail_issue,hardware,lateral_recipe,live_alarm,pm_planning,recipe_search,recipe_tat,skew,storage}/` → `back_dev_home/ebeam/`
- Move: `back_dev_home/ebeam/hitachi/{_analytics.py,_analytics_routes.py,_office_meas_hist.py,_office_search.py,_tool_specs.py}` → `back_dev_home/ebeam/`
- Move: `back_dev_home/ebeam/hitachi/tests/` → `back_dev_home/ebeam/tests/`
- Move: `back_dev_home/ebeam/cdsem/device_statistics/` → `back_dev_home/ebeam/device_statistics/`
- Delete: `back_dev_home/ebeam/hitachi/__init__.py`, `back_dev_home/ebeam/cdsem/__init__.py`
- Modify: `back_dev_home.ebeam.hitachi` / `back_dev_home.ebeam.cdsem` 를 참조하는 모든 파일

**Interfaces:**

- Consumes: 없음 (첫 작업)
- Produces: `back_dev_home.ebeam.<feature>` 및 `back_dev_home.ebeam._tool_specs` 임포트 경로. 이후 모든 Task 가 이 경로를 씁니다.

- [ ] **Step 1: 이동 전 참조 수를 기록**

```bash
grep -rn "ebeam\.hitachi\|ebeam\.cdsem" --include="*.py" back_dev_home/ scripts/ tests/ | wc -l
```

숫자를 적어 둡니다. Step 4 이후 0 이 되어야 합니다.

- [ ] **Step 2: 디렉터리 이동**

`git mv` 는 추적된 파일만 옮기므로, gitignored `office.py` 가 남지 않도록
디렉터리 통째로 옮깁니다. worktree 에는 `office.py` 가 없지만, 같은 절차가
메인 체크아웃에서도 안전하도록 이렇게 씁니다.

```bash
cd back_dev_home/ebeam
for d in fail_issue hardware lateral_recipe live_alarm pm_planning \
         recipe_search recipe_tat skew storage tests; do
  git mv "hitachi/$d" "$d"
done
for f in _analytics.py _analytics_routes.py _office_meas_hist.py \
         _office_search.py _tool_specs.py; do
  git mv "hitachi/$f" "$f"
done
git mv cdsem/device_statistics device_statistics
git rm hitachi/__init__.py cdsem/__init__.py
rmdir hitachi cdsem 2>/dev/null || true
cd ../..
```

- [ ] **Step 3: 임포트 경로 치환**

```bash
grep -rl "ebeam\.hitachi\|ebeam\.cdsem" --include="*.py" back_dev_home/ scripts/ tests/ \
  | xargs sed -i '' -e 's/back_dev_home\.ebeam\.hitachi\./back_dev_home.ebeam./g' \
                     -e 's/back_dev_home\.ebeam\.cdsem\./back_dev_home.ebeam./g' \
                     -e 's/from back_dev_home\.ebeam\.hitachi import/from back_dev_home.ebeam import/g'
```

- [ ] **Step 4: 잔여 참조가 0인지 확인**

```bash
grep -rn "ebeam\.hitachi\|ebeam\.cdsem" --include="*.py" back_dev_home/ scripts/ tests/
```

기대: 출력 없음.

- [ ] **Step 5: 상대 임포트가 여전히 맞는지 확인**

`storage/routes.py` 는 `from .._tool_specs import VALID_TOOL_SLUGS` 를 씁니다.
이동 전 `..` 는 `ebeam.hitachi`, 이동 후 `..` 는 `ebeam` 이며 `_tool_specs.py`
도 함께 `ebeam/` 로 올라왔으므로 그대로 해석됩니다. 확인만 합니다.

```bash
grep -rn "from \.\._tool_specs\|from \.\._office\|from \.\._analytics" --include="*.py" back_dev_home/ebeam/
.venv/bin/python -c "import back_dev_home; back_dev_home.create_app()" && echo BOOT_OK
```

기대: 마지막 줄에 `BOOT_OK`.

- [ ] **Step 6: 전체 테스트**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -3
```

기대: Task 0 Step 3 에서 적어 둔 **passed + skipped 합계와 동일**.

- [ ] **Step 7: 커밋**

```bash
git add back_dev_home/ebeam back_dev_home/meas_hist back_dev_home/msr_file \
        back_dev_home/_runtime back_dev_home/_spa back_dev_home/_auth \
        back_dev_home/_logging scripts tests
git commit -m "refactor(ebeam): 벤더 중간 폴더를 없애고 feature 를 평탄화한다

office_registry 가 feature_dir.name 하나로 feature 를 식별하므로 중간 폴더는
provider 해석에 아무 역할도 하지 않는다. 라우트에도 벤더가 등장하지 않는다.
반면 meas_hist·msr_file·device_statistics 가 ebeam/hitachi 내부를 import 하고
있어 이름이 사실과 다른 상태였다. 동작 변경은 없다."
```

---

### Task 2: `_tool_specs.py` 를 4계열 레지스트리로 확장

**Files:**

- Modify: `back_dev_home/ebeam/_tool_specs.py`
- Test: `back_dev_home/ebeam/tests/test_tool_specs.py`

**Interfaces:**

- Consumes: Task 1 의 `back_dev_home.ebeam._tool_specs` 경로
- Produces:
  - `ToolSlug = Literal["cdsem", "hvsem", "veritysem", "provision"]`
  - `ToolType = Literal["cd-sem", "hv-sem", "veritysem", "provision"]`
  - `Vendor = Literal["HITACHI", "AMAT"]`
  - `SLUG_TO_TOOL_TYPE: dict[ToolSlug, ToolType]`
  - `TOOL_TYPE_TO_VENDOR: dict[ToolType, Vendor]`
  - `SLUG_TO_ADAPTER: dict[ToolSlug, str]`
  - `SEM_TOOL_TYPES: frozenset[ToolType]` — `{"cd-sem", "hv-sem"}`
  - `model_to_tool_type(eqp_model_cd: str) -> ToolType | None`
  - `resolve_tool_type_from_slug(tool_slug: str) -> ToolType | None`

- [ ] **Step 1: 실패하는 테스트를 작성**

`back_dev_home/ebeam/tests/test_tool_specs.py` 끝에 추가합니다.

```python
from back_dev_home.ebeam._tool_specs import (
    SEM_TOOL_TYPES,
    SLUG_TO_ADAPTER,
    SLUG_TO_TOOL_TYPE,
    TOOL_TYPE_TO_VENDOR,
    model_to_tool_type,
    resolve_tool_type_from_slug,
)


def test_amat_families_resolve_to_their_own_tool_types():
    assert model_to_tool_type("VERITYSEM_4") == "veritysem"
    assert model_to_tool_type("VERITY_SEM_5") == "veritysem"
    assert model_to_tool_type("PROVISION_10") == "provision"


def test_amat_tool_types_carry_no_hyphen():
    """제품명이 한 단어이고, 슬러그·라우트와 같은 문자열을 쓰기 위함."""
    assert SLUG_TO_TOOL_TYPE["veritysem"] == "veritysem"
    assert SLUG_TO_TOOL_TYPE["provision"] == "provision"


def test_unknown_model_is_still_unclassified():
    assert model_to_tool_type("ZZ9000") is None


def test_vendor_is_a_label_not_the_adapter_axis():
    """벤더는 2개, 어댑터 폴더는 3개 — 같은 것으로 다루지 않는다."""
    assert TOOL_TYPE_TO_VENDOR["cd-sem"] == "HITACHI"
    assert TOOL_TYPE_TO_VENDOR["veritysem"] == "AMAT"
    assert TOOL_TYPE_TO_VENDOR["provision"] == "AMAT"
    assert set(SLUG_TO_ADAPTER.values()) == {"hitachi", "veritysem", "provision"}


def test_hitachi_is_the_only_adapter_covering_two_families():
    assert SLUG_TO_ADAPTER["cdsem"] == "hitachi"
    assert SLUG_TO_ADAPTER["hvsem"] == "hitachi"
    assert SLUG_TO_ADAPTER["veritysem"] == "veritysem"
    assert SLUG_TO_ADAPTER["provision"] == "provision"


def test_sem_tool_types_excludes_amat():
    """CD/HV 전용 화면이 무엇을 담는지 명시적으로 이름 붙인 집합."""
    assert SEM_TOOL_TYPES == frozenset({"cd-sem", "hv-sem"})


def test_amat_slugs_resolve_from_slug():
    assert resolve_tool_type_from_slug("veritysem") == "veritysem"
    assert resolve_tool_type_from_slug("PROVISION") == "provision"
    assert resolve_tool_type_from_slug("nope") is None
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/tests/test_tool_specs.py -q 2>&1 | tail -5
```

기대: FAIL — `ImportError: cannot import name 'SEM_TOOL_TYPES'`.

- [ ] **Step 3: 레지스트리를 확장**

`back_dev_home/ebeam/_tool_specs.py` 에서 타입과 매핑을 다음으로 바꿉니다.

```python
ToolSlug = Literal["cdsem", "hvsem", "veritysem", "provision"]
ToolType = Literal["cd-sem", "hv-sem", "veritysem", "provision"]
Vendor = Literal["HITACHI", "AMAT"]
```

`TOOL_SPECS` 에 두 계열을 추가합니다. 아래 값은 전부 mock 용 재료이며
분류기가 아닙니다 (모듈 docstring 참조).

```python
TOOL_SPECS: dict[ToolSlug, ToolSpec] = {
    "cdsem": {
        "eqp_models": ["CG6300", "CG6320", "CG6340", "CG6360", "CG6380", "GT2000", "GT2000S"],
        "eqp_prefixes": ["ECXDX", "ECDX", "HCDX"],
    },
    "hvsem": {
        "eqp_models": ["TP3000", "TP3500", "TP4000", "TP4500"],
        "eqp_prefixes": ["PCD", "MCD", "ACD", "VCD"],
    },
    # OFFICE-VERIFY: AMAT 모델 코드는 sem_list mock 의 AMAT_MODELS 와 같은
    # 추정값입니다. 사무실에서 v3_df_sem_list 의 eqp_model_cd 를 확인해
    # 실제 코드로 교체하고 `office 확인 <날짜>` 로 표기를 올립니다.
    "veritysem": {
        "eqp_models": ["VERITYSEM_4", "VERITYSEM_5"],
        "eqp_prefixes": ["VCD", "MCD"],
    },
    "provision": {
        "eqp_models": ["PROVISION_10", "PROVISION_20"],
        "eqp_prefixes": ["ACD", "MCD"],
    },
}

SLUG_TO_TOOL_TYPE: dict[ToolSlug, ToolType] = {
    "cdsem": "cd-sem",
    "hvsem": "hv-sem",
    "veritysem": "veritysem",
    "provision": "provision",
}

TOOL_TYPE_TO_VENDOR: dict[ToolType, Vendor] = {
    "cd-sem": "HITACHI",
    "hv-sem": "HITACHI",
    "veritysem": "AMAT",
    "provision": "AMAT",
}

# providers/<이 이름>/ 하위 폴더. 기본은 항등 매핑이고, cdsem/hvsem 만
# "hitachi" 로 합쳐지는 예외입니다 — 두 계열이 마침 겹치는 부분이 많아 하나의
# 어댑터로 처리할 수 있었을 뿐이며, 규칙이 아니라 우연입니다. 갈라지면
# "cdsem"/"hvsem" 으로 쪼갭니다.
SLUG_TO_ADAPTER: dict[ToolSlug, str] = {
    "cdsem": "hitachi",
    "hvsem": "hitachi",
    "veritysem": "veritysem",
    "provision": "provision",
}

# CD/HV 전용 화면이 담는 범위. `model_to_tool_type() is not None` 으로 이
# 집합을 흉내내던 코드가 있었는데, 분류기가 AMAT 을 해석하기 시작하면 그
# 표현은 조용히 의미가 바뀝니다. 의도를 이름으로 고정합니다.
SEM_TOOL_TYPES: frozenset[ToolType] = frozenset({"cd-sem", "hv-sem"})

_TOOL_TYPE_BY_PREFIX: tuple[tuple[str, ToolType], ...] = (
    ("CG", "cd-sem"),
    ("GT", "cd-sem"),
    ("TP", "hv-sem"),
    ("VERITYSEM", "veritysem"),
    ("VERITY_SEM", "veritysem"),
    ("PROVISION", "provision"),
)
```

`model_to_tool_type()` 의 docstring 을 바꿉니다. 기존 docstring 은 None 이
AMAT 을 뜻한다고 적혀 있는데 더 이상 사실이 아닙니다.

```python
def model_to_tool_type(eqp_model_cd: str) -> ToolType | None:
    """Classify a model code, or None when it belongs to no known family.

    Mirrors `classifyToolType()` in front-dev-home/app/utils/toolType.ts;
    the two are pinned together by __fixtures__/tool_type_cases.json.

    None now means genuinely unknown. It used to double as "an AMAT tool",
    and callers that wanted "CD/HV only" wrote `is not None` — those must
    say `in SEM_TOOL_TYPES` instead.

    Normalizes case and surrounding whitespace first — parquet/Redis text
    cells carry both, and an unclassified tool vanishes from the UI without
    raising, so a stray space must not silently delete a row.
    """
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/tests/test_tool_specs.py -q 2>&1 | tail -3
```

기대: PASS.

- [ ] **Step 5: 전체 테스트로 파급을 확인**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -20
```

`model_to_tool_type` 이 AMAT 을 해석하기 시작했으므로 `is not None` 에
의존하던 곳이 여기서 드러납니다. 실패가 나오면 **Task 3 에서 고칩니다.**
실패 목록을 적어 둡니다.

- [ ] **Step 6: 커밋 (실패가 없을 때만)**

실패가 있으면 Task 3 을 끝낸 뒤 함께 커밋합니다.

```bash
git add back_dev_home/ebeam/_tool_specs.py back_dev_home/ebeam/tests/test_tool_specs.py
git commit -m "feat(ebeam): tool_type 레지스트리를 4계열로 확장한다

AMAT 두 계열을 model_to_tool_type 이 해석하게 하고, 벤더(2)와 어댑터 폴더(3)
를 별도 매핑으로 분리한다. None 이 AMAT 을 겸하던 의미를 없애는 대신 CD/HV
범위를 SEM_TOOL_TYPES 로 명시한다."
```

---

### Task 3: `is not None` 으로 CD/HV 를 흉내내던 곳을 명시화

**Files:**

- Modify: `back_dev_home/meas_hist/providers/mock.py:267-269`
- Test: `back_dev_home/meas_hist/tests/test_contract.py`

**Interfaces:**

- Consumes: Task 2 의 `SEM_TOOL_TYPES`, `model_to_tool_type`
- Produces: 없음 (기존 동작 유지)

meas_hist 는 AMAT 오피스 소스가 없습니다. 따라서 AMAT 장비를 측정 이력에
넣는 것은 **없는 데이터를 지어내는 것**입니다. 제외는 유지하되, 분류기의
반환값에 우연히 기대는 대신 의도를 코드에 적습니다.

- [ ] **Step 1: 실패하는 테스트를 작성**

`back_dev_home/meas_hist/tests/test_contract.py` 끝에 추가합니다.

```python
def test_meas_hist_fleet_excludes_amat_tools_deliberately():
    """AMAT 은 measurement 소스가 없으므로 mock 도 지어내지 않는다.

    분류기가 AMAT 을 해석하기 시작한 뒤에도 이 제외가 유지되어야 한다.
    """
    from back_dev_home.ebeam._tool_specs import model_to_tool_type
    from back_dev_home.meas_hist.providers.mock import _eligible_sem_rows

    tool_types = {model_to_tool_type(row["eqp_model_cd"]) for row in _eligible_sem_rows()}
    assert tool_types <= {"cd-sem", "hv-sem"}
    assert tool_types  # 비어 있으면 필터가 전부를 지운 것
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/meas_hist/tests/test_contract.py -q -k amat 2>&1 | tail -5
```

기대: FAIL — `veritysem` / `provision` 이 집합에 포함됨.

- [ ] **Step 3: 제외를 명시적으로 표현**

`back_dev_home/meas_hist/providers/mock.py` 의 임포트에 `SEM_TOOL_TYPES` 를
추가하고 `_eligible_sem_rows()` 를 바꿉니다.

```python
from back_dev_home.ebeam._tool_specs import SEM_TOOL_TYPES, ToolType, model_to_tool_type


@lru_cache(maxsize=1)
def _eligible_sem_rows() -> tuple[SemListRow, ...]:
    """CD-SEM / HV-SEM 장비만. AMAT 은 measurement 소스가 없다.

    예전에는 `model_to_tool_type(...) is not None` 이었다. 그때는 분류기가
    AMAT 에 None 을 돌려주어 결과가 같았지만, 그것은 의도가 아니라 우연이었다.
    분류기가 AMAT 을 해석하게 된 지금 그 표현은 없는 측정 이력을 지어낸다.
    """
    return tuple(
        row for row in get_sem_list()
        if model_to_tool_type(row["eqp_model_cd"]) in SEM_TOOL_TYPES
    )
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/meas_hist -q 2>&1 | tail -3
```

기대: PASS.

- [ ] **Step 5: Task 2 Step 5 의 나머지 실패를 처리**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -20
```

남은 실패가 있으면 각각 확인합니다. 판단 기준은 하나입니다 — **그 코드가
"CD/HV 만"을 의도했으면 `in SEM_TOOL_TYPES` 로, "분류 가능한 것 전부"를
의도했으면 `is not None` 을 유지**합니다. 고칠 때마다 이유를 주석에 남깁니다.

- [ ] **Step 6: 전체 테스트가 기준선과 같은지 확인**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -3
```

기대: Task 0 기준선 + 이 Task 들에서 추가한 테스트 수.

- [ ] **Step 7: 커밋**

```bash
git add back_dev_home/meas_hist back_dev_home/ebeam
git commit -m "fix(meas-hist): CD/HV 한정을 분류기의 None 대신 명시 집합으로 표현한다

model_to_tool_type 이 AMAT 을 해석하게 되면서 'is not None' 은 없는 AMAT
측정 이력을 지어내는 표현이 되었다. SEM_TOOL_TYPES 로 의도를 고정한다."
```

---

### Task 4: 미지 tool_type 을 400 으로 거절

지금은 `tool_type=veritysem` 이 `None` 이 되고, `None` 의 의미가 "필터 없음
= 전체"이므로 **필터를 걸었는데 전 장비가 반환**됩니다. 오류도 빈 결과도
아니어서 화면상 이상이 보이지 않습니다.

**Files:**

- Modify: `back_dev_home/meas_hist/routes.py:15-20,40-69`
- Test: `back_dev_home/meas_hist/tests/test_routes.py` (없으면 생성)

**Interfaces:**

- Consumes: Task 2 의 `SLUG_TO_TOOL_TYPE`
- Produces: `/api/meas-hist*` 가 미지 `tool_type` 에 400 반환

- [ ] **Step 1: 실패하는 테스트를 작성**

`back_dev_home/meas_hist/tests/test_routes.py` 를 만들고 다음을 씁니다.

```python
import pytest

from back_dev_home import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        c.set_cookie("LASTUSER", "local-dev")
        yield c


@pytest.mark.parametrize("path", [
    "/api/meas-hist",
    "/api/meas-hist/search",
    "/api/meas-hist/facets",
])
def test_unknown_tool_type_is_rejected_not_widened(client, path):
    """미지 값이 조용히 '전체'로 떨어지면 필터가 무시된 결과가 나온다."""
    response = client.get(f"{path}?tool_type=zz-sem")
    assert response.status_code == 400
    assert "tool_type" in response.get_json()["error"]


@pytest.mark.parametrize("path", [
    "/api/meas-hist",
    "/api/meas-hist/search",
    "/api/meas-hist/facets",
])
def test_absent_tool_type_still_means_everything(client, path):
    """미지정은 '전체'가 맞다. 파싱 실패와 구분되어야 한다."""
    assert client.get(path).status_code == 200


def test_known_tool_types_are_accepted(client):
    for value in ("cd-sem", "hv-sem"):
        assert client.get(f"/api/meas-hist?tool_type={value}").status_code == 200
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/meas_hist/tests/test_routes.py -q 2>&1 | tail -5
```

기대: FAIL — 400 대신 200.

- [ ] **Step 3: 라우트를 고침**

`back_dev_home/meas_hist/routes.py` 에서 `VALID_TOOL_TYPES` 하드코딩과
`_resolve_tool_type()` 을 다음으로 바꿉니다.

```python
from back_dev_home.ebeam._tool_specs import SLUG_TO_TOOL_TYPE

# 하드코딩하지 않습니다. 계열이 늘어나면 레지스트리만 고칩니다.
VALID_TOOL_TYPES: frozenset[str] = frozenset(SLUG_TO_TOOL_TYPE.values())


class _UnknownToolType(Exception):
    pass


def _resolve_tool_type() -> ToolType | None:
    """미지정이면 None(= 전체), 미지의 값이면 예외.

    둘을 같은 None 으로 뭉개면 'veritysem 으로 필터했는데 전 장비가 나오는'
    조용한 오답이 됩니다. 400 이 정답입니다.
    """
    raw = (request.args.get("tool_type") or "").strip().lower()
    if not raw:
        return None
    if raw not in VALID_TOOL_TYPES:
        raise _UnknownToolType(raw)
    return raw  # type: ignore[return-value]


@bp.errorhandler(_UnknownToolType)
def _reject_unknown_tool_type(exc: _UnknownToolType):
    return jsonify({
        "error": f"unknown tool_type {exc.args[0]!r}; "
                 f"expected one of {sorted(VALID_TOOL_TYPES)}"
    }), 400
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/meas_hist -q 2>&1 | tail -3
```

기대: PASS.

- [ ] **Step 5: 다른 라우트에도 같은 구멍이 있는지 확인**

```bash
grep -rn "else None" --include="routes.py" back_dev_home/ | grep -i "tool\|slug"
```

`VALID_TOOL_SLUGS` 를 쓰는 fleet 형 라우트들은 이미 400 을 냅니다
(`storage/routes.py:22`). 새로 발견되는 곳이 있으면 같은 방식으로 고치고,
없으면 그대로 둡니다.

- [ ] **Step 6: 커밋**

```bash
git add back_dev_home/meas_hist/routes.py back_dev_home/meas_hist/tests/test_routes.py
git commit -m "fix(meas-hist): 미지 tool_type 을 전체 조회로 넓히지 않고 400 으로 거절한다

파싱 실패와 미지정이 둘 다 None 이 되어, veritysem 으로 필터를 걸면 필터가
무시된 전 장비 결과가 조용히 돌아왔다. 유효 목록도 하드코딩 대신
_tool_specs 레지스트리에서 가져온다."
```

---

### Task 5: 프론트 tool_type 레지스트리 승격과 `veritysem` 표기

**Files:**

- Modify: `front-dev-home/app/utils/toolType.ts`
- Modify: `front-dev-home/app/utils/toolType.test.ts`
- Modify: `front-dev-home/app/stores/navigation.ts:5`

**Interfaces:**

- Consumes: 없음 (프론트 독립)
- Produces:
  - `TOOL_TYPES: readonly ToolType[]`
  - `ToolType = 'cd-sem' | 'hv-sem' | 'veritysem' | 'provision'`
  - `classifyToolType(eqpModelCd: string): ToolType | null`
  - `toolSlug(toolType: ToolType): string`
  - `SEM_TOOL_TYPES: readonly ToolType[]` — `['cd-sem', 'hv-sem']`

- [ ] **Step 1: 실패하는 테스트를 작성**

`front-dev-home/app/utils/toolType.test.ts` 의 첫 테스트를 바꾸고 아래를
추가합니다.

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyToolType, toolSlug, TOOL_TYPES, SEM_TOOL_TYPES } from './toolType.ts'

test('classifyToolType recognizes both VeritySEM prefixes case-insensitively', () => {
  for (const model of [
    'VERITYSEM_4',
    'VeritySEM_4',
    'veritysem_4',
    'VERITY_SEM_5',
    'Verity_SEM_5',
    'verity_sem_5'
  ]) {
    assert.equal(classifyToolType(model), 'veritysem', model)
  }
})

test('classifyToolType keeps an unrelated model unclassified', () => {
  assert.equal(classifyToolType('ZZ9000'), null)
})

test('AMAT tool types carry no hyphen', () => {
  assert.equal(classifyToolType('PROVISION_10'), 'provision')
  assert.ok(TOOL_TYPES.includes('veritysem'))
  assert.ok(!TOOL_TYPES.includes('verity-sem' as never))
})

test('toolSlug maps every tool type to its backend slug', () => {
  assert.equal(toolSlug('cd-sem'), 'cdsem')
  assert.equal(toolSlug('hv-sem'), 'hvsem')
  assert.equal(toolSlug('veritysem'), 'veritysem')
  assert.equal(toolSlug('provision'), 'provision')
})

test('SEM_TOOL_TYPES names the CD/HV-only scope explicitly', () => {
  assert.deepEqual([...SEM_TOOL_TYPES], ['cd-sem', 'hv-sem'])
})
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
cd front-dev-home && npm test 2>&1 | tail -10
```

기대: FAIL — `toolSlug` / `TOOL_TYPES` 미정의.

- [ ] **Step 3: `toolType.ts` 를 레지스트리로 승격**

파일 전체를 다음으로 바꿉니다. `ToolType` 을 여기서 정의하고
`stores/navigation.ts` 는 이것을 re-export 합니다 — 두 곳에서 각자 선언하면
다시 갈라집니다.

```ts
/**
 * 프론트의 tool_type 단일 원천.
 *
 * 백엔드 `back_dev_home/ebeam/_tool_specs.py` 의 거울이며, 두 분류기는
 * `__fixtures__/tool_type_cases.json` 계약 테스트로 묶여 있습니다.
 * 한쪽만 고치면 그 테스트가 깨집니다.
 *
 * utils 에 있는 이유: `pendingToolMatrix.ts` 가 런타임에 쓰는 순수 함수인데
 * `npm test` 는 번들러 없이 `node --test` 로 돌기 때문에 `~/composables/…`
 * 임포트는 해석되지 않습니다. 호출부는 Nuxt auto-import 로 그대로 씁니다.
 *
 * AMAT 계열(veritysem/provision)에는 하이픈이 없습니다. 제품명이 한 단어이고,
 * 슬러그·tool_type·라우트가 같은 문자열이면 매핑 테이블이 생기지 않습니다.
 * 이중 표기는 Hitachi 레거시(cdsem ↔ cd-sem)로만 남습니다.
 */
export const TOOL_TYPES = ['cd-sem', 'hv-sem', 'veritysem', 'provision'] as const

export type ToolType = (typeof TOOL_TYPES)[number]

/** CD/HV 전용 화면이 담는 범위. 'AMAT 이 아닌 것' 으로 흉내내지 않습니다. */
export const SEM_TOOL_TYPES = ['cd-sem', 'hv-sem'] as const satisfies readonly ToolType[]

const TOOL_SLUGS: Record<ToolType, string> = {
  'cd-sem': 'cdsem',
  'hv-sem': 'hvsem',
  veritysem: 'veritysem',
  provision: 'provision'
}

/** 백엔드 `/api/<tool_slug>/…` 에 들어가는 슬러그. */
export const toolSlug = (toolType: ToolType): string => TOOL_SLUGS[toolType]

export const classifyToolType = (eqpModelCd: string): ToolType | null => {
  const model = eqpModelCd.trim().toUpperCase()
  if (model.startsWith('CG') || model.startsWith('GT')) return 'cd-sem'
  if (model.startsWith('TP')) return 'hv-sem'
  if (model.startsWith('VERITYSEM') || model.startsWith('VERITY_SEM')) return 'veritysem'
  if (model.startsWith('PROVISION')) return 'provision'
  return null
}
```

- [ ] **Step 4: `stores/navigation.ts` 가 재선언하지 않도록 수정**

5번 줄의 지역 선언을 지우고 re-export 로 바꿉니다.

```ts
export type { ToolType } from '~/utils/toolType'
```

- [ ] **Step 5: 테스트와 타입 검사**

```bash
cd front-dev-home && npm test 2>&1 | tail -5 && npm run typecheck 2>&1 | tail -20
```

기대: 테스트 PASS. typecheck 는 `'verity-sem'` 을 쓰는 곳에서 **에러가
납니다** — 그것이 Task 6 의 작업 목록입니다. 에러 목록을 적어 둡니다.

- [ ] **Step 6: 커밋 (typecheck 에러는 Task 6 에서 해소)**

```bash
git add front-dev-home/app/utils/toolType.ts front-dev-home/app/utils/toolType.test.ts \
        front-dev-home/app/stores/navigation.ts
git commit -m "feat(front): tool_type 단일 레지스트리를 세우고 veritysem 표기를 확정한다

TOOL_TYPES/toolSlug/SEM_TOOL_TYPES 를 utils/toolType.ts 에 모으고
stores/navigation 은 re-export 만 한다. AMAT 계열은 하이픈 없이
veritysem/provision 을 쓴다."
```

---

### Task 6: 흩어진 union 5벌과 슬러그 매핑을 흡수

**Files:**

- Modify: `front-dev-home/app/composables/useMeasHistApi.ts:4`
- Modify: `front-dev-home/app/composables/useFailIssueApi.ts:3,219`
- Modify: `front-dev-home/app/composables/useRecipeSearchApi.ts:4`
- Modify: `front-dev-home/app/composables/useLateralRecipeApi.ts:4,41`
- Modify: Task 5 Step 5 의 typecheck 에러가 가리킨 나머지 파일
- Modify: `front-dev-home/app/pages/ebeam/verity-sem/` → `veritysem/` (2파일)
- Modify: `front-dev-home/app/components/nav/FeatureTabs.vue:40`, `nav/FabSidebar.vue:55`
- Modify: `front-dev-home/app/composables/useToolData.ts:14`
- Modify: `front-dev-home/app/pages/tool-roster.vue:308`
- Modify: `front-dev-home/app/utils/pendingToolMatrix.test.ts:41,75`
- Modify: `front-dev-home/app/utils/pageIdentity.test.ts:162`

**Interfaces:**

- Consumes: Task 5 의 `ToolType`, `toolSlug`, `TOOL_TYPES`
- Produces: 프론트 전역에서 tool_type 선언이 1곳

- [ ] **Step 1: 지역 union 을 alias 로 바꾸는 테스트를 먼저 확인**

이 Task 는 타입 수준 리팩터링이라 별도 테스트를 쓰지 않습니다. **검증
수단은 `npm run typecheck` 와 중복 선언 0** 입니다. 먼저 현재 개수를 셉니다.

```bash
cd front-dev-home && grep -rn "= 'cd-sem' | 'hv-sem'" app/ | wc -l
```

기대: 4 이상. 이 숫자가 0 이 되는 것이 완료 조건입니다.

- [ ] **Step 2: 각 composable 의 지역 union 을 레지스트리 alias 로 교체**

각 파일에서 아래 형태의 선언을 지우고,

```ts
export type MeasHistToolType = 'cd-sem' | 'hv-sem'
```

다음으로 바꿉니다. 이름은 유지해서 호출부 변경을 최소화합니다.

```ts
import type { ToolType } from '~/utils/toolType'

/** @deprecated 이름만 유지. 새 코드는 ToolType 을 직접 씁니다. */
export type MeasHistToolType = ToolType
```

`useFailIssueApi.ts`, `useRecipeSearchApi.ts`, `useLateralRecipeApi.ts` 도
같은 방식으로 각각 `FailIssueToolType`, `RecipeSearchToolType`,
`LateralRecipeToolType` 을 바꿉니다.

- [ ] **Step 3: composable 별 슬러그 매핑을 `toolSlug` 로 교체**

`useFailIssueApi.ts:219` 의

```ts
const toolSlug = (toolType: FailIssueToolType): 'cdsem' | 'hvsem' =>
```

와 `useLateralRecipeApi.ts:41` 의 `TOOL_TO_BACKEND_SLUG` 를 지우고,
`~/utils/toolType` 의 `toolSlug` 를 씁니다 (Nuxt auto-import 로 이름이
그대로 잡히므로 `useFailIssueApi.ts` 는 지역 정의만 지우면 됩니다).

- [ ] **Step 4: 라우트 폴더와 리터럴을 `veritysem` 으로**

```bash
cd front-dev-home
git mv app/pages/ebeam/verity-sem app/pages/ebeam/veritysem
grep -rl "verity-sem" app/ | xargs sed -i '' "s/verity-sem/veritysem/g"
grep -rn "verity-sem" app/
```

기대: 마지막 명령의 출력 없음.

- [ ] **Step 5: 타입 검사와 테스트**

```bash
cd front-dev-home && npm run typecheck 2>&1 | tail -20 && npm test 2>&1 | tail -5 && npm run lint 2>&1 | tail -5
```

기대: typecheck 0 errors, 테스트 PASS, lint 통과.

- [ ] **Step 6: 중복 선언이 0인지 확인**

```bash
cd front-dev-home && grep -rn "= 'cd-sem' | 'hv-sem'" app/ | wc -l
```

기대: `0`.

- [ ] **Step 7: 커밋**

```bash
git add front-dev-home/app
git commit -m "refactor(front): tool_type union 5벌과 슬러그 매핑을 레지스트리로 흡수한다

각 composable 이 'cd-sem' | 'hv-sem' 을 따로 선언하고 슬러그 매핑도 자기
것을 들고 있어, 계열이 늘 때 한 곳만 고치면 나머지가 조용히 어긋났다.
라우트 폴더도 veritysem 으로 맞춘다."
```

---

### Task 7: skewvoir 의 2계열 전제 삼항을 제거

`ws.toolType === 'cd-sem' ? 'hv-sem' : 'cd-sem'` 은 tool_type 이 정확히
2개라는 전제입니다. `veritysem` 이 오면 `'cd-sem'` 으로 떨어져 **엉뚱한
계열의 비교 데이터**를 나란히 렌더합니다.

**Files:**

- Modify: `front-dev-home/app/composables/useSkewvoirAnalysis.ts:75`
- Modify: `front-dev-home/app/utils/toolType.ts` (`otherSemFamily` 추가)
- Test: `front-dev-home/app/utils/toolType.test.ts`

**Interfaces:**

- Consumes: Task 5 의 `ToolType`, `SEM_TOOL_TYPES`
- Produces: `otherSemFamily(toolType: ToolType): ToolType | null`

- [ ] **Step 1: 실패하는 테스트를 작성**

`front-dev-home/app/utils/toolType.test.ts` 에 추가합니다.

```ts
test('otherSemFamily pairs CD-SEM and HV-SEM', () => {
  assert.equal(otherSemFamily('cd-sem'), 'hv-sem')
  assert.equal(otherSemFamily('hv-sem'), 'cd-sem')
})

test('otherSemFamily has no answer outside the SEM pair', () => {
  // 삼항으로 짜면 veritysem 이 조용히 cd-sem 이 되어 엉뚱한 계열을 붙인다.
  assert.equal(otherSemFamily('veritysem'), null)
  assert.equal(otherSemFamily('provision'), null)
})
```

임포트 줄에 `otherSemFamily` 를 추가합니다.

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
cd front-dev-home && npm test 2>&1 | tail -10
```

기대: FAIL — `otherSemFamily is not defined`.

- [ ] **Step 3: `otherSemFamily` 를 구현**

`front-dev-home/app/utils/toolType.ts` 끝에 추가합니다.

```ts
/**
 * CD-SEM ↔ HV-SEM 의 짝. 그 밖에는 짝이 없으므로 null 입니다.
 *
 * skewvoir 의 "다른 SEM 계열 이력도 함께 조회" 는 두 계열만 있을 때 성립하는
 * 개념입니다. 삼항(`x === 'cd-sem' ? 'hv-sem' : 'cd-sem'`)으로 쓰면 AMAT 계열이
 * 조용히 'cd-sem' 이 되어 엉뚱한 계열의 데이터를 나란히 그립니다.
 */
export const otherSemFamily = (toolType: ToolType): ToolType | null => {
  if (toolType === 'cd-sem') return 'hv-sem'
  if (toolType === 'hv-sem') return 'cd-sem'
  return null
}
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

```bash
cd front-dev-home && npm test 2>&1 | tail -5
```

기대: PASS.

- [ ] **Step 5: `useSkewvoirAnalysis.ts` 가 쓰도록 수정**

75번 줄의 삼항을 바꾸고, 짝이 없을 때 두 번째 요청을 아예 하지 않도록
합니다.

```ts
// 짝이 없는 계열(AMAT)은 '다른 SEM 계열' 개념 자체가 성립하지 않으므로
// 두 번째 이력을 조회하지 않습니다. 예전 삼항은 veritysem 을 cd-sem 으로
// 떨어뜨려 엉뚱한 계열을 비교 대상으로 붙였습니다.
const otherToolType = computed<ToolType | null>(() => otherSemFamily(ws.toolType))
```

`useAsyncData` 호출과 `otherHistWanted` 트리거를 `otherToolType.value` 가
`null` 이면 실행하지 않도록 감쌉니다. 캐시 키는
`skewvoir-meas-hist:${otherToolType.value ?? 'none'}` 로 두어 키 충돌을
막습니다.

- [ ] **Step 6: 타입 검사와 테스트**

```bash
cd front-dev-home && npm run typecheck 2>&1 | tail -10 && npm test 2>&1 | tail -5
```

기대: 0 errors, PASS.

- [ ] **Step 7: 커밋**

```bash
git add front-dev-home/app/utils/toolType.ts front-dev-home/app/utils/toolType.test.ts \
        front-dev-home/app/composables/useSkewvoirAnalysis.ts
git commit -m "fix(skewvoir): '다른 SEM 계열' 을 삼항 대신 명시적 짝으로 구한다

tool_type 이 2개라는 전제가 삼항에 박혀 있어, AMAT 계열이 들어오면 조용히
cd-sem 으로 떨어져 엉뚱한 계열의 이력을 비교 대상으로 붙였다. 짝이 없으면
두 번째 조회를 하지 않는다."
```

---

### Task 8: 활동 로그 슬러그 (append-only)

**Files:**

- Modify: `back_dev_home/_logging/feature_map.py`
- Modify: `back_dev_home/_logging/tests/test_feature_map.py:182,240`
- Modify: `front-dev-home/app/utils/activity.ts:55-97`
- Modify: `front-dev-home/app/utils/pageIdentity.test.ts:162`

**Interfaces:**

- Consumes: Task 6 의 `/ebeam/veritysem/…` 경로
- Produces: 없음

- [ ] **Step 1: 실패하는 테스트를 작성**

`back_dev_home/_logging/tests/test_feature_map.py` 의 기존 두 케이스에서
경로를 바꾸고, 옛 경로가 여전히 해석되는지도 확인합니다.

```python
def test_veritysem_pages_use_the_hyphenless_slug():
    assert page_to_feature("/ebeam/veritysem/M14") == "tool_inventory"
    assert page_to_feature("/ebeam/veritysem/M14/unmapped-page") == "veritysem"


def test_the_retired_hyphenated_path_still_resolves():
    """이미 기록된 행을 위해 옛 경로도 계속 해석되어야 한다(append-only)."""
    assert page_to_feature("/ebeam/verity-sem/M14/unmapped-page") == "verity_sem"
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/_logging -q 2>&1 | tail -5
```

기대: FAIL.

- [ ] **Step 3: `feature_map.py` 를 확인하고 필요한 경우만 수정**

슬러그는 URL 세그먼트에서 파생되므로 대개 코드 변경 없이 통과합니다.
`_PAGE_RULES` 는 tool 세그먼트 뒤의 페이지 이름만 보므로 영향이 없습니다.
실패가 남으면 fallback 분기에서 하이픈 처리를 확인합니다.

- [ ] **Step 4: `activity.ts` 에 라벨을 추가 (기존 항목 유지)**

`FEATURE_LABELS` 에 알파벳 순서로 `veritysem` 을 추가합니다. **`verity_sem`
은 지우지 않습니다** — OpenSearch 에 이미 쌓인 행이 30일 창을 지날 때까지
필요하고, 주석이 "PERMANENT" 라고 못박아 두었습니다.

```ts
  tool_inventory: '장비 상태',
  verity_sem: 'VeritySEM',
  veritysem: 'VeritySEM'
```

주석 블록의 슬러그 목록에도 `veritysem` 을 추가하고, `verity_sem` 이 이제
**은퇴한 경로에서만 나온다**는 사실을 한 줄 적습니다.

- [ ] **Step 5: 테스트**

```bash
.venv/bin/python -m pytest back_dev_home/_logging -q 2>&1 | tail -3
cd front-dev-home && npm test 2>&1 | tail -5 && cd ..
```

기대: 양쪽 PASS.

- [ ] **Step 6: 커밋**

```bash
git add back_dev_home/_logging front-dev-home/app/utils/activity.ts \
        front-dev-home/app/utils/pageIdentity.test.ts
git commit -m "feat(activity): veritysem 슬러그를 추가하고 옛 verity_sem 라벨을 유지한다

usage_events 슬러그는 append-only 이므로 이미 기록된 verity_sem 을 rename
하지 않고 새 슬러그를 더한다. 라벨을 지우면 30일 창 안의 기존 행이
'Verity Sem' 으로 렌더된다."
```

---

### Task 9: 프론트·백 분류기 일치를 계약 테스트로 고정

두 분류기가 갈라진 채로 "별도 추적"으로 남아 있던 부채를 여기서 갚습니다.
같은 fixture 를 양쪽이 읽으면 한쪽만 고칠 수 없습니다.

**Files:**

- Create: `back_dev_home/ebeam/__fixtures__/tool_type_cases.json`
- Create: `back_dev_home/ebeam/tests/test_tool_type_parity.py`
- Create: `front-dev-home/app/utils/toolTypeParity.test.ts`

**Interfaces:**

- Consumes: Task 2 의 `model_to_tool_type`, Task 5 의 `classifyToolType`
- Produces: 없음

- [ ] **Step 1: fixture 를 작성**

`back_dev_home/ebeam/__fixtures__/tool_type_cases.json`:

```json
{
  "_comment": "프론트 classifyToolType 과 백엔드 model_to_tool_type 이 함께 읽는 유일한 계약. 한쪽만 고치면 양쪽 테스트 중 하나가 깨진다.",
  "cases": [
    { "model": "CG6300", "expected": "cd-sem" },
    { "model": "CG6380", "expected": "cd-sem" },
    { "model": "GT2000", "expected": "cd-sem" },
    { "model": "GT2000S", "expected": "cd-sem" },
    { "model": "TP4000", "expected": "hv-sem" },
    { "model": "TP3500", "expected": "hv-sem" },
    { "model": "VERITYSEM_4", "expected": "veritysem" },
    { "model": "VeritySEM_5", "expected": "veritysem" },
    { "model": "VERITY_SEM_5", "expected": "veritysem" },
    { "model": "verity_sem_4", "expected": "veritysem" },
    { "model": "PROVISION_10", "expected": "provision" },
    { "model": "provision_20", "expected": "provision" },
    { "model": "  CG6300  ", "expected": "cd-sem" },
    { "model": "ZZ9000", "expected": null },
    { "model": "", "expected": null }
  ]
}
```

- [ ] **Step 2: 백엔드 계약 테스트를 작성**

`back_dev_home/ebeam/tests/test_tool_type_parity.py`:

```python
import json
from pathlib import Path

import pytest

from back_dev_home.ebeam._tool_specs import model_to_tool_type


_FIXTURE = Path(__file__).resolve().parent.parent / "__fixtures__" / "tool_type_cases.json"


def _cases():
    return json.loads(_FIXTURE.read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", _cases(), ids=lambda c: c["model"] or "<empty>")
def test_backend_classifier_matches_the_shared_fixture(case):
    assert model_to_tool_type(case["model"]) == case["expected"]
```

- [ ] **Step 3: 백엔드 테스트가 통과하는지 확인**

```bash
.venv/bin/python -m pytest back_dev_home/ebeam/tests/test_tool_type_parity.py -q 2>&1 | tail -3
```

기대: PASS (Task 2 에서 이미 구현했으므로).

- [ ] **Step 4: 프론트 계약 테스트를 작성**

`front-dev-home/app/utils/toolTypeParity.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { classifyToolType } from './toolType.ts'

// 백엔드와 같은 파일을 읽습니다. 경로가 깨지면 테스트가 죽는 편이,
// 두 분류기가 조용히 갈라지는 것보다 낫습니다.
const FIXTURE = new URL(
  '../../../back_dev_home/ebeam/__fixtures__/tool_type_cases.json',
  import.meta.url
)

const { cases } = JSON.parse(readFileSync(FIXTURE, 'utf-8')) as {
  cases: { model: string, expected: string | null }[]
}

test('frontend classifier matches the shared fixture', () => {
  assert.ok(cases.length > 0, 'fixture is empty — path likely wrong')
  for (const { model, expected } of cases) {
    assert.equal(classifyToolType(model), expected, model)
  }
})
```

- [ ] **Step 5: 프론트 테스트가 통과하는지 확인**

```bash
cd front-dev-home && npm test 2>&1 | tail -5
```

기대: PASS.

- [ ] **Step 6: 계약이 실제로 물려 있는지 확인**

`toolType.ts` 의 `'PROVISION'` 을 일부러 `'PROVISN'` 으로 바꾸고 프론트
테스트를 돌립니다. FAIL 이 나야 합니다. 확인 후 되돌립니다.

```bash
cd front-dev-home && npm test 2>&1 | grep -c "fail" && git checkout app/utils/toolType.ts
```

- [ ] **Step 7: `toolType.ts` 의 자백 주석을 삭제**

기존 주석의 *"this DISAGREES with the backend … Reconciling the two is real
work, tracked separately"* 문장이 Task 5 에서 이미 사라졌는지 확인하고,
남아 있으면 지웁니다. 부채가 갚혔으므로 그 문장은 이제 거짓입니다.

- [ ] **Step 8: 커밋**

```bash
git add back_dev_home/ebeam/__fixtures__/tool_type_cases.json \
        back_dev_home/ebeam/tests/test_tool_type_parity.py \
        front-dev-home/app/utils/toolTypeParity.test.ts \
        front-dev-home/app/utils/toolType.ts
git commit -m "test(tool-type): 프론트·백 분류기를 공유 fixture 로 묶는다

두 분류기가 갈라진 채 '별도 추적' 으로 남아 있었다. 같은 JSON 을 pytest 와
node --test 가 함께 읽게 해서 한쪽만 고치면 깨지도록 한다."
```

---

### Task 10: 규약 문서와 스킬

**Files:**

- Create: `docs/back-end/vendor-onboarding.md`
- Create: `.claude/skills/add-vendor/SKILL.md`
- Modify: `docs/back-end/provider-selection.md` (상호 링크)
- Modify: `docs/back-end/README.md`
- Modify: `CLAUDE.md` (Agent skills 표에 `add-vendor` 추가)
- Modify: `.claude/skills/home-to-office/SKILL.md`

**Interfaces:**

- Consumes: Task 1~9 의 결과
- Produces: 없음

- [ ] **Step 1: 규약 문서를 작성**

`docs/back-end/vendor-onboarding.md` 를 한국어로 쓰고 `~입니다.` / `~합니다.`
로 맺습니다. spec 의 §4·§5·§6 을 옮기되, **결정의 근거를 함께 적습니다** —
근거 없는 규약은 다음 사람이 뒤집습니다. 최소 다음을 담습니다.

1. 왜 벤더가 feature 위 폴더가 될 수 없는지 (`office_registry._discover()` 의
   전역 유일 슬러그 제약, `Duplicate feature slug` 부팅 실패)
2. 하위 폴더의 기본 단위가 장비 패밀리인 이유, `hitachi/` 가 예외인 이유
3. 어댑터 미작성 시 501 인 이유 (hardware `_tab()` 과 의도적으로 다름)
4. Phase 1 의 8단계 표
5. 불변식 3가지 (명부는 하나 / 사실은 두 곳에 / 없는 건 없다고)

- [ ] **Step 2: 스킬을 작성**

`.claude/skills/add-vendor/SKILL.md` 에 frontmatter 를 두고, Phase 1 8단계를
체크리스트로 씁니다. 규약 본문은 반복하지 말고
`docs/back-end/vendor-onboarding.md` 를 읽으라고 지시합니다 — 두 곳에
같은 규칙을 적으면 갈라집니다.

```markdown
---
name: add-vendor
description: Use when adding a new e-beam tool family (VeritySEM, Provision, or a future one) to an existing backend feature — scaffolds providers/<family>/, the datatables entry, MIGRATION.md, and the contract tests in the required order.
---
```

- [ ] **Step 3: 링크와 표를 갱신**

`docs/back-end/provider-selection.md` 와 `docs/back-end/README.md` 에서 새
문서를 링크합니다. `CLAUDE.md` 의 "Project skills" 표에 `add-vendor` 행을
더합니다. `.claude/skills/home-to-office/SKILL.md` 의 감사 대상에
`providers/<family>/` 하위 폴더를 포함시킵니다.

- [ ] **Step 4: Markdown lint**

```bash
npm run lint:md 2>&1 | tail -3
```

기대: `Summary: 0 error(s)`.

- [ ] **Step 5: 커밋**

```bash
git add docs/back-end/vendor-onboarding.md docs/back-end/provider-selection.md \
        docs/back-end/README.md CLAUDE.md .claude/skills/add-vendor \
        .claude/skills/home-to-office
git commit -m "docs(back-end): 벤더 온보딩 규약과 add-vendor 스킬을 추가한다

Phase 1(feature × 계열) 이 기계적 반복이 되도록 8단계 절차와 그 근거를
문서로 고정하고, 실행 절차는 스킬로 뽑는다."
```

---

### Task 11: 통합 검증과 병합

**Files:** 없음 (검증만)

- [ ] **Step 1: 전체 백엔드 테스트**

```bash
.venv/bin/python -m pytest -q 2>&1 | tail -3
```

기대: Task 0 기준선의 passed+skipped 합계 + 이 계획에서 추가한 테스트 수.
**줄어들면 안 됩니다** — 줄었다면 평탄화 과정에서 테스트 파일이 수집되지
않고 있다는 뜻입니다.

- [ ] **Step 2: 수집 경로를 직접 확인**

```bash
.venv/bin/python -m pytest --collect-only -q 2>&1 | grep -c "back_dev_home/ebeam"
```

기대: 0 보다 큼. `ebeam/hitachi` 경로는 하나도 나오지 않아야 합니다.

- [ ] **Step 3: 프론트 검증**

```bash
cd front-dev-home && npm test 2>&1 | tail -3 && npm run typecheck 2>&1 | tail -3 && npm run lint 2>&1 | tail -3
```

기대: 전부 통과, typecheck 0 errors.

- [ ] **Step 4: 앱을 띄워 브라우저 확인**

```bash
.venv/bin/python index.py &
cd front-dev-home && npm run dev &
```

확인 항목:

1. `http://localhost:3000/ebeam/veritysem/M14` 가 렌더되고 장비 목록이 보임
2. `http://localhost:3000/ebeam/cd-sem/M14/storage` 가 기존과 동일하게 렌더
3. `curl -s localhost:5050/api/health/providers` 의 feature 목록이 평탄화
   전과 같은 이름들(`storage`, `hardware`, `device_statistics` …)
4. `curl -s "localhost:5050/api/meas-hist?tool_type=zz-sem"` 가 400
5. `/ebeam/cd-sem/skewvoir` 진입 후 콘솔에 에러 없음

스크린샷은 `.playwright-mcp/screenshots/` 에 저장합니다.

- [ ] **Step 5: 병합과 정리**

```bash
cd /Users/daeyoung/Codes/skewnono_v3_nuxt
git merge --ff-only work/ebeam-phase0 && git push
git worktree remove ../skewnono-ebeam-phase0
git branch -d work/ebeam-phase0
git worktree list   # 메인 트리만 남아야 합니다
```

- [ ] **Step 6: 메인 체크아웃의 고아 `office.py` 를 정리**

worktree 에는 gitignored 파일이 없으므로 병합만으로는 메인 체크아웃의
옛 경로에 있던 `office.py` 가 남습니다. 이것들은 아무도 import 하지 않는
고아입니다.

```bash
find back_dev_home/ebeam/hitachi back_dev_home/ebeam/cdsem -name "office.py" 2>/dev/null
```

출력이 있으면 새 경로로 옮깁니다. 예:

```bash
mv back_dev_home/ebeam/hitachi/storage/providers/office.py \
   back_dev_home/ebeam/storage/providers/office.py
```

옮긴 뒤 빈 디렉터리를 지우고 부팅을 확인합니다.

```bash
find back_dev_home/ebeam/hitachi back_dev_home/ebeam/cdsem -type d -empty -delete 2>/dev/null
.venv/bin/python -m pytest -q 2>&1 | tail -3
```

- [ ] **Step 7: 사무실 전달 사항을 기록**

`.scratch/` 에 다음을 남깁니다 — 사무실 체크아웃에도 같은 고아 `office.py`
문제가 있고, **거기서는 앱이 부팅에 실패합니다**(옛 경로를 import 하므로).

```text
[사무실 필독] ebeam 평탄화 후 첫 pull 시
1. git pull
2. find back_dev_home/ebeam/hitachi back_dev_home/ebeam/cdsem -name "office.py"
3. 나온 파일을 back_dev_home/ebeam/<feature>/providers/ 로 옮긴다
4. .venv/bin/python -m scripts.sync_office_adapters   # STALE 여부 확인
5. 부팅 로그에서 STALE office.py 경고가 없는지 확인
```

---

## Self-Review

**Spec 커버리지**

| spec 절 | 담당 Task |
| --- | --- |
| §4.1 목표 구조 | Task 1 |
| §4.2 평탄화 근거 | Task 1, Task 10 |
| §4.3 기존 도구 호환 | Task 11 Step 2 |
| §4.4 하위 폴더 단위 | Task 10 (문서). 구현은 Phase 1 |
| §4.5 어댑터 디스패처 | **Phase 1** — 이 계획의 범위 밖 (Global Constraints 에 명시) |
| §5.1 레지스트리 | Task 2 |
| §5.2 프론트 통합 | Task 5, Task 6, Task 9 |
| §5.3 침묵 실패 | Task 3, Task 4, Task 7 |
| §5.4 `veritysem` 파급 | Task 6, Task 8 |
| §6 워크플로 문서화 | Task 10 |
| §8 검증 | Task 11 |

**남은 것**: §4.4·§4.5 의 실제 구현은 AMAT 오피스 소스가 확인된 뒤
Phase 1 계획서에서 다룹니다. 이 계획은 그 전제 조건만 만듭니다.
