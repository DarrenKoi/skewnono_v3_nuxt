# Recipe TAT 장비별 뷰 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Recipe TAT 화면에 `장비별`(eqp_id 기준) 뷰를 추가해, 장비별 측정 부하·소요 시간·레시피 커버리지를 한 표에서 비교하고 최대 5대를 골라 트렌드와 레시피 구성을 겹쳐 볼 수 있게 합니다.

**Architecture:** 백엔드에 새 엔드포인트 2개(`/equipments`, `/equipment-compare`)를 추가합니다. 기존 4개 엔드포인트와 그 office 어댑터는 건드리지 않습니다. 두 엔드포인트 모두 `meas_hist` 행을 `(eqp_id, full_name)`으로 집계한 결과에서 파생되며, 홈에서는 mock이, 사무실에서는 OpenSearch composite 집계가 같은 계약을 채웁니다. 프론트엔드는 `RecipeTatView.vue`의 기존 본문을 건드리지 않고 모드 분기만 추가한 뒤 새 컴포넌트 3개로 뻗어나갑니다.

**Tech Stack:** Flask blueprint + TypedDict 계약 + pytest / Nuxt 4 + NuxtUI + ECharts(`useEchart`) + `node --test`

## Global Constraints

설계 문서: `docs/superpowers/specs/2026-08-07-recipe-tat-by-equipment-design.md`. 아래는 모든 task에 암묵적으로 적용됩니다.

- **`data.py`는 편집 금지.** 새 함수는 dispatcher 패턴(`_provider()` 경유)을 그대로 따라 추가만 합니다.
- **office 어댑터는 `office_example.py`만 작성합니다.** `office.py`는 gitignore된 사무실 복사본이라 홈에 존재하지 않습니다.
- **공유 모듈 시그니처를 깨지 않습니다.** `_office_meas_hist.py`의 `composite_buckets(index, field, sub_aggs, query_body)` 기존 호출 형태는 그대로 동작해야 합니다. 사무실에는 아직 복사되지 않은 오래된 `office.py`들이 있고, import 에러 하나가 앱 팩토리 전체를 죽입니다.
- **커밋은 직접 편집한 파일만 명시적 경로로.** `git add -A`, `git add .`, `git commit -a` 금지 — 같은 작업 트리에서 다른 세션이 동시에 돌아갑니다.
- **임계값 상수 4개는 전부 `OFFICE-VERIFY` 주석과 함께** `equipmentSignals.ts` 한 파일에만 존재합니다: `USAGE_FLOOR = 0.85`, `TAT_CEIL = 1.10`, `TAT_FLOOR = 0.92`, `SHARE_CEIL = 0.50`.
- **`TAT_INDEX_MIN_SAMPLE = 12`** (OFFICE-VERIFY), **`MAX_EQP_IDS = 5`**.
- **자동 임포트 태그에는 경로 접두사가 붙습니다.** `components/ebeam/RecipeTatFleetTable.vue` → `<EbeamRecipeTatFleetTable>`. 틀리면 정적 검사 신호 없이 빈 화면만 나옵니다.
- **UI 색상은 `--sk-*` 토큰만 사용합니다.** 인라인 hex 금지. UI 작업 전 `DESIGN.md`를 읽습니다.
- **차트 옵션은 커서 상태에 의존하면 안 됩니다** (`useEchart`의 `notMerge` 재빌드 규약). 다중 시리즈 라인에 `areaStyle`을 쓰지 않습니다 — hover 시 blur가 채움을 지웁니다.
- 백엔드 테스트: `.venv/bin/python -m pytest -q` (반드시 `python -m`, 저장소 루트에서).
- 프론트엔드: `npm test`, `npm run typecheck`, `npm run lint` (`front-dev-home/`에서). Markdown 편집 후 루트에서 `npm run lint:md`.

**작업 격리:** 이 계획은 여러 파일을 건드리므로 worktree에서 진행합니다.

```bash
git worktree add ../skewnono-eqp-view -b work/recipe-tat-eqp   # 저장소 루트에서
# ...모든 task를 ../skewnono-eqp-view 안에서 수행...
git -C . merge --ff-only work/recipe-tat-eqp && git push        # main으로 복귀
git worktree remove ../skewnono-eqp-view && git branch -d work/recipe-tat-eqp
```

worktree에는 gitignore된 `office.py` 사본이 없으므로 `pytest`의 **skip 수가 main 체크아웃과 다릅니다.** passed 수만 비교하지 말고 passed+skipped 합계로 비교하세요.

## File Structure

| 파일 | 책임 | Task |
| --- | --- | --- |
| `back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py` | lot 풀의 fab 어휘 (M12 → M10) | 1 |
| `back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py` | 장비 플릿 · 행 생성 · 집계 | 2, 4, 5 |
| `back_dev_home/ebeam/hitachi/_analytics.py` | 공유 분위수 헬퍼 | 4 |
| `back_dev_home/ebeam/hitachi/recipe_tat/contracts.py` | 새 TypedDict + 상수 | 4, 5 |
| `back_dev_home/ebeam/hitachi/recipe_tat/data.py` | dispatcher 함수 2개 추가 | 4, 5 |
| `back_dev_home/ebeam/hitachi/recipe_tat/routes.py` | 라우트 2개 추가 | 4, 5 |
| `back_dev_home/ebeam/hitachi/_analytics_routes.py` | `eqp_ids` 파싱 | 5 |
| `back_dev_home/ebeam/hitachi/_office_meas_hist.py` | 다중 소스 composite (하위호환) | 6 |
| `back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py` | office 집계 템플릿 | 6 |
| `front-dev-home/app/utils/equipmentSignals.ts` | 배지 판정 순수 함수 | 7 |
| `front-dev-home/app/composables/useRecipeTatApi.ts` | 타입 + fetcher 2개 | 8 |
| `front-dev-home/app/components/ebeam/RecipeTatFleetTable.vue` | 플릿 표 (표시 전용) | 8 |
| `front-dev-home/app/components/ebeam/RecipeTatEquipmentView.vue` | 오케스트레이터 (fetch + 선택 상태) | 8 |
| `front-dev-home/app/components/ebeam/RecipeTatEquipmentCompare.vue` | 트렌드 오버레이 + 레시피 매트릭스 | 9 |
| `front-dev-home/app/components/ebeam/RecipeTatView.vue` | 모드 토글 + 분기 (최소 편집) | 8 |
| `front-dev-home/app/components/ebeam/DateRangePopover.vue` | 60/90일 프리셋 | 10 |
| `docs/datatables/meas_hist.txt`, `docs/api-contracts/recipe-tat.yaml` | 문서 | 2, 10 |

---

### Task 1: fab 어휘 통일 — M12는 실재하지 않는 fab

`docs/datatables/sem_list.txt`가 이미 판정해 둔 사실입니다: *"현재 운영 중인 값의 전부는 R3, M16, M15, M14, M11, M10 입니다 (user-confirmed 2026-08-03). 예전 문서와 mock 에 있던 M12 는 실재하지 않는 값이었습니다."*

`sem_list` mock은 이미 고쳐졌지만 `device_statistics`의 lot 풀은 아직 M12를 만들고 M10을 만들지 않습니다. Task 2에서 "장비의 fac_id에 맞는 lot"을 뽑아야 하는데, 장비는 M10에 있고 lot은 M12에 있으면 둘이 절대 만나지 못합니다. 폴백으로 덮으면 문서가 틀렸다고 기록해 둔 값이 mock 안에 영원히 남습니다.

**Files:**
- Modify: `back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py:66`, `:78-84`, docstring `:10`
- Modify: `docs/datatables/device_info.txt:9`, `docs/datatables/meas_hist.txt:11`
- Test: `back_dev_home/ebeam/cdsem/device_statistics/tests/test_contract.py`

**Interfaces:**
- Consumes: 없음 (첫 task)
- Produces: `_lot_index()`가 `{lot_cd: fac_id}`를 반환하며 `fac_id ∈ {R3, M10, M11, M14, M15, M16}`. Task 2가 이 fac_id로 장비와 lot을 짝지웁니다.

- [ ] **Step 1: 현재 fac 분포를 기록해 두는 실패 테스트 작성**

`back_dev_home/ebeam/cdsem/device_statistics/tests/test_contract.py` 끝에 추가:

```python
def test_lot_index_fac_ids_match_the_operating_fabs():
    # M12는 실재하지 않습니다 — docs/datatables/sem_list.txt (user-confirmed
    # 2026-08-03). sem_list가 장비 명부의 진실이고, lot 풀의 fac_id는 그
    # 어휘를 벗어나면 안 됩니다. 벗어나면 recipe_tat의 장비<->lot 짝짓기가
    # 조용히 폴백 경로로 새어 나갑니다.
    from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index
    from back_dev_home.sem_list.providers.mock import FAC_IDS

    fac_ids = set(_lot_index().values())
    assert fac_ids <= set(FAC_IDS), f"sem_list에 없는 fac_id: {fac_ids - set(FAC_IDS)}"
    assert "M12" not in fac_ids
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/cdsem/device_statistics/tests/test_contract.py::test_lot_index_fac_ids_match_the_operating_fabs -v`

Expected: FAIL — `sem_list에 없는 fac_id: {'M12'}`

- [ ] **Step 3: M12 → M10 치환**

`back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py`:

```python
M_FAC_IDS = ["M10", "M11", "M14", "M15", "M16"]
```

```python
M_LOT_PREFIX_BY_FAC = {
    "M10": "0",
    "M11": "1",
    "M14": "4",
    "M15": "5",
    "M16": "6"
}
```

docstring 10번째 줄의 `M11/M12/M14/M15/M16`을 `M10/M11/M14/M15/M16`으로 고치고, 아래 주석을 `M_FAC_IDS` 바로 위에 붙입니다:

```python
# 운영 중인 M-fab 전부입니다. 예전 mock에 있던 M12는 실재하지 않는 값이었고
# (docs/datatables/sem_list.txt, user-confirmed 2026-08-03), sem_list의 FAC_IDS가
# 이 어휘의 진실입니다. 여기가 어긋나면 recipe_tat이 장비(sem_list)와
# lot(여기)을 fac_id로 짝지을 때 만나지 못하는 조합이 생깁니다.
```

- [ ] **Step 4: 통과 확인 + device_statistics 전체 회귀**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/cdsem/device_statistics -q`

Expected: 전부 PASS. 이 스위트가 저장소에서 가장 크므로(전체 ~72초의 대부분) 여기서 깨지면 즉시 멈추고 원인을 봅니다. lot_cd 접두사가 `2*` → `0*`로 바뀌므로, 특정 lot_cd 문자열을 하드코딩한 테스트가 있으면 그 테스트가 잘못된 것입니다(생성값에 의존해야 함).

- [ ] **Step 5: 데이터 문서 갱신**

`docs/datatables/device_info.txt:9`와 `docs/datatables/meas_hist.txt:11`의 `예: M11, M12, M14, M15, M16` 을 각각 다음으로 고칩니다:

```text
fac_id -> string: fab 대표 코드. 예: M10, M11, M14, M15, M16, R3
                  (M12는 실재하지 않습니다 — sem_list.txt 참조, user-confirmed 2026-08-03)
```

- [ ] **Step 6: 전체 스위트 + 커밋**

```bash
.venv/bin/python -m pytest -q
npm run lint:md
git add back_dev_home/ebeam/cdsem/device_statistics/providers/mock.py \
        back_dev_home/ebeam/cdsem/device_statistics/tests/test_contract.py \
        docs/datatables/device_info.txt docs/datatables/meas_hist.txt
git commit -m "fix(mock): M12 -> M10, 실재하지 않는 fab을 lot 풀에서 제거

sem_list.txt가 이미 판정한 사실입니다(user-confirmed 2026-08-03). sem_list
mock은 고쳐졌지만 device_statistics의 lot 풀은 여전히 M12 lot을 만들고 M10
lot을 만들지 않아, 장비(M10 보유)와 lot(M12 보유)이 fac_id로 만날 수
없었습니다. recipe_tat 장비별 뷰가 이 짝짓기를 필요로 합니다.

lot_cd 접두사도 함께 이동합니다(M12='2' -> M10='0')."
```

**참고 — 범위 밖:** `sem_list/__fixtures__/sem-list.json`과 `storage/__fixtures__/*.json`에도 M12가 남아 있습니다. 이들은 캡처된 API 응답이고 이 feature의 경로에 관여하지 않으므로 건드리지 않습니다. 별도 정리 과제입니다.

---

### Task 2: mock 장비 플릿 — sem_list를 명부로, 생성 순서를 장비→lot으로

지금 mock은 `CG63-04` 같은 eqp_id를 지어냅니다. `_tool_specs.py`가 명시적으로 금지하는 일입니다: *"sem_list is the roster of record… never parse the id itself."* `docs/datatables/meas_hist.txt` 규칙 1도 *"eqp_id…는 sem-list mock data에서 고른 장비 row를 복사합니다"*라고 이미 요구하고 있습니다.

또한 지어낸 eqp_id는 fab에도 meastime에도 묶여 있지 않아서, 같은 장비가 7개 fab에 동시에 나타나고 `tat_index`는 잡음이 됩니다.

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py` (전면 — docstring, 상수, 생성 함수)
- Modify: `docs/datatables/meas_hist.txt` (생성 규칙 1·6)
- Test: `back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py`

**Interfaces:**
- Consumes: Task 1의 `_lot_index()` (fac_id ∈ sem_list 어휘)
- Produces:
  - `_tool_fleet() -> dict[ToolType, tuple[ToolProfile, ...]]` — `ToolProfile`은 `{"eqp_id","fab_name","fac_id","eqp_model_cd","vendor_nm","speed","workload","classes"}` 키를 가진 dict. `classes`는 `tuple[str, ...] | None`(None이면 fab 기본 mix 사용).
  - `ACTIVE_TOOLS_PER_FAB = 5`, `TOTAL_MEAS_ROWS = 55_000`, `HISTORY_WINDOW_DAYS = 180`
  - `get_meas_hist()` 행의 `eqp_id`/`fab_name`/`eqp_model_cd`/`vendor_nm`이 전부 sem_list row에서 옴
  - `FAB_NAMES_BY_FAC`와 `_build_eqp_id()`는 **삭제됨** — 이후 task는 이 이름을 참조하면 안 됩니다.

- [ ] **Step 1: 플릿 정합성 실패 테스트 4개 작성**

`back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py` 끝에 추가:

```python
def test_mock_rows_carry_real_sem_list_tools():
    # eqp_id를 지어내지 않습니다 — sem_list가 장비 명부의 진실입니다
    # (_tool_specs.py 모듈 docstring, meas_hist.txt 생성 규칙 1).
    if get_data_provider("recipe_tat") != "mock":
        return
    from back_dev_home.sem_list.providers.mock import _generate_rows

    roster = {}
    for row in _generate_rows():
        roster.setdefault(row["eqp_id"], row)   # 중복 eqp_id는 첫 행이 이깁니다

    for row in data.get_meas_hist():
        tool = roster.get(row["eqp_id"])
        assert tool is not None, f"sem_list에 없는 eqp_id: {row['eqp_id']}"
        assert row["fab_name"] == tool["fab_name"]
        assert row["eqp_model_cd"] == tool["eqp_model_cd"]
        assert row["vendor_nm"] == tool["vendor_nm"]


def test_mock_each_tool_lives_in_exactly_one_fab():
    # 물리 장비는 fab 하나에 있습니다. 이게 깨지면 장비별 표에서 한 장비가
    # 여러 fab에 걸쳐 나타납니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    fabs_by_eqp: dict[str, set[str]] = {}
    for row in data.get_meas_hist():
        fabs_by_eqp.setdefault(row["eqp_id"], set()).add(row["fab_name"])
    offenders = {eqp: fabs for eqp, fabs in fabs_by_eqp.items() if len(fabs) > 1}
    assert not offenders, f"여러 fab에 걸친 장비: {offenders}"


def test_mock_lot_fac_matches_tool_fac():
    # 측정은 장비가 있는 fab에서 일어나고 lot이 거기 들어옵니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index

    lot_fac = _lot_index()
    for row in data.get_meas_hist():
        assert lot_fac[row["lot_cd"]] == row["fac_id"]


def test_mock_density_supports_the_tat_index():
    # 기본 조회(fab 1개 · 14일)에서 장비당 실행 수 중앙값이 표본 하한을
    # 넘어야 합니다. 이 가드가 없으면 누가 행 수를 줄였을 때 장비별 표의
    # TAT index 열이 조용히 전부 '—'가 됩니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    import statistics

    anchor = data.get_anchor_time().date()
    end = anchor.isoformat()
    start = (anchor - timedelta(days=14)).isoformat()
    rows = [
        r for r in data.get_meas_hist()
        if r["tool_type"] == "cd-sem" and r["fab_name"] == "R3"
        and start <= r["timestamp"][:10] <= end
    ]
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["eqp_id"]] = counts.get(row["eqp_id"], 0) + 1
    assert counts, "R3 / cd-sem / 최근 14일에 측정이 하나도 없습니다"
    assert statistics.median(counts.values()) >= 12
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat -q -k "mock_"`

Expected: 4개 모두 FAIL. 각각 `sem_list에 없는 eqp_id: CG63-04`, `여러 fab에 걸친 장비: {...}`, `KeyError`/불일치, 밀도 미달.

- [ ] **Step 3: 플릿 빌더 구현**

`back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py`에서 `FAB_NAMES_BY_FAC`, `_build_eqp_id()`, `TOOL_MODELS`를 **삭제**하고 아래를 추가합니다. import에 `from back_dev_home.ebeam.hitachi._tool_specs import model_to_tool_type`와 `from back_dev_home.sem_list.providers import mock as sem_list_mock`를 더합니다.

```python
ACTIVE_TOOLS_PER_FAB = 5    # (tool_type, fab_name) 칸마다 실제로 측정하는 장비 수


@lru_cache(maxsize=1)
def _tool_fleet() -> dict[ToolType, tuple[dict, ...]]:
    """sem_list 명부에서 활성 장비를 뽑고 장비별 고정 스칼라를 붙입니다.

    eqp_id는 절대 지어내지 않습니다 — sem_list가 장비 명부의 진실이고
    (_tool_specs.py 모듈 docstring), fab_name/eqp_model_cd/vendor_nm은 그
    장비의 sem_list row에서 그대로 복사합니다(meas_hist.txt 생성 규칙 1).

    sem_list mock은 eqp_id가 중복될 수 있으므로(300행 중 고유 290개)
    첫 행이 이기도록 dedupe합니다. dedupe하지 않으면 한 eqp_id가 두 fab에
    속하게 되어 "장비는 fab 하나에 산다"는 불변식이 첫날부터 깨집니다.

    장비별 스칼라(speed/workload/classes)가 흉내내는 것은 실 데이터의 *값*이
    아니라 *편차가 존재한다는 사실*입니다. 정상 장비의 폭을 좁게(±8 %) 둔
    것은 실 플릿의 가동률이 대부분 90 % 이상으로 몰려 있다는 현업 확인을
    반영한 것입니다(user-confirmed 2026-08-07). 칸마다 역할을 고정 배정하는
    이유는 어느 fab을 보더라도 UI의 모든 배지 상태를 한 번씩 밟아보기
    위해서이지, 실제로 5대 중 1대가 느리다는 주장이 아닙니다.
    """
    rng = random.Random(20260807)

    roster: dict[str, dict] = {}
    for row in sem_list_mock._generate_rows():
        roster.setdefault(row["eqp_id"], row)

    cells: dict[tuple[ToolType, str], list[dict]] = {}
    for eqp_id in sorted(roster):                 # 정렬 = 결정론
        row = roster[eqp_id]
        tool_type = model_to_tool_type(row["eqp_model_cd"])
        if tool_type is None:                     # AMAT VeritySEM/Provision — 2027년 이후
            continue
        cells.setdefault((tool_type, row["fab_name"]), []).append(row)

    fleet: dict[ToolType, list[dict]] = {"cd-sem": [], "hv-sem": []}
    for (tool_type, fab_name), members in sorted(cells.items()):
        # 보유분보다 많이 뽑지 않습니다 — hv-sem에는 5대 미만인 칸이 여럿입니다
        # (예: M10B는 1대). 없는 장비를 지어내지 않습니다.
        active = members[:ACTIVE_TOOLS_PER_FAB]
        for index, row in enumerate(active):
            fleet[tool_type].append({
                "eqp_id": row["eqp_id"],
                "fab_name": row["fab_name"],
                "fac_id": row["fac_id"],
                "eqp_model_cd": row["eqp_model_cd"],
                "vendor_nm": row["vendor_nm"],
                **_tool_scalars(rng, index, fab_name),
            })

    return {tool_type: tuple(tools) for tool_type, tools in fleet.items()}


def _tool_scalars(rng: random.Random, index: int, fab_name: str) -> dict:
    """칸 안의 순번으로 역할을 고정 배정합니다 (0=느림, 1=저사용, 2=편중).

    순번 배정이라 fab을 어디로 바꿔도 배지 상태가 하나씩 나타납니다.
    R3의 순번 3만 예외적으로 거의 놀게 두어 tat_index=None 경로(표본 미달)를
    기본 화면에서 밟을 수 있게 합니다 — 실 데이터에 그런 장비가 있다는
    주장이 아니라 UI 상태를 시연하기 위해 의도적으로 과장한 사례입니다.
    """
    normal_speed = round(rng.uniform(0.96, 1.04), 4)
    normal_workload = round(rng.uniform(0.92, 1.08), 4)

    if index == 0:
        return {"speed": round(rng.uniform(1.12, 1.20), 4),
                "workload": normal_workload, "classes": None}
    if index == 1:
        return {"speed": normal_speed,
                "workload": round(rng.uniform(0.70, 0.80), 4), "classes": None}
    if index == 2:
        return {"speed": normal_speed, "workload": normal_workload,
                "classes": (rng.choice(DEFAULT_CLASS_MIX),)}
    if index == 3 and fab_name == "R3":
        return {"speed": normal_speed, "workload": 0.30, "classes": None}
    return {"speed": normal_speed, "workload": normal_workload, "classes": None}
```

- [ ] **Step 4: 행 생성을 장비 우선으로 재작성**

밀도 상수를 갱신하고:

```python
RECIPE_DEFINITIONS_PER_TOOL = 60      # distinct recipes per tool_type
TOTAL_MEAS_ROWS = 55_000              # 기본 조회(fab 1개·14일)에서 장비당 ~25건
HISTORY_WINDOW_DAYS = 180             # 90일 프리셋에 2배 여유
```

`_recipe_definitions()`에서 `eqp_model_cd` / `vendor_nm` 키를 **제거**합니다 (이제 장비에서 옵니다). `TOOL_MODELS` 참조도 함께 사라집니다:

```python
            recipes.append({
                "tool_type": tool_type,
                "class_name": class_name,
                "recipe_name": recipe_name,
                "full_name": full_name,
                "baseline_meastime": baseline
            })
```

fac_id별 lot 색인을 추가합니다 (`_lot_pool()` 대체):

```python
@lru_cache(maxsize=1)
def _lots_by_fac() -> dict[str, tuple[str, ...]]:
    """fac_id -> 그 fab의 lot_cd들. 측정은 장비가 있는 fab에서 일어납니다."""
    grouped: dict[str, list[str]] = {}
    for lot_cd, fac_id in sorted(_lot_index().items()):
        grouped.setdefault(fac_id, []).append(lot_cd)
    return {fac_id: tuple(lots) for fac_id, lots in grouped.items()}
```

`_generate_meas_hist()` 본문을 교체합니다:

```python
@lru_cache(maxsize=1)
def _generate_meas_hist() -> tuple[MeasHistRow, ...]:
    """meas_hist mock 전체를 생성합니다.

    순서가 중요합니다: **장비 → lot → 레시피**. 측정은 어떤 fab의 어떤
    장비에서 일어나고, lot이 거기 들어오고, 그 lot에 레시피가 돕니다.
    예전 구현은 lot에서 시작해 fab을 고르고 장비를 지어냈는데, 그러면
    같은 장비가 여러 fab에 나타나고 meastime이 장비와 무관해집니다.

    결정론이 계약입니다: 같은 (tool_type, 기간) 질의는 항상 같은 집계를
    돌려줘야 대시보드가 렌더 사이에 흔들리지 않습니다.
    """
    rng = random.Random(20260508)
    recipes = _recipe_definitions()
    by_tool_class, by_tool = _recipe_indexes(recipes)
    fleet = _tool_fleet()
    lots_by_fac = _lots_by_fac()

    if not recipes or not any(fleet.values()):
        return ()

    # workload 가중 추출용 누적 가중치 (tool_type별로 한 번 계산)
    weighted: dict[ToolType, tuple[list[dict], list[float]]] = {}
    for tool_type, tools in fleet.items():
        if not tools:
            continue
        cumulative: list[float] = []
        running = 0.0
        for tool in tools:
            running += tool["workload"]
            cumulative.append(running)
        weighted[tool_type] = (list(tools), cumulative)

    rows: list[MeasHistRow] = []
    history_start = ANCHOR_TIME - timedelta(days=HISTORY_WINDOW_DAYS)
    window_seconds = HISTORY_WINDOW_DAYS * 24 * 3600

    for index in range(TOTAL_MEAS_ROWS):
        tool_type: ToolType = "cd-sem" if index % 2 == 0 else "hv-sem"
        if tool_type not in weighted:
            continue
        tools, cumulative = weighted[tool_type]
        tool = tools[bisect.bisect_left(cumulative, rng.uniform(0, cumulative[-1]))]

        # lot은 장비가 선 fab의 것만. Task 1에서 fac 어휘를 통일했으므로
        # 여기서 비는 fac은 없어야 하지만, sem_list에만 있고 lot이 없는
        # fac이 생기면 그 장비는 측정 없이 남습니다(조용한 폴백 금지).
        lots = lots_by_fac.get(tool["fac_id"])
        if not lots:
            continue
        lot_cd = lots[rng.randrange(len(lots))]

        recipe = _pick_recipe_for_tool(rng, by_tool_class, by_tool, tool_type, tool)

        offset = rng.randint(0, window_seconds - 1)
        end_dt = history_start + timedelta(seconds=offset)

        # meastime = 레시피 baseline × fab 성격 × **장비 speed** × jitter.
        # 장비 항이 여기 들어와야 tat_index가 잡음이 아닌 신호가 됩니다.
        jitter = rng.uniform(-0.25, 0.25)
        fab_multiplier = FAB_MEASTIME_MULTIPLIER.get(fab_base(tool["fab_name"]), 1.0)
        meastime = max(
            30,
            int(recipe["baseline_meastime"] * fab_multiplier * tool["speed"] * (1 + jitter))
        )

        start_dt = end_dt - timedelta(seconds=meastime)

        rows.append({
            "id": f"MEAS-{index + 1:06d}",
            "fac_id": tool["fac_id"],
            "fab_name": tool["fab_name"],
            "vendor_nm": tool["vendor_nm"],
            "eqp_id": tool["eqp_id"],
            "eqp_model_cd": tool["eqp_model_cd"],
            "tool_type": tool_type,
            "lot_cd": lot_cd,
            "lot_id": _build_lot_id(rng, lot_cd),
            "class_name": recipe["class_name"],
            "recipe_name": recipe["recipe_name"],
            "full_name": recipe["full_name"],
            "timestamp": _format_iso(end_dt),
            "start_time": _format_iso(start_dt),
            "end_time": _format_iso(end_dt),
            "meastime": meastime
        })

    return tuple(rows)
```

`_pick_recipe_for_fab()`를 `_pick_recipe_for_tool()`로 교체합니다:

```python
def _pick_recipe_for_tool(
    rng: random.Random,
    by_tool_class: dict[tuple[ToolType, str], tuple[dict, ...]],
    by_tool: dict[ToolType, tuple[dict, ...]],
    tool_type: ToolType,
    tool: dict
) -> dict:
    # 편중 장비(classes 지정)는 자기 class만 돕니다 — 레시피 커버리지 신호.
    mix = tool["classes"] or FAB_CLASS_MIX.get(fab_base(tool["fab_name"]), DEFAULT_CLASS_MIX)
    class_name = rng.choice(mix)
    candidates = by_tool_class.get((tool_type, class_name)) or by_tool[tool_type]
    return candidates[rng.randrange(len(candidates))]
```

파일 상단 import에 `import bisect`를 추가하고, `from back_dev_home.ebeam.cdsem.device_statistics.providers.mock import _lot_index`는 그대로 둡니다.

`FAB_MEASTIME_MULTIPLIER`와 `FAB_CLASS_MIX`의 `"M12"` 키를 `"M10"`으로 고칩니다 (Task 1과 같은 이유).

- [ ] **Step 5: 통과 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat back_dev_home/ebeam/hitachi/fail_issue -q`

Expected: 전부 PASS. `fail_issue`는 같은 행을 읽으므로 함께 돌립니다.

첫 호출에서 55,000행 생성에 약 0.9초가 듭니다 (실측: 842 B/row 선형, 6k=0.10s/5.1MB, 30k=0.50s/25.3MB, 60k=0.98s/50.5MB). `lru_cache`로 프로세스당 1회입니다.

- [ ] **Step 6: docstring 재작성**

`mock.py` 모듈 docstring에서 아래 두 문장을 **삭제**합니다 (둘 다 더는 사실이 아닙니다):

- `NOTE: _lot_index is currently sourced from cdsem.device_statistics. HV-SEM responses … until an HV-SEM-specific lot pool is introduced — acceptable for mock-only Phase 1 since no HV-SEM frontend currently calls these endpoints.` → HV-SEM 프론트엔드는 **존재합니다** (`pages/ebeam/hv-sem/[fab]/recipe-status.vue`).
- `Multi-fab filtering …` 단락은 유지합니다.

대신 아래를 추가합니다:

```text
장비 플릿은 sem_list mock에서 옵니다 (_tool_fleet). eqp_id / fab_name /
eqp_model_cd / vendor_nm 을 sem_list row에서 그대로 복사하며, 지어내지
않습니다 — meas_hist.txt 생성 규칙 1과 _tool_specs.py 모듈 docstring이
요구하는 방식입니다. 행 생성 순서는 장비 → lot → 레시피이고, lot은 장비가
선 fab(fac_id)의 것만 뽑습니다.

장비별 고정 스칼라(speed / workload / classes)가 흉내내는 것은 사무실
데이터의 *값*이 아니라 *장비 사이에 편차가 존재한다는 사실*입니다. 정상
장비의 폭을 ±8 %로 좁게 둔 근거는 실 플릿의 가동률이 대부분 90 % 이상으로
몰려 있다는 현업 확인입니다(user-confirmed 2026-08-07). R3의 거의 놀고 있는
장비 한 대는 tat_index=None(표본 미달) 경로를 UI에서 밟기 위해 의도적으로
과장한 사례이지 실 데이터에 대한 주장이 아닙니다.

측정 물량(TOTAL_MEAS_ROWS)은 집계와 화면을 제대로 돌려보기 위한 최소치이지
사무실 물량이 아닙니다. 실제 CD-SEM은 이보다 훨씬 많이 측정합니다.

사무실 주의사항: ANCHOR_TIME 은 모듈 로드 시점의 wall-clock 입니다. 사무실
구현은 wall-clock 대신 실 인덱스의 max(timestamp) 를 anchor 로 사용해야
합니다.
```

- [ ] **Step 7: 데이터 문서 갱신**

`docs/datatables/meas_hist.txt`의 "Mock data 생성 규칙" 1번과 6번을 고칩니다:

```text
1. eqp_id, eqp_model_cd, vendor_nm, fac_id, fab_name은 sem-list mock data에서
   먼저 고른 장비 row를 기준으로 복사합니다. 지어내지 않습니다. 생성 순서는
   장비 → lot → recipe 이며, lot은 그 장비가 선 fab(fac_id)의 것만 고릅니다.
   sem_list mock은 eqp_id가 중복될 수 있으므로 첫 행이 이기도록 dedupe합니다.
```

```text
6. timestamp는 최근 180일 안에서 생성합니다. (장비별 뷰가 90일 조회를
   지원하므로 60일로는 부족합니다.) meastime은 end_time - start_time입니다.
   timestamp는 기본적으로 end_time과 같게 둡니다. meastime은 recipe baseline
   × fab 배수 × 장비 speed × jitter 로 만들며, 장비 항이 있어야 장비별
   TAT 지수가 잡음이 아닌 신호가 됩니다.
```

- [ ] **Step 8: 전체 스위트 + 커밋**

```bash
.venv/bin/python -m pytest -q
npm run lint:md
git add back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py \
        docs/datatables/meas_hist.txt
git commit -m "fix(recipe-tat/mock): 장비 플릿을 sem_list에서 가져오고 생성 순서를 뒤집기

지어낸 eqp_id(CG63-04)를 sem_list 명부의 실제 장비로 교체합니다.
_tool_specs.py가 'sem_list is the roster of record, never parse the id
itself'라고, meas_hist.txt 규칙 1이 'sem-list에서 고른 장비 row를
복사합니다'라고 이미 요구하던 것입니다.

생성 순서를 lot->fab->장비(날조)에서 장비->lot->recipe로 뒤집습니다.
효과:
- FAB_NAMES_BY_FAC 하드코딩 표가 사라져 fab 어휘 드리프트가 구조적으로
  재발 불가능해집니다
- 한 장비가 여러 fab에 나타나던 문제가 사라집니다
- meastime 식에 장비 speed가 들어가 tat_index가 신호가 됩니다

밀도: HISTORY_WINDOW_DAYS 120->180, TOTAL_MEAS_ROWS 6,000->55,000.
현재 mock은 cd-sem/M14A/14일 조회에 측정이 전 장비 합쳐 7건뿐이었습니다.
실측 비용은 842 B/row 선형으로 55k행 = 약 46MB / 생성 0.9초(lru_cache 1회).

fail_issue가 같은 행을 읽으므로 함께 개선됩니다."
```

---

### Task 3: 분위수 헬퍼

`/equipments`가 배지 임계값을 사무실에서 조정할 수 있도록 분포 요약을 함께 내려보냅니다. 이게 없으면 사무실에서 임계값 맞추는 일이 raw 데이터를 따로 뽑아 분석하는 별도 과제가 됩니다.

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/_analytics.py`
- Test: `back_dev_home/ebeam/hitachi/tests/test_analytics.py` (없으면 생성; `back_dev_home/ebeam/hitachi/tests/__init__.py`도 함께)

**Interfaces:**
- Consumes: 없음
- Produces: `percentile_summary(values: Iterable[float]) -> dict[str, float]` — 키 `p10/p25/p50/p75/p90`, 빈 입력이면 `{}`.

- [ ] **Step 1: 실패 테스트 작성**

`back_dev_home/ebeam/hitachi/tests/test_analytics.py`:

```python
from back_dev_home.ebeam.hitachi._analytics import percentile_summary


def test_percentile_summary_is_empty_for_no_values():
    assert percentile_summary([]) == {}


def test_percentile_summary_is_monotonic():
    # p10 <= p25 <= p50 <= p75 <= p90 은 정의상 항상 성립해야 합니다.
    # 프론트엔드의 배지 판정이 "꼬리에 있는가"를 이 값들로 묻기 때문입니다.
    summary = percentile_summary([5, 1, 9, 3, 7, 2, 8, 4, 6, 10])
    keys = ["p10", "p25", "p50", "p75", "p90"]
    values = [summary[key] for key in keys]
    assert values == sorted(values)


def test_percentile_summary_uses_nearest_rank():
    # 10개 표본에서 p10은 최솟값, p90은 9번째 값(nearest-rank).
    summary = percentile_summary(range(1, 11))
    assert summary["p10"] == 1.0
    assert summary["p50"] == 5.0
    assert summary["p90"] == 9.0


def test_percentile_summary_handles_a_single_value():
    assert percentile_summary([4.5]) == {
        "p10": 4.5, "p25": 4.5, "p50": 4.5, "p75": 4.5, "p90": 4.5
    }
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/tests/test_analytics.py -v`

Expected: FAIL — `ImportError: cannot import name 'percentile_summary'`

- [ ] **Step 3: 구현**

`back_dev_home/ebeam/hitachi/_analytics.py` 끝에 추가하고, 상단에 `import math`를 더합니다:

```python
_PERCENTILE_POINTS: tuple[tuple[str, float], ...] = (
    ("p10", 0.10), ("p25", 0.25), ("p50", 0.50), ("p75", 0.75), ("p90", 0.90),
)


def percentile_summary(values: Iterable[float]) -> dict[str, float]:
    """p10/p25/p50/p75/p90을 nearest-rank로 계산합니다.

    보간이 아니라 nearest-rank인 이유는 결과가 항상 실제 표본값이고 단조가
    정의상 보장되기 때문입니다 — 프론트엔드가 "이 장비가 꼬리에 있는가"를
    이 값들과의 단순 비교로 묻습니다.

    표본이 없으면 빈 dict입니다. 호출자(그리고 UI)는 이걸 "판단 근거 없음"
    으로 읽어야 하며, 배지를 달지 않습니다.
    """
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return {}

    def at(quantile: float) -> float:
        index = math.ceil(quantile * len(ordered)) - 1
        return ordered[max(0, min(index, len(ordered) - 1))]

    return {name: at(quantile) for name, quantile in _PERCENTILE_POINTS}
```

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/tests/test_analytics.py -v`

Expected: 4 passed

- [ ] **Step 5: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/_analytics.py \
        back_dev_home/ebeam/hitachi/tests/__init__.py \
        back_dev_home/ebeam/hitachi/tests/test_analytics.py
git commit -m "feat(analytics): nearest-rank 분위수 요약 헬퍼

장비별 뷰가 배지 임계값을 '분위수 꼬리 AND 절대 기준'으로 판정합니다.
분포 요약을 응답에 실어야 사무실에서 API 한 번 호출로 절대 상수를 맞출
수 있습니다. nearest-rank라서 결과가 항상 실제 표본값이고 단조가 정의상
보장됩니다."
```

---

### Task 4: `/equipments` 엔드포인트

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/contracts.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/data.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/routes.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py`

**Interfaces:**
- Consumes: Task 3의 `percentile_summary`, Task 2의 `_filter_rows`
- Produces:
  - `contracts.TAT_INDEX_MIN_SAMPLE = 12`
  - `contracts.EquipmentRow`, `contracts.FleetReference`, `contracts.EquipmentsPayload`
  - `data.get_equipments(tool_type, fab_names, start_date, end_date) -> EquipmentsPayload`
  - 라우트 `GET /<tool_slug>/recipe-tat/equipments`

- [ ] **Step 1: 계약 정의**

`back_dev_home/ebeam/hitachi/recipe_tat/contracts.py`의 `__all__`에 `"EquipmentRow"`, `"FleetReference"`, `"EquipmentsPayload"`, `"TAT_INDEX_MIN_SAMPLE"`를 더하고 파일 끝에 추가:

```python
# 이 미만의 실행 수를 가진 장비는 tat_index 가 None 입니다. 3건짜리 장비의
# 지수는 신호가 아니라 잡음이고, 잡음에 경고 배지를 다는 순간 화면 전체의
# 신뢰가 무너집니다.
# OFFICE-VERIFY — 실 플릿의 장비당 실행 수 분포를 보고 조정합니다.
TAT_INDEX_MIN_SAMPLE = 12


class EquipmentRow(TypedDict):
    eqp_id: str
    fab_name: str
    eqp_model_cd: str
    # 표시용입니다. 신호 판정에는 쓰지 않습니다 — 가동률은 "얼마나 바빴는가"
    # 이지 "몇 번 돌았는가"가 아니라서, 긴 레시피를 도는 장비가 실행 수만
    # 보면 저사용으로 오진됩니다.
    exec_count: int
    total_meastime: int
    avg_meastime: float
    recipe_count: int
    top_recipe: str | None
    top_recipe_share: float
    # 실제 총 TAT / 이 장비의 레시피 구성이라면 걸렸어야 할 TAT.
    # 1.25 = 같은 일을 25 % 더 오래 함. 표본 미달이면 None.
    tat_index: float | None
    # 절대값: total_meastime / 조회 기간 총 초. **MES 가동률이 아닙니다** —
    # meastime 합이라 로딩·대기·PM이 빠져 있어 실제 가동률보다 낮게 읽힙니다.
    occupancy: float
    # 상대값: total_meastime / 플릿 중앙값
    usage_ratio: float


class FleetReference(TypedDict):
    tool_count: int
    total_executions: int
    total_meastime: int
    window_seconds: int
    median_total_meastime: float
    median_recipe_count: float
    min_sample: int
    # 배지 임계값을 사무실에서 조정하기 위한 분포 요약.
    # 키: "usage_ratio" | "tat_index" | "occupancy" | "recipe_count"
    # 값: {"p10","p25","p50","p75","p90"}. tat_index 는 None 인 장비를 제외하고
    # 계산하며, 대상 장비가 없으면 빈 dict.
    percentiles: dict[str, dict[str, float]]


class EquipmentsPayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    fleet: FleetReference
    equipments: list[EquipmentRow]
```

- [ ] **Step 2: 실패 테스트 작성**

`back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py`에 `EquipmentsPayload`, `TAT_INDEX_MIN_SAMPLE` import를 더하고 추가:

```python
def test_get_equipments_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    assert_matches(payload, EquipmentsPayload)


def test_get_equipments_is_sorted_by_total_meastime_desc():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    totals = [row["total_meastime"] for row in rows]
    assert totals == sorted(totals, reverse=True)


def test_get_equipments_totals_agree_with_summary():
    # 같은 범위를 두 엔드포인트가 다르게 집계하면 사용자는 어느 쪽도
    # 믿지 못합니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    summary = data.get_summary(tool_type, fab_names, start_date, end_date, lot_cd=None)
    assert sum(r["exec_count"] for r in payload["equipments"]) == summary["total_executions"]
    assert sum(r["total_meastime"] for r in payload["equipments"]) == summary["total_tat_seconds"]


def test_get_equipments_tat_index_is_none_below_the_sample_floor():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    for row in rows:
        if row["exec_count"] < TAT_INDEX_MIN_SAMPLE:
            assert row["tat_index"] is None
        else:
            assert row["tat_index"] is not None and row["tat_index"] > 0


def test_get_equipments_occupancy_matches_the_window():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    # 포함 일수 × 86400 — start/end 양 끝을 모두 포함합니다.
    assert payload["fleet"]["window_seconds"] == (DEFAULT_DAYS + 1) * 86400
    for row in payload["equipments"]:
        expected = row["total_meastime"] / payload["fleet"]["window_seconds"]
        assert abs(row["occupancy"] - expected) < 1e-9


def test_get_equipments_usage_ratio_follows_time_not_count():
    # 실행이 적어도 긴 레시피를 도는 장비는 놀고 있지 않습니다. usage_ratio가
    # 실행 수를 따라가면 그런 장비를 저사용으로 오진합니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    if len(rows) < 2:
        return
    by_time = sorted(rows, key=lambda r: r["total_meastime"], reverse=True)
    ratios = [r["usage_ratio"] for r in by_time]
    assert ratios == sorted(ratios, reverse=True)


def test_get_equipments_percentiles_cover_every_metric():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipments(tool_type, fab_names, start_date, end_date)
    percentiles = payload["fleet"]["percentiles"]
    for metric in ("usage_ratio", "tat_index", "occupancy", "recipe_count"):
        assert metric in percentiles
        summary = percentiles[metric]
        if not summary:
            continue
        values = [summary[key] for key in ("p10", "p25", "p50", "p75", "p90")]
        assert values == sorted(values)


def test_get_equipments_is_empty_outside_the_data_window():
    # 빈 범위: 목록도 분위수도 비고, 0으로 나누지 않습니다.
    payload = data.get_equipments("cd-sem", None, "1990-01-01", "1990-01-02")
    assert payload["equipments"] == []
    assert payload["fleet"]["tool_count"] == 0
    assert payload["fleet"]["percentiles"] == {
        "usage_ratio": {}, "tat_index": {}, "occupancy": {}, "recipe_count": {}
    }


def test_get_equipments_mock_exercises_every_badge_state():
    # mock이 UI의 모든 상태를 실제로 만들어내지 못하면 홈에서 배지를 검증할
    # 방법이 없습니다. R3 / cd-sem 기본 조회에 각 상태가 1대 이상 있어야
    # 합니다.
    if get_data_provider("recipe_tat") != "mock":
        return
    anchor = data.get_anchor_time().date()
    payload = data.get_equipments(
        "cd-sem", ("R3",), (anchor - timedelta(days=DEFAULT_DAYS)).isoformat(),
        anchor.isoformat()
    )
    rows = payload["equipments"]
    indexed = [r for r in rows if r["tat_index"] is not None]
    assert any(r["tat_index"] is None for r in rows), "표본 미달 장비가 없습니다"
    assert max(r["tat_index"] for r in indexed) > 1.05, "느린 장비가 없습니다"
    assert min(r["usage_ratio"] for r in rows) < 0.85, "저사용 장비가 없습니다"
    assert max(r["top_recipe_share"] for r in rows) >= 0.50, "편중 장비가 없습니다"
```

- [ ] **Step 3: 실패 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat -q -k equipments`

Expected: 전부 FAIL — `AttributeError: module ... has no attribute 'get_equipments'`

- [ ] **Step 4: mock provider 구현**

`back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py`의 `__all__`에 `"get_equipments"`를 더하고, import에 `percentile_summary`와 새 계약 타입들을 더한 뒤 추가:

```python
def _window_seconds(start_date: str | None, end_date: str | None) -> int:
    """조회 기간의 총 초. 양 끝 날짜를 모두 포함합니다(필터와 같은 규칙)."""
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start is None or end is None or end < start:
        return 0
    return ((end - start).days + 1) * 86400


def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None
) -> EquipmentsPayload:
    """장비별 집계 + 배지 판정을 위한 플릿 분포 요약.

    `tat_index`는 간접표준화입니다: 실제 총 TAT을, 이 장비의 레시피 구성이면
    걸렸어야 할 TAT(레시피별 플릿 평균 × 이 장비의 실행 수)으로 나눕니다.
    단순 평균 TAT으로 장비를 줄세우면 QC만 도는 장비가 저절로 빠른 장비가
    되고 ADI를 많이 도는 장비가 느린 장비가 됩니다 — 장비 상태가 아니라
    일감의 종류를 잰 것입니다.

    어떤 레시피를 장비 한 대만 돌았다면 그 레시피의 플릿 평균이 곧 그 장비의
    평균이라 해당 항이 정확히 1.0을 기여합니다. 비교 정보가 없는 일감은
    지수를 1.0 쪽으로 희석시킬 뿐 없는 경보를 만들지 않습니다 — 의도된
    성질입니다.
    """
    rows = _filter_rows(tool_type, fab_names, start_date, end_date)

    # (eqp_id, full_name) 격자 하나로 모든 지표가 나옵니다.
    per_tool: dict[str, dict] = {}
    per_recipe: dict[str, dict] = {}
    for row in rows:
        eqp_id = row["eqp_id"]
        full_name = row["full_name"]
        tool = per_tool.setdefault(eqp_id, {
            "eqp_id": eqp_id,
            "fab_name": row["fab_name"],
            "eqp_model_cd": row["eqp_model_cd"],
            "exec_count": 0,
            "total_meastime": 0,
            "recipes": {}
        })
        tool["exec_count"] += 1
        tool["total_meastime"] += row["meastime"]
        cell = tool["recipes"].setdefault(full_name, {"count": 0, "tat": 0})
        cell["count"] += 1
        cell["tat"] += row["meastime"]

        recipe = per_recipe.setdefault(full_name, {"count": 0, "tat": 0})
        recipe["count"] += 1
        recipe["tat"] += row["meastime"]

    # base(r) = 레시피 r의 플릿 평균 meastime
    base = {
        name: agg["tat"] / agg["count"]
        for name, agg in per_recipe.items() if agg["count"]
    }

    window = _window_seconds(start_date, end_date)
    totals = sorted(tool["total_meastime"] for tool in per_tool.values())
    median_total = float(statistics.median(totals)) if totals else 0.0

    equipments: list[EquipmentRow] = []
    for tool in per_tool.values():
        exec_count = tool["exec_count"]
        total = tool["total_meastime"]
        cells = tool["recipes"]

        top_name, top_cell = max(
            cells.items(), key=lambda item: item[1]["tat"], default=(None, None)
        )
        expected = sum(cell["count"] * base[name] for name, cell in cells.items())

        equipments.append({
            "eqp_id": tool["eqp_id"],
            "fab_name": tool["fab_name"],
            "eqp_model_cd": tool["eqp_model_cd"],
            "exec_count": exec_count,
            "total_meastime": total,
            "avg_meastime": round(total / exec_count, 2) if exec_count else 0.0,
            "recipe_count": len(cells),
            "top_recipe": top_name,
            "top_recipe_share": round(top_cell["tat"] / total, 4) if total and top_cell else 0.0,
            "tat_index": (
                round(total / expected, 4)
                if exec_count >= TAT_INDEX_MIN_SAMPLE and expected else None
            ),
            "occupancy": round(total / window, 6) if window else 0.0,
            "usage_ratio": round(total / median_total, 4) if median_total else 0.0
        })

    equipments.sort(key=lambda row: (row["total_meastime"], row["exec_count"]), reverse=True)

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "fleet": {
            "tool_count": len(equipments),
            "total_executions": sum(row["exec_count"] for row in equipments),
            "total_meastime": sum(row["total_meastime"] for row in equipments),
            "window_seconds": window,
            "median_total_meastime": median_total,
            "median_recipe_count": float(
                statistics.median([row["recipe_count"] for row in equipments])
            ) if equipments else 0.0,
            "min_sample": TAT_INDEX_MIN_SAMPLE,
            "percentiles": {
                "usage_ratio": percentile_summary(r["usage_ratio"] for r in equipments),
                "occupancy": percentile_summary(r["occupancy"] for r in equipments),
                "recipe_count": percentile_summary(r["recipe_count"] for r in equipments),
                # None 장비는 제외 — 표본 미달은 "느리지 않다"가 아니라
                # "모른다"이고, 0으로 채우면 p10이 통째로 무너집니다.
                "tat_index": percentile_summary(
                    r["tat_index"] for r in equipments if r["tat_index"] is not None
                )
            }
        },
        "equipments": equipments
    }
```

파일 상단에 `import statistics`를 추가합니다.

- [ ] **Step 5: dispatcher + 라우트 추가**

`back_dev_home/ebeam/hitachi/recipe_tat/data.py`의 `__all__`에 `"get_equipments"`를 더하고 파일 끝에 추가:

```python
def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> EquipmentsPayload:
    return _provider().get_equipments(tool_type, fab_names, start_date, end_date)
```

import 블록에 `EquipmentsPayload`를 더합니다.

`back_dev_home/ebeam/hitachi/recipe_tat/routes.py`의 import에 `get_equipments`를 더하고 파일 끝에 추가:

```python
@bp.get("/<tool_slug>/recipe-tat/equipments")
def recipe_tat_equipments(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    # /devices 와 같은 이유로 lot_cd 를 받지 않습니다: 이 엔드포인트는 범위
    # 안에 어떤 장비가 있는지에 대한 진실이라 선택으로 걸러지면 안 됩니다.
    return jsonify(get_equipments(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
    ))
```

- [ ] **Step 6: 통과 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat -q`

Expected: 전부 PASS

- [ ] **Step 7: HTTP 확인**

Flask를 띄우고(`.venv/bin/python index.py`) 다른 터미널에서:

```bash
curl -s --cookie "LASTUSER=local-dev" \
  "http://localhost:5050/api/cdsem/recipe-tat/equipments?fab_name=R3" \
  | .venv/bin/python -m json.tool | head -40
curl -s --cookie "LASTUSER=local-dev" \
  "http://localhost:5050/api/nope/recipe-tat/equipments" -o /dev/null -w "%{http_code}\n"
```

Expected: 첫 호출은 `fleet.percentiles`가 채워진 payload, 두 번째는 `400`.
`/api/*`는 5초에 20건 제한이니 curl을 몰아치지 마세요.

- [ ] **Step 8: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/recipe_tat/contracts.py \
        back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_tat/data.py \
        back_dev_home/ebeam/hitachi/recipe_tat/routes.py \
        back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py
git commit -m "feat(recipe-tat): GET /<slug>/recipe-tat/equipments

장비(eqp_id)별 측정 부하·소요 시간·레시피 커버리지 집계입니다.

tat_index는 간접표준화입니다 — 실제 총 TAT을 '이 장비의 레시피 구성이면
걸렸어야 할 TAT'으로 나눕니다. 단순 평균 TAT으로 줄세우면 QC만 도는
장비가 저절로 빠른 장비가 되고 ADI를 많이 도는 장비가 느린 장비가 되어,
장비 상태가 아니라 일감의 종류를 재게 됩니다. 표본 12건 미만은 None.

usage_ratio는 실행 횟수가 아니라 측정 시간 기준입니다. 가동률은 '얼마나
바빴는가'이지 '몇 번 돌았는가'가 아니라서, 긴 레시피를 도는 장비가 실행
수만 보면 저사용으로 오진됩니다.

fleet.percentiles를 함께 내려보냅니다. 배지 임계값을 사무실에서 API 한 번
호출로 조정하기 위해서입니다."
```

---

### Task 5: `/equipment-compare` 엔드포인트

기존 `/ranking`·`/daily-trend`에 `eqp_id`를 붙이지 않는 이유: 5대 선택 시 요청이 10건인데 `/api/*`는 5초에 20건 제한이라 체크박스 클릭 한 번이 예산의 절반을 씁니다. 그리고 레시피 비교표는 선택 장비들의 레시피 **합집합에 0을 채운** 형태여야 하는데, 서버에서 한 번 만드는 편이 클라이언트에서 5개 응답을 조인하는 것보다 단순합니다.

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/_analytics_routes.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/contracts.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/data.py`, `routes.py`
- Test: `back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py`

**Interfaces:**
- Consumes: Task 4의 `_filter_rows`, `_window_seconds`
- Produces:
  - `_analytics_routes.MAX_EQP_IDS = 5`, `AnalyticsRequestScope.eqp_ids: tuple[str, ...]`
  - `contracts.EquipmentTrendSeries`, `EquipmentRecipeCell`, `EquipmentRecipeRow`, `EquipmentComparePayload`
  - `data.get_equipment_compare(tool_type, fab_names, start_date, end_date, eqp_ids) -> EquipmentComparePayload`
  - 라우트 `GET /<tool_slug>/recipe-tat/equipment-compare`

- [ ] **Step 1: 계약 정의**

`recipe_tat/contracts.py`의 `__all__`에 네 이름을 더하고 파일 끝에 추가:

```python
class EquipmentTrendSeries(TypedDict):
    eqp_id: str
    points: list[DailyTrendPoint]


class EquipmentRecipeCell(TypedDict):
    eqp_id: str
    meas_counts: int
    total_meastime: int
    avg_meastime: float


class EquipmentRecipeRow(TypedDict):
    class_name: str
    recipe_name: str
    full_name: str
    # 선택된 장비 전체의 합. 표 정렬 기준입니다.
    total_meastime: int
    # 선택된 장비 수만큼, 요청 순서 그대로. 그 장비가 이 레시피를 돌지
    # 않았으면 0으로 채웁니다 — 열이 밀리면 비교표가 거짓말을 합니다.
    cells: list[EquipmentRecipeCell]


class EquipmentComparePayload(TypedDict):
    tool_type: ToolType
    fab_names: list[str]
    start_date: str | None
    end_date: str | None
    # 실제로 사용된 목록(상한 적용 후). 절단을 조용히 하지 않기 위한 에코입니다.
    eqp_ids: list[str]
    trends: list[EquipmentTrendSeries]
    recipes: list[EquipmentRecipeRow]
```

- [ ] **Step 2: 실패 테스트 작성**

`recipe_tat/tests/test_contract.py`에 추가 (import에 `EquipmentComparePayload` 추가):

```python
def _two_busiest_eqp_ids():
    tool_type, fab_names, start_date, end_date = _default_scope()
    rows = data.get_equipments(tool_type, fab_names, start_date, end_date)["equipments"]
    return tuple(row["eqp_id"] for row in rows[:2])


def test_get_equipment_compare_matches_contract():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, _two_busiest_eqp_ids()
    )
    assert_matches(payload, EquipmentComparePayload)


def test_get_equipment_compare_zero_fills_every_cell():
    # 모든 행의 cells 길이가 선택 장비 수와 같아야 합니다. 짧으면 프론트엔드
    # 열이 밀려서 다른 장비의 숫자를 보여주게 됩니다.
    tool_type, fab_names, start_date, end_date = _default_scope()
    eqp_ids = _two_busiest_eqp_ids()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
    for row in payload["recipes"]:
        assert [cell["eqp_id"] for cell in row["cells"]] == list(eqp_ids)


def test_get_equipment_compare_trends_cover_the_whole_range():
    tool_type, fab_names, start_date, end_date = _default_scope()
    eqp_ids = _two_busiest_eqp_ids()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
    assert [series["eqp_id"] for series in payload["trends"]] == list(eqp_ids)
    for series in payload["trends"]:
        dates = [point["date"] for point in series["points"]]
        assert dates[0] == start_date and dates[-1] == end_date
        assert dates == sorted(dates)
        assert len(dates) == DEFAULT_DAYS + 1


def test_get_equipment_compare_recipes_sorted_by_total_desc():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipment_compare(
        tool_type, fab_names, start_date, end_date, _two_busiest_eqp_ids()
    )
    totals = [row["total_meastime"] for row in payload["recipes"]]
    assert totals == sorted(totals, reverse=True)


def test_get_equipment_compare_with_no_eqp_ids_is_empty():
    tool_type, fab_names, start_date, end_date = _default_scope()
    payload = data.get_equipment_compare(tool_type, fab_names, start_date, end_date, ())
    assert payload["eqp_ids"] == []
    assert payload["trends"] == []
    assert payload["recipes"] == []


def test_request_scope_caps_and_echoes_eqp_ids():
    # 절단을 조용히 하지 않습니다 — 6대를 보내면 5대만 쓰였다는 사실이
    # 응답에 드러나야 합니다.
    from flask import Flask

    from back_dev_home.ebeam.hitachi._analytics_routes import (
        MAX_EQP_IDS,
        resolve_analytics_scope,
    )

    app = Flask(__name__)
    query = "eqp_id=" + ",".join(f"EQP{n}" for n in range(1, 8))
    with app.test_request_context(f"/?{query}"):
        scope = resolve_analytics_scope("cdsem", data.get_anchor_time())
    assert scope is not None
    assert len(scope.eqp_ids) == MAX_EQP_IDS
    assert scope.eqp_ids == ("EQP1", "EQP2", "EQP3", "EQP4", "EQP5")


def test_request_scope_eqp_ids_default_to_empty():
    from flask import Flask

    from back_dev_home.ebeam.hitachi._analytics_routes import resolve_analytics_scope

    app = Flask(__name__)
    with app.test_request_context("/?fab_name=R3"):
        scope = resolve_analytics_scope("cdsem", data.get_anchor_time())
    assert scope is not None and scope.eqp_ids == ()
```

- [ ] **Step 3: 실패 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/recipe_tat -q -k "compare or scope"`

Expected: 전부 FAIL

- [ ] **Step 4: 요청 파싱 확장**

`back_dev_home/ebeam/hitachi/_analytics_routes.py`:

```python
# equipment-compare 가 한 번에 받는 장비 수 상한. 요청 형태에 관한 값이라
# 계약이 아니라 파서가 소유합니다. fail_issue 도 같은 헬퍼를 쓰지만 이
# 필드를 읽지 않으므로 무해합니다.
MAX_EQP_IDS = 5
```

`AnalyticsRequestScope`에 필드를 더합니다:

```python
    eqp_ids: tuple[str, ...]
```

`resolve_analytics_scope`의 반환에 추가합니다:

```python
        # eqp_id 는 정확 일치 키입니다. fab_name 과 달리 대문자로 정규화하지
        # 않습니다 — 사무실 인덱스의 표기를 그대로 term 조회해야 합니다.
        eqp_ids=tuple(
            part.strip()
            for part in (request.args.get("eqp_id") or "").split(",")
            if part.strip()
        )[:MAX_EQP_IDS],
```

- [ ] **Step 5: mock provider 구현**

`recipe_tat/providers/mock.py`의 `__all__`에 `"get_equipment_compare"`를 더하고 추가:

```python
def _zero_filled_days(start_date: str | None, end_date: str | None) -> list[str]:
    """요청 기간의 모든 날짜. 트렌드 x축이 조용한 날을 건너뛰지 않게 합니다."""
    start = parse_iso_date(start_date)
    end = parse_iso_date(end_date)
    if start is None or end is None or end < start:
        return []
    days: list[str] = []
    cursor = start
    while cursor <= end:
        days.append(cursor.date().isoformat())
        cursor += timedelta(days=1)
    return days


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...]
) -> EquipmentComparePayload:
    """선택된 장비들의 일별 트렌드와 레시피 구성을 한 응답에 담습니다.

    레시피 행은 선택 장비들의 **합집합**이고, 돌지 않은 장비 칸은 0으로
    채웁니다. 클라이언트가 장비별 응답 여러 개를 조인하면 이 합집합과
    0채움을 매번 다시 만들어야 하고, 한 번 어긋나면 열이 밀려 다른 장비의
    숫자를 보여주게 됩니다.
    """
    selected = list(dict.fromkeys(eqp_ids))     # 순서 보존 dedupe
    if not selected:
        return {
            "tool_type": tool_type,
            "fab_names": list(fab_names or []),
            "start_date": start_date,
            "end_date": end_date,
            "eqp_ids": [],
            "trends": [],
            "recipes": []
        }

    wanted = set(selected)
    rows = [
        row for row in _filter_rows(tool_type, fab_names, start_date, end_date)
        if row["eqp_id"] in wanted
    ]

    days = _zero_filled_days(start_date, end_date)
    trend: dict[str, dict[str, dict]] = {
        eqp_id: {day: {"total_meastime": 0, "exec_count": 0} for day in days}
        for eqp_id in selected
    }
    grid: dict[str, dict[str, dict]] = {}

    for row in rows:
        day = row["timestamp"][:10]
        bucket = trend[row["eqp_id"]].get(day)
        if bucket is not None:
            bucket["total_meastime"] += row["meastime"]
            bucket["exec_count"] += 1

        recipe = grid.setdefault(row["full_name"], {
            "class_name": row["class_name"],
            "recipe_name": row["recipe_name"],
            "full_name": row["full_name"],
            "total_meastime": 0,
            "cells": {eqp_id: {"count": 0, "tat": 0} for eqp_id in selected}
        })
        recipe["total_meastime"] += row["meastime"]
        cell = recipe["cells"][row["eqp_id"]]
        cell["count"] += 1
        cell["tat"] += row["meastime"]

    recipes: list[EquipmentRecipeRow] = [
        {
            "class_name": entry["class_name"],
            "recipe_name": entry["recipe_name"],
            "full_name": entry["full_name"],
            "total_meastime": entry["total_meastime"],
            "cells": [
                {
                    "eqp_id": eqp_id,
                    "meas_counts": entry["cells"][eqp_id]["count"],
                    "total_meastime": entry["cells"][eqp_id]["tat"],
                    "avg_meastime": round(
                        entry["cells"][eqp_id]["tat"] / entry["cells"][eqp_id]["count"], 2
                    ) if entry["cells"][eqp_id]["count"] else 0.0
                }
                for eqp_id in selected
            ]
        }
        for entry in sorted(
            grid.values(), key=lambda e: e["total_meastime"], reverse=True
        )
    ]

    return {
        "tool_type": tool_type,
        "fab_names": list(fab_names or []),
        "start_date": start_date,
        "end_date": end_date,
        "eqp_ids": selected,
        "trends": [
            {
                "eqp_id": eqp_id,
                "points": [
                    {
                        "date": day,
                        "total_meastime": trend[eqp_id][day]["total_meastime"],
                        "exec_count": trend[eqp_id][day]["exec_count"]
                    }
                    for day in days
                ]
            }
            for eqp_id in selected
        ],
        "recipes": recipes
    }
```

- [ ] **Step 6: dispatcher + 라우트**

`data.py` (`__all__`과 import에 이름 추가):

```python
def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...],
) -> EquipmentComparePayload:
    return _provider().get_equipment_compare(
        tool_type, fab_names, start_date, end_date, eqp_ids
    )
```

`routes.py`:

```python
@bp.get("/<tool_slug>/recipe-tat/equipment-compare")
def recipe_tat_equipment_compare(tool_slug: str):
    scope = resolve_analytics_scope(tool_slug, get_anchor_time())
    if scope is None:
        return bad_tool_slug_response()

    return jsonify(get_equipment_compare(
        scope.tool_type,
        scope.fab_names or None,
        scope.start_date,
        scope.end_date,
        scope.eqp_ids,
    ))
```

- [ ] **Step 7: 통과 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi -q`

Expected: 전부 PASS (`fail_issue`도 같은 파서를 쓰므로 함께 확인)

- [ ] **Step 8: 커밋**

```bash
git add back_dev_home/ebeam/hitachi/_analytics_routes.py \
        back_dev_home/ebeam/hitachi/recipe_tat/contracts.py \
        back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_tat/data.py \
        back_dev_home/ebeam/hitachi/recipe_tat/routes.py \
        back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py
git commit -m "feat(recipe-tat): GET /<slug>/recipe-tat/equipment-compare

선택한 장비들(최대 5대)의 일별 트렌드와 레시피 구성을 한 응답에 담습니다.

기존 /ranking·/daily-trend에 eqp_id를 붙이지 않은 이유: 5대 선택 시
요청이 10건인데 /api/*는 5초에 20건 제한이라 클릭 한 번이 예산의 절반을
씁니다. 그리고 레시피 비교표는 선택 장비들의 합집합에 0을 채운 형태여야
하는데, 열이 한 번 밀리면 다른 장비의 숫자를 보여주므로 서버에서 한 번
만드는 편이 안전합니다.

상한 절단은 응답의 eqp_ids 에코로 드러냅니다."
```

---

### Task 6: office 어댑터 템플릿

**Files:**
- Modify: `back_dev_home/ebeam/hitachi/_office_meas_hist.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py`
- Modify: `back_dev_home/ebeam/hitachi/recipe_tat/MIGRATION.md`
- Test: `back_dev_home/ebeam/hitachi/tests/test_office_meas_hist.py` (생성)

**Interfaces:**
- Consumes: Task 4·5의 계약
- Produces: `composite_buckets(index, field, sub_aggs, query_body)`가 `field`로 `str` 또는 `Sequence[tuple[str, str]]`(이름, 필드)를 받습니다. `str`이면 기존과 완전히 동일하게 동작합니다.

- [ ] **Step 1: 하위호환 실패 테스트 작성**

`back_dev_home/ebeam/hitachi/tests/test_office_meas_hist.py`:

```python
"""composite_buckets 의 소스 빌더 단위 테스트.

OpenSearch 없이 순수 함수만 검사합니다. 기존 `field: str` 호출을 깨면
사무실의 아직 갱신되지 않은 office.py 사본들이 import 에러로 앱 팩토리
전체를 죽입니다 — 그래서 하위호환이 테스트로 고정되어야 합니다.
"""

from back_dev_home.ebeam.hitachi._office_meas_hist import _composite_sources


def test_single_field_keeps_the_legacy_group_source():
    assert _composite_sources("full_name.keyword") == [
        {"group": {"terms": {"field": "full_name.keyword"}}}
    ]


def test_multiple_sources_preserve_order_and_names():
    assert _composite_sources([
        ("eqp", "eqp_id.keyword"),
        ("fab", "fab_name.keyword"),
    ]) == [
        {"eqp": {"terms": {"field": "eqp_id.keyword"}}},
        {"fab": {"terms": {"field": "fab_name.keyword"}}},
    ]
```

- [ ] **Step 2: 실패 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi/tests/test_office_meas_hist.py -v`

Expected: FAIL — `ImportError: cannot import name '_composite_sources'`

- [ ] **Step 3: 다중 소스 지원 추가**

`back_dev_home/ebeam/hitachi/_office_meas_hist.py`에 추가:

```python
def _composite_sources(field: str | Sequence[tuple[str, str]]) -> list[dict[str, Any]]:
    """composite 의 sources 절을 만듭니다.

    문자열 하나면 예전과 똑같이 `group` 이라는 이름의 소스 하나입니다 —
    기존 호출자(사무실의 갱신되지 않은 office.py 포함)가 그대로 동작해야
    합니다. (이름, 필드) 목록을 주면 그 순서대로 다중 소스가 됩니다.
    """
    if isinstance(field, str):
        return [{"group": {"terms": {"field": field}}}]
    return [{name: {"terms": {"field": path}}} for name, path in field]
```

`composite_buckets`의 시그니처와 본문을 고칩니다:

```python
def composite_buckets(
    index: str,
    field: str | Sequence[tuple[str, str]],
    sub_aggs: dict[str, Any],
    query_body: dict[str, Any] | None,
) -> list[dict[str, Any]]:
```

```python
        composite: dict[str, Any] = {
            "size": _COMPOSITE_PAGE_SIZE,
            "sources": _composite_sources(field),
        }
```

docstring 첫 줄을 고칩니다: `"""Every bucket for a terms/composite grouping via a paginated composite aggregation.` 그리고 마지막 문단에 한 줄 추가:

```text
    ``field`` 가 문자열이면 버킷 키는 ``key.group`` 입니다(기존 동작).
    (이름, 필드) 목록을 주면 ``key.<이름>`` 으로 각각 접근합니다.
```

`typing` import에 `Sequence`가 없으면 더합니다.

- [ ] **Step 4: 통과 확인**

Run: `.venv/bin/python -m pytest back_dev_home/ebeam/hitachi -q`

Expected: 전부 PASS. 기존 office_example 들의 `composite_buckets(..., _FULL_KW, ...)` 호출은 변경 없이 그대로 동작해야 합니다.

- [ ] **Step 5: office 어댑터 템플릿 작성**

`recipe_tat/providers/office_example.py`의 `__all__`에 두 이름을 더하고, import에 `EQP_MODEL_CD_KW`가 필요하므로 `_office_meas_hist.py`에 먼저 상수를 추가합니다:

```python
EQP_MODEL_CD_KW = "eqp_model_cd.keyword"   # 장비별 뷰의 모델 열. OFFICE-VERIFY:
                                           # meas_hist.txt 는 eqp_model_cd 가 text 라고
                                           # 적고 있으나 .keyword 서브필드 존재는 미확인
```

그리고 `office_example.py` 끝에 추가:

```python
def get_equipments(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
) -> EquipmentsPayload:
    """장비별 집계. composite 한 번으로 표에 필요한 값이 전부 나옵니다.

    소스가 4개인 이유: fab_name 과 eqp_model_cd 는 eqp_id 에 함수 종속이라
    버킷 수를 곱하지 않고(장비 수 × 레시피 수 그대로), 대신 top_hits 서브집계
    없이 표의 fab/model 열을 채울 수 있습니다.

    지수·중앙값·분위수는 파이썬에서 파생합니다 — mock 과 같은 코드 경로를
    타야 두 provider 의 숫자가 어긋나지 않습니다.
    """
    clauses = _filter_clauses(fab_names, start_date, end_date)
    buckets = _composite_buckets(
        _INDEX[tool_type],
        [
            ("eqp", _EQP_KW),
            ("fab", _FAB_KW),
            ("model", _EQP_MODEL_KW),
            ("recipe", _FULL_KW),
        ],
        {"tat": {"sum": {"field": _MEAS_F}}},
        _query(clauses),
    )

    grid: list[tuple[str, str, str, str, int, int]] = [
        (
            _text(b["key"]["eqp"]),
            _text(b["key"]["fab"]),
            _text(b["key"]["model"]),
            _text(b["key"]["recipe"]),
            int(b["doc_count"]),
            int(b.get("tat", {}).get("value") or 0),
        )
        for b in buckets
    ]
    return build_equipments_payload(
        tool_type, fab_names, start_date, end_date, grid
    )


def get_equipment_compare(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: tuple[str, ...],
) -> EquipmentComparePayload:
    """선택 장비의 일별 트렌드 + 레시피 격자. 집계 2개, 요청 1건."""
    selected = list(dict.fromkeys(eqp_ids))
    if not selected:
        return build_equipment_compare_payload(
            tool_type, fab_names, start_date, end_date, [], [], []
        )

    clauses = _filter_clauses(fab_names, start_date, end_date)
    clauses.append({"terms": {_EQP_KW: selected}})

    histogram: dict[str, Any] = {
        "field": _TIME_F,
        "calendar_interval": "day",
        "format": "yyyy-MM-dd",
        "min_doc_count": 0,
    }
    if start_date and end_date:
        histogram["extended_bounds"] = {"min": start_date, "max": end_date}

    trend_result = _aggregate(
        _INDEX[tool_type],
        {
            "by_eqp": {
                "terms": {"field": _EQP_KW, "size": len(selected)},
                "aggs": {
                    "by_day": {
                        "date_histogram": histogram,
                        "aggs": {"tat": {"sum": {"field": _MEAS_F}}},
                    }
                },
            }
        },
        _query(clauses),
    )
    trend_rows = [
        (
            _text(eqp_bucket["key"]),
            str(day_bucket["key_as_string"]),
            int(day_bucket.get("tat", {}).get("value") or 0),
            int(day_bucket["doc_count"]),
        )
        for eqp_bucket in trend_result.get("by_eqp", {}).get("buckets", [])
        for day_bucket in eqp_bucket.get("by_day", {}).get("buckets", [])
    ]

    recipe_buckets = _composite_buckets(
        _INDEX[tool_type],
        [("eqp", _EQP_KW), ("recipe", _FULL_KW)],
        {"tat": {"sum": {"field": _MEAS_F}}},
        _query(clauses),
    )
    recipe_rows = [
        (
            _text(b["key"]["eqp"]),
            _text(b["key"]["recipe"]),
            int(b["doc_count"]),
            int(b.get("tat", {}).get("value") or 0),
        )
        for b in recipe_buckets
    ]

    return build_equipment_compare_payload(
        tool_type, fab_names, start_date, end_date, selected, trend_rows, recipe_rows
    )
```

이 템플릿이 부르는 `build_equipments_payload` / `build_equipment_compare_payload`는 **mock과 office가 공유해야 하는 순수 조립 함수**입니다. `recipe_tat/providers/_shape.py`를 새로 만들어 거기 두고, Task 4·5에서 mock에 쓴 조립 로직을 이 함수로 옮긴 뒤 mock은 격자를 만들어 넘기기만 하게 리팩터링합니다. 두 provider가 지수·중앙값·분위수를 각자 계산하면 언젠가 어긋납니다.

시그니처:

```python
def build_equipments_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    # (eqp_id, fab_name, eqp_model_cd, full_name, meas_counts, total_meastime)
    grid: Sequence[tuple[str, str, str, str, int, int]],
) -> EquipmentsPayload: ...


def build_equipment_compare_payload(
    tool_type: ToolType,
    fab_names: tuple[str, ...] | None,
    start_date: str | None,
    end_date: str | None,
    eqp_ids: Sequence[str],
    # (eqp_id, date, total_meastime, exec_count)
    trend_rows: Sequence[tuple[str, str, int, int]],
    # (eqp_id, full_name, meas_counts, total_meastime)
    recipe_rows: Sequence[tuple[str, str, int, int]],
) -> EquipmentComparePayload: ...
```

`full_name`에서 `class_name`/`recipe_name`을 되살릴 때는 첫 `/`로 나눕니다 (`full_name = f"{class_name}/{recipe_name}"`).

- [ ] **Step 6: 계약 게이트가 두 provider를 모두 검사하는지 확인**

기존 `test_office_get_meas_hist_is_intentionally_disconnected`와 같은 방식으로, `office_example`이 import 가능하고 새 함수 두 개를 노출하는지 고정합니다:

```python
def test_office_example_exposes_the_equipment_endpoints():
    import pytest

    office_example = pytest.importorskip(
        "back_dev_home.ebeam.hitachi.recipe_tat.providers.office_example"
    )
    assert callable(office_example.get_equipments)
    assert callable(office_example.get_equipment_compare)
```

- [ ] **Step 7: MIGRATION.md 갱신**

`recipe_tat/MIGRATION.md`에 새 엔드포인트 2개의 집계 모양과 사무실 확인 절차를 추가합니다:

```markdown
## 장비별 뷰 (2026-08-07 추가)

| 엔드포인트 | 집계 |
| --- | --- |
| `/equipments` | composite `[eqp_id, fab_name, eqp_model_cd, full_name]` + `sum(meastime)` |
| `/equipment-compare` | `terms(eqp_id) → date_histogram(day, extended_bounds)` + composite `[eqp_id, full_name]` |

버킷 수는 대략 (장비 수 × 레시피 수)입니다. `fab_name`과 `eqp_model_cd`는
`eqp_id`에 함수 종속이라 곱해지지 않습니다.

**OFFICE-VERIFY 두 가지**

1. `eqp_model_cd.keyword` 서브필드 존재. `meas_hist.txt`는 `eqp_model_cd`가
   `text`라고만 적고 있습니다. 없으면 `_EQP_MODEL_KW`를 `eqp_model_cd`로
   바꾸거나 `top_hits`로 대체합니다.
2. 배지 임계값. 첫 실행에서 아래를 호출하고 `fleet.percentiles`를 읽어
   `front-dev-home/app/utils/equipmentSignals.ts`의 상수 네 개를 맞춘 뒤
   `OFFICE-VERIFY` 주석을 `office 확인 YYYY-MM-DD`로 바꿉니다.

    curl -s "$BASE/api/cdsem/recipe-tat/equipments?start_date=…&end_date=…" | python -m json.tool

   `occupancy`의 절대 수준을 MES 가동률과 나란히 놓고 격차를
   `docs/datatables/meas_hist.txt`에 기록합니다 — 이 값은 측정 점유율이지
   장비 가동률이 아닙니다(로딩·대기·PM 제외).
```

- [ ] **Step 8: 전체 스위트 + 커밋**

```bash
.venv/bin/python -m pytest -q
npm run lint:md
git add back_dev_home/ebeam/hitachi/_office_meas_hist.py \
        back_dev_home/ebeam/hitachi/tests/test_office_meas_hist.py \
        back_dev_home/ebeam/hitachi/recipe_tat/providers/office_example.py \
        back_dev_home/ebeam/hitachi/recipe_tat/providers/_shape.py \
        back_dev_home/ebeam/hitachi/recipe_tat/providers/mock.py \
        back_dev_home/ebeam/hitachi/recipe_tat/tests/test_contract.py \
        back_dev_home/ebeam/hitachi/recipe_tat/MIGRATION.md
git commit -m "feat(recipe-tat/office): 장비별 집계 템플릿 + 다중 소스 composite

composite_buckets가 (이름, 필드) 목록을 받도록 확장합니다. 문자열 하나를
넘기는 기존 호출은 완전히 동일하게 동작합니다 — 사무실에는 아직 갱신되지
않은 office.py 사본들이 있고 import 에러 하나가 앱 팩토리 전체를 죽입니다.

payload 조립을 providers/_shape.py로 빼서 mock과 office가 지수·중앙값·
분위수를 같은 코드로 계산하게 합니다. 각자 계산하면 언젠가 어긋납니다.

OFFICE-VERIFY 2건을 MIGRATION.md에 남겼습니다: eqp_model_cd.keyword 존재
여부, 그리고 fleet.percentiles로 배지 임계값 조정."
```

---

### Task 7: 배지 판정 순수 함수

**Files:**
- Create: `front-dev-home/app/utils/equipmentSignals.ts`
- Test: `front-dev-home/app/utils/equipmentSignals.test.ts`

**Interfaces:**
- Consumes: 없음 (순수 함수)
- Produces:
  - `EquipmentSignalInput` — `{ tat_index: number | null, usage_ratio: number, recipe_count: number, top_recipe_share: number }`
  - `FleetPercentiles = Record<string, Record<string, number>>`
  - `EquipmentSignal = 'slow' | 'fast' | 'underused' | 'narrow'`
  - `equipmentSignals(row, percentiles): EquipmentSignal[]`
  - `SIGNAL_META: Record<EquipmentSignal, { label: string, tone: 'warn' | 'info' }>`

- [ ] **Step 1: 실패 테스트 작성**

`front-dev-home/app/utils/equipmentSignals.test.ts`:

```ts
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  equipmentSignals,
  SIGNAL_META,
  type FleetPercentiles
} from './equipmentSignals.ts'

// 촘촘한 플릿을 흉내낸 분위수. 실 플릿은 가동률이 대부분 90% 이상으로
// 몰려 있다는 현업 확인을 반영합니다.
const percentiles: FleetPercentiles = {
  usage_ratio: { p10: 0.82, p25: 0.94, p50: 1.00, p75: 1.06, p90: 1.14 },
  tat_index: { p10: 0.94, p25: 0.97, p50: 1.00, p75: 1.04, p90: 1.13 },
  recipe_count: { p10: 4, p25: 12, p50: 20, p75: 28, p90: 34 }
}

const healthy = { tat_index: 1.0, usage_ratio: 1.0, recipe_count: 20, top_recipe_share: 0.2 }

test('건강한 장비에는 배지를 달지 않는다', () => {
  assert.deepEqual(equipmentSignals(healthy, percentiles), [])
})

test('tat_index가 null이면 느림/빠름 판정을 하지 않는다', () => {
  // 표본 미달은 "느리지 않다"가 아니라 "모른다"입니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: null }, percentiles),
    []
  )
})

test('분위수 꼬리지만 절대 기준을 넘지 않으면 배지가 없다', () => {
  // 완전히 건강한 플릿에서도 누군가는 하위 10%입니다. 그것만으로는
  // 문제가 아닙니다.
  assert.deepEqual(
    equipmentSignals({ ...healthy, usage_ratio: 0.82 }, percentiles),
    []
  )
})

test('절대 기준을 넘어도 분위수 꼬리가 아니면 배지가 없다', () => {
  // 상수가 실 분포와 어긋났을 때 전부 경고가 되는 것을 막습니다.
  const wide: FleetPercentiles = {
    ...percentiles,
    usage_ratio: { p10: 0.30, p25: 0.50, p50: 1.00, p75: 1.50, p90: 2.00 }
  }
  assert.deepEqual(equipmentSignals({ ...healthy, usage_ratio: 0.80 }, wide), [])
})

test('꼬리이면서 절대 기준을 넘으면 저사용', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, usage_ratio: 0.70 }, percentiles),
    ['underused']
  )
})

test('꼬리이면서 절대 기준을 넘으면 느림', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 1.22 }, percentiles),
    ['slow']
  )
})

test('빠름은 하위 꼬리 + 절대 기준', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, tat_index: 0.90 }, percentiles),
    ['fast']
  )
})

test('편중은 레시피 수 꼬리와 상위 레시피 비중을 모두 요구한다', () => {
  assert.deepEqual(
    equipmentSignals({ ...healthy, recipe_count: 3, top_recipe_share: 0.2 }, percentiles),
    []
  )
  assert.deepEqual(
    equipmentSignals({ ...healthy, recipe_count: 3, top_recipe_share: 0.7 }, percentiles),
    ['narrow']
  )
})

test('분위수가 비면 아무 배지도 달지 않는다', () => {
  // 빈 범위 = 판단 근거 없음. 근거 없이 경고하지 않습니다.
  const empty: FleetPercentiles = {
    usage_ratio: {}, tat_index: {}, occupancy: {}, recipe_count: {}
  }
  assert.deepEqual(
    equipmentSignals({ tat_index: 9, usage_ratio: 0.01, recipe_count: 1, top_recipe_share: 1 }, empty),
    []
  )
})

test('여러 신호가 동시에 나올 수 있다', () => {
  assert.deepEqual(
    equipmentSignals(
      { tat_index: 1.30, usage_ratio: 0.60, recipe_count: 2, top_recipe_share: 0.9 },
      percentiles
    ),
    ['underused', 'slow', 'narrow']
  )
})

test('모든 신호에 표시용 메타가 있다', () => {
  for (const signal of ['slow', 'fast', 'underused', 'narrow'] as const) {
    assert.ok(SIGNAL_META[signal].label.length > 0)
  }
})
```

- [ ] **Step 2: 실패 확인**

Run (from `front-dev-home/`): `npm test`

Expected: FAIL — `Cannot find module './equipmentSignals.ts'`

- [ ] **Step 3: 구현**

`front-dev-home/app/utils/equipmentSignals.ts`:

```ts
// 장비별 뷰의 배지 판정. 백엔드는 비율과 분포(분위수)를 계산하고, 여기서는
// "이 값을 경고로 볼 것인가"라는 표시 정책만 결정합니다.
//
// 판정이 분위수 AND 절대 기준인 이유:
//  - 절대 기준만 쓰면, 상수가 실 분포와 어긋나는 순간 전부 정상이거나 전부
//    경고가 됩니다. 실 플릿은 가동률이 대부분 90% 이상으로 촘촘히 몰려
//    있어서(user-confirmed 2026-08-07) 이 위험이 실제로 큽니다.
//  - 분위수만 쓰면, 완벽히 건강한 플릿에서도 항상 하위 10%를 경고합니다.
//    "제일 낮은 장비"와 "문제 있는 장비"는 다릅니다.

export interface EquipmentSignalInput {
  tat_index: number | null
  usage_ratio: number
  recipe_count: number
  top_recipe_share: number
}

// 백엔드 fleet.percentiles: { metric: { p10..p90 } }. 빈 dict은
// "판단 근거 없음"이고, 그 경우 배지를 달지 않습니다.
export type FleetPercentiles = Record<string, Record<string, number>>

export type EquipmentSignal = 'slow' | 'fast' | 'underused' | 'narrow'

// OFFICE-VERIFY — 사무실 실 분포를 보기 전까지는 전부 자리표시자입니다.
// 조정 절차는 recipe_tat/MIGRATION.md 의 "장비별 뷰" 절.
// 값이 확정되면 이 주석을 `office 확인 YYYY-MM-DD` 로 바꿉니다.
export const USAGE_FLOOR = 0.85
export const TAT_CEIL = 1.10
export const TAT_FLOOR = 0.92
export const SHARE_CEIL = 0.50

export const SIGNAL_META: Record<EquipmentSignal, { label: string, tone: 'warn' | 'info' }> = {
  slow: { label: '느림', tone: 'warn' },
  underused: { label: '저사용', tone: 'warn' },
  narrow: { label: '편중', tone: 'warn' },
  fast: { label: '빠름', tone: 'info' }
}

const at = (percentiles: FleetPercentiles, metric: string, key: string): number | null => {
  const value = percentiles?.[metric]?.[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

export const equipmentSignals = (
  row: EquipmentSignalInput,
  percentiles: FleetPercentiles
): EquipmentSignal[] => {
  const signals: EquipmentSignal[] = []

  const usageTail = at(percentiles, 'usage_ratio', 'p10')
  if (usageTail !== null && row.usage_ratio <= usageTail && row.usage_ratio < USAGE_FLOOR) {
    signals.push('underused')
  }

  // tat_index === null 은 표본 미달입니다. "느리지 않다"가 아니라 "모른다"
  // 이므로 어느 쪽으로도 판정하지 않습니다.
  if (row.tat_index !== null) {
    const slowTail = at(percentiles, 'tat_index', 'p90')
    if (slowTail !== null && row.tat_index >= slowTail && row.tat_index > TAT_CEIL) {
      signals.push('slow')
    }
    const fastTail = at(percentiles, 'tat_index', 'p10')
    if (fastTail !== null && row.tat_index <= fastTail && row.tat_index < TAT_FLOOR) {
      signals.push('fast')
    }
  }

  const coverageTail = at(percentiles, 'recipe_count', 'p10')
  if (
    coverageTail !== null
    && row.recipe_count <= coverageTail
    && row.top_recipe_share >= SHARE_CEIL
  ) {
    signals.push('narrow')
  }

  return signals
}
```

- [ ] **Step 4: 통과 확인**

Run (from `front-dev-home/`): `npm test && npm run typecheck && npm run lint`

Expected: 전부 PASS

- [ ] **Step 5: 커밋**

```bash
git add front-dev-home/app/utils/equipmentSignals.ts \
        front-dev-home/app/utils/equipmentSignals.test.ts
git commit -m "feat(recipe-tat): 장비 배지 판정 — 분위수 AND 절대 기준

절대 기준만 쓰면 상수가 실 분포와 어긋나는 순간 전부 정상이거나 전부
경고가 됩니다. 분위수만 쓰면 완벽히 건강한 플릿에서도 항상 하위 10%를
경고합니다. 둘을 AND로 묶어 서로의 실패 모드를 막습니다.

tat_index === null(표본 미달)은 어느 쪽으로도 판정하지 않습니다 —
'느리지 않다'가 아니라 '모른다'입니다.

임계값 4개는 전부 OFFICE-VERIFY 자리표시자입니다."
```

---

### Task 8: 플릿 표 + 모드 추가

**Files:**
- Modify: `front-dev-home/app/composables/useRecipeTatApi.ts`
- Create: `front-dev-home/app/components/ebeam/RecipeTatFleetTable.vue`
- Create: `front-dev-home/app/components/ebeam/RecipeTatEquipmentView.vue`
- Modify: `front-dev-home/app/components/ebeam/RecipeTatView.vue`

**Interfaces:**
- Consumes: Task 4의 `/equipments`, Task 7의 `equipmentSignals`
- Produces:
  - `useRecipeTatApi().fetchRecipeTatEquipments(params)` → `RecipeTatEquipmentsResponse`
  - `RecipeTatEquipmentRow`, `RecipeTatFleetReference` 타입
  - `<EbeamRecipeTatFleetTable>` props `{ rows, percentiles, selected, maxSelected }`, emit `update:selected`
  - `<EbeamRecipeTatEquipmentView>` props `{ fabs, toolType, dateRange }`

- [ ] **Step 1: API 타입 + fetcher 추가**

`front-dev-home/app/composables/useRecipeTatApi.ts`에 추가:

```ts
export const MAX_COMPARE_EQPS = 5

export interface RecipeTatEquipmentRow {
  eqp_id: string
  fab_name: string
  eqp_model_cd: string
  // 표시용. 신호 판정에는 쓰지 않습니다 — 가동률은 "얼마나 바빴는가"이지
  // "몇 번 돌았는가"가 아닙니다.
  exec_count: number
  total_meastime: number
  avg_meastime: number
  recipe_count: number
  top_recipe: string | null
  top_recipe_share: number
  // 실제 총 TAT / 이 장비의 레시피 구성이면 걸렸어야 할 TAT.
  // 표본 미달이면 null.
  tat_index: number | null
  // 측정 점유율. MES 가동률이 아닙니다 — 로딩·대기·PM이 빠져 있습니다.
  occupancy: number
  usage_ratio: number
}

export interface RecipeTatFleetReference {
  tool_count: number
  total_executions: number
  total_meastime: number
  window_seconds: number
  median_total_meastime: number
  median_recipe_count: number
  min_sample: number
  percentiles: Record<string, Record<string, number>>
}

export interface RecipeTatEquipmentsResponse {
  tool_type: RecipeTatToolType
  fab_names: string[]
  start_date: string | null
  end_date: string | null
  fleet: RecipeTatFleetReference
  equipments: RecipeTatEquipmentRow[]
}
```

`useRecipeTatApi()` 안에 추가하고 반환 객체에 이름을 더합니다:

```ts
  const fetchRecipeTatEquipments = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatEquipmentsResponse> => {
    // /devices 와 같은 이유로 lot_cd·limit 을 벗겨냅니다: 이 엔드포인트는
    // 범위 안에 어떤 장비가 있는지에 대한 진실이라 선택으로 걸러지면
    // 안 됩니다.
    const scope: RecipeTatQuery = {
      toolType: params.toolType,
      fabNames: params.fabNames,
      startDate: params.startDate,
      endDate: params.endDate
    }
    return await $fetch<RecipeTatEquipmentsResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/equipments`),
      { query: buildQuery(scope) }
    )
  }
```

- [ ] **Step 2: 플릿 표 컴포넌트 작성**

작업 전 `DESIGN.md`를 읽습니다. 색상은 `--sk-*` 토큰만 씁니다.

`front-dev-home/app/components/ebeam/RecipeTatFleetTable.vue`:

```vue
<template>
  <div class="dashboard-surface rounded-2xl px-3.5 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
      <div class="flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          장비 목록
        </h3>
        <span class="inline-flex h-5 items-center rounded bg-zinc-100 px-1.5 font-mono text-[10px] tabular-nums text-zinc-600 dark:bg-zinc-800 dark:text-zinc-300">
          {{ filteredRows.length.toLocaleString() }} / {{ rows.length.toLocaleString() }}
        </span>
        <span class="sk-meta">
          {{ selected.length }} / {{ maxSelected }}대 선택
        </span>
      </div>
      <div class="flex items-center gap-2">
        <UInput
          v-model="search"
          size="xs"
          placeholder="eqp_id / model 검색…"
          icon="i-lucide-search"
          class="w-[14rem]"
        />
        <UButton
          size="xs"
          color="neutral"
          variant="outline"
          icon="i-lucide-rotate-ccw"
          label="선택 해제"
          :disabled="selected.length === 0"
          @click="emit('update:selected', [])"
        />
      </div>
    </div>

    <UTable
      v-model:sorting="sorting"
      :columns="columns"
      :data="sortedRows"
      :sorting-options="{ enableMultiSort: false, enableSortingRemoval: false }"
      sticky="header"
      :ui="tableUi"
    >
      <template
        v-for="id in sortableColumnIds"
        :key="id"
        #[`${id}-header`]="{ column }"
      >
        <UButton
          size="xs"
          color="neutral"
          variant="ghost"
          class="-mx-2 -my-1 h-6 px-2 text-[11px] font-medium text-(--sk-ink-muted) hover:text-(--sk-ink)"
          :trailing-icon="getSortIcon(column.getIsSorted())"
          @click="column.toggleSorting(column.getIsSorted() === 'asc')"
        >
          {{ column.columnDef.header }}
        </UButton>
      </template>

      <template #pick-cell="{ row }">
        <UCheckbox
          :model-value="selected.includes(row.original.eqp_id)"
          :disabled="!selected.includes(row.original.eqp_id) && selected.length >= maxSelected"
          @update:model-value="toggle(row.original.eqp_id)"
        />
      </template>

      <template #occupancy-cell="{ row }">
        {{ (row.original.occupancy * 100).toFixed(1) }}%
      </template>

      <template #tat_index-cell="{ row }">
        <span :class="row.original.tat_index === null ? 'text-(--sk-ink-muted)' : ''">
          {{ row.original.tat_index === null ? '—' : row.original.tat_index.toFixed(2) }}
        </span>
      </template>

      <template #signals-cell="{ row }">
        <div class="flex flex-wrap gap-1">
          <span
            v-for="signal in signalsFor(row.original)"
            :key="signal"
            class="inline-flex h-5 items-center rounded px-1.5 text-[10px] font-medium ring-1"
            :class="SIGNAL_META[signal].tone === 'warn'
              ? 'bg-amber-50 text-amber-700 ring-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:ring-amber-900'
              : 'bg-zinc-50 text-(--sk-ink-muted) ring-(--sk-border-soft) dark:bg-zinc-900/40'"
          >
            {{ SIGNAL_META[signal].label }}
          </span>
        </div>
      </template>
    </UTable>
  </div>
</template>

<script setup lang="ts">
import type { TableColumn } from '@nuxt/ui'
import type { SortingState } from '@tanstack/vue-table'
import {
  formatSecondsAsDuration,
  type RecipeTatEquipmentRow
} from '~/composables/useRecipeTatApi'
import {
  equipmentSignals,
  SIGNAL_META,
  type FleetPercentiles
} from '~/utils/equipmentSignals'

const props = defineProps<{
  rows: RecipeTatEquipmentRow[]
  percentiles: FleetPercentiles
  selected: string[]
  maxSelected: number
}>()

const emit = defineEmits<{ 'update:selected': [string[]] }>()

const search = ref('')

const filteredRows = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return props.rows
  return props.rows.filter(row =>
    row.eqp_id.toLowerCase().includes(q)
    || row.eqp_model_cd.toLowerCase().includes(q)
    || row.fab_name.toLowerCase().includes(q))
})

const sortableColumnIds = [
  'exec_count', 'total_meastime', 'occupancy', 'avg_meastime', 'recipe_count', 'tat_index'
] as const
type SortableColumnId = typeof sortableColumnIds[number]

const sorting = ref<SortingState>([{ id: 'total_meastime', desc: true }])

const getSortIcon = (direction: false | 'asc' | 'desc') => {
  if (direction === 'asc') return 'i-lucide-arrow-up-narrow-wide'
  if (direction === 'desc') return 'i-lucide-arrow-down-wide-narrow'
  return 'i-lucide-arrow-up-down'
}

const sortedRows = computed(() => {
  const current = sorting.value[0]
  if (!current) return filteredRows.value
  const id = current.id as SortableColumnId
  const dir = current.desc ? -1 : 1
  // tat_index가 null인 행은 정렬 방향과 무관하게 항상 맨 뒤로 보냅니다 —
  // '모른다'를 0으로 취급하면 표본 미달 장비가 최상위/최하위로 몰립니다.
  return [...filteredRows.value].sort((a, b) => {
    const av = a[id]
    const bv = b[id]
    if (av === null && bv === null) return 0
    if (av === null) return 1
    if (bv === null) return -1
    return (av - bv) * dir
  })
})

const toggle = (eqpId: string) => {
  if (props.selected.includes(eqpId)) {
    emit('update:selected', props.selected.filter(id => id !== eqpId))
    return
  }
  if (props.selected.length >= props.maxSelected) return
  emit('update:selected', [...props.selected, eqpId])
}

const signalsFor = (row: RecipeTatEquipmentRow) => equipmentSignals(row, props.percentiles)

const columns: TableColumn<RecipeTatEquipmentRow>[] = [
  { id: 'pick', header: '', size: 44 },
  { accessorKey: 'eqp_id', header: 'eqp_id', size: 120 },
  { accessorKey: 'fab_name', header: 'fab', size: 72 },
  { accessorKey: 'eqp_model_cd', header: 'model', size: 100 },
  {
    accessorKey: 'exec_count',
    header: '실행수',
    size: 88,
    cell: ({ row }) => row.original.exec_count.toLocaleString()
  },
  {
    accessorKey: 'total_meastime',
    header: '총 TAT',
    size: 130,
    cell: ({ row }) => formatSecondsAsDuration(row.original.total_meastime)
  },
  { accessorKey: 'occupancy', header: '점유율', size: 88 },
  {
    accessorKey: 'avg_meastime',
    header: '평균',
    size: 110,
    cell: ({ row }) => formatSecondsAsDuration(Math.round(row.original.avg_meastime))
  },
  { accessorKey: 'recipe_count', header: '레시피수', size: 88 },
  { accessorKey: 'tat_index', header: 'TAT index', size: 100 },
  { id: 'signals', header: '신호', size: 140 }
]

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>
```

**`점유율` 헤더 툴팁을 반드시 붙입니다.** 이 문장이 없으면 사용자가 62%를 보고 장비가 놀고 있다고 읽습니다. `occupancy` 열 헤더를 `UTooltip`으로 감싸고 텍스트는:

```text
측정 시간 기준입니다. 로딩·대기·PM이 빠져 있어 MES 가동률보다 낮게 읽힙니다.
```

- [ ] **Step 3: 오케스트레이터 작성**

`front-dev-home/app/components/ebeam/RecipeTatEquipmentView.vue`:

```vue
<template>
  <div class="space-y-3">
    <AppLoadingState
      v-if="status === 'pending' && !equipmentRows.length"
      title="장비별 데이터를 불러오는 중입니다."
    />
    <div
      v-else-if="!equipmentRows.length"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
      <UIcon
        name="i-lucide-inbox"
        class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
      />
      <p class="mt-2 sk-body">
        이 기간에 측정한 장비가 없습니다.
      </p>
      <p class="mt-1 sk-meta">
        기간을 넓히거나 다른 fab을 선택해보세요.
      </p>
    </div>

    <template v-else>
      <EbeamRecipeTatFleetTable
        :rows="equipmentRows"
        :percentiles="percentiles"
        :selected="selected"
        :max-selected="MAX_COMPARE_EQPS"
        @update:selected="selected = $event"
      />

      <EbeamRecipeTatEquipmentCompare
        v-if="selected.length"
        :tool-type="toolType"
        :fabs="fabs"
        :date-range="dateRange"
        :eqp-ids="selected"
        :rows="selectedRows"
      />
      <div
        v-else
        class="dashboard-surface rounded-2xl px-6 py-10 text-center"
      >
        <UIcon
          name="i-lucide-mouse-pointer-click"
          class="mx-auto h-6 w-6 text-(--sk-ink-muted)"
        />
        <p class="mt-2 sk-body">
          장비를 선택해주세요
        </p>
        <p class="mt-1 sk-meta">
          위 표에서 최대 {{ MAX_COMPARE_EQPS }}대까지 체크하면 트렌드와 레시피 구성을 비교합니다.
        </p>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import {
  MAX_COMPARE_EQPS,
  useRecipeTatApi,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'

const props = defineProps<{
  fabs: string[]
  toolType: RecipeTatToolType
  dateRange: { start: string, end: string }
}>()

const { fetchRecipeTatEquipments } = useRecipeTatApi()

const selected = ref<string[]>([])

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined
}))

const cacheKey = computed(
  () => `recipe-tat-equipments:${queryParams.value.toolType}`
    + `:${queryParams.value.fabNames?.join(',') ?? 'ALL'}`
    + `:${queryParams.value.startDate ?? 'auto'}:${queryParams.value.endDate ?? 'auto'}`
)

const { data, status } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeTatEquipments(queryParams.value),
  { watch: [cacheKey] }
)

// 조회 범위가 바뀌면 선택을 비웁니다. 범위 밖 장비를 선택한 채로 두면
// 빈 비교 패널이 남습니다 (디바이스별의 resetKey 패턴과 같은 이유).
watch(cacheKey, () => {
  selected.value = []
})

const equipmentRows = computed(() => data.value?.equipments ?? [])
const percentiles = computed(() => data.value?.fleet.percentiles ?? {})
const selectedRows = computed(
  () => equipmentRows.value.filter(row => selected.value.includes(row.eqp_id))
)
</script>
```

- [ ] **Step 4: 모드 토글 + 분기 추가 (RecipeTatView.vue 최소 편집)**

`VIEW_MODES`에 항목 하나를 더합니다:

```ts
const VIEW_MODES = [
  { value: 'summary', label: '전체 요약', icon: 'i-lucide-layers' },
  { value: 'by-device', label: '디바이스별', icon: 'i-lucide-cpu' },
  { value: 'by-equipment', label: '장비별', icon: 'i-lucide-microscope' }
] as const
```

`metaSubtitle`을 확장합니다:

```ts
const metaSubtitle = computed(() => {
  if (viewMode.value === 'by-device') return 'Recipe별 측정 시간 (TAT) 디바이스별로 분석합니다.'
  if (viewMode.value === 'by-equipment') return '장비(eqp_id)별 측정 부하와 소요 시간을 비교합니다.'
  return 'Recipe별 측정 시간 (TAT)을 Fab 기준으로 분석합니다.'
})
```

디바이스 피커의 `v-if`를 유지한 채, 장비별 분기를 **디바이스 안내문 앞**에 넣습니다:

```vue
    <!-- 장비별: 별도 컴포넌트 트리. 기존 본문은 건드리지 않습니다. -->
    <EbeamRecipeTatEquipmentView
      v-if="viewMode === 'by-equipment'"
      :fabs="fabs"
      :tool-type="toolType"
      :date-range="dateRange"
    />

    <!-- 디바이스별 모드에서 선택이 없으면 대시보드 대신 안내 -->
    <div
      v-else-if="viewMode === 'by-device' && !selectedLot"
      class="dashboard-surface rounded-2xl px-6 py-12 text-center"
    >
```

`queryParams`의 `lotCd`는 그대로 둡니다 (`viewMode === 'by-device'`일 때만 채워지므로 장비별에서는 자동으로 비어 있습니다).

- [ ] **Step 5: 검증**

Run (from `front-dev-home/`): `npm run typecheck && npm run lint && npm test`

Expected: 전부 PASS. 이 시점에는 `EbeamRecipeTatEquipmentCompare`가 아직 없어 typecheck가 통과해도 브라우저에서 빈 영역이 나옵니다 — Task 9에서 채웁니다.

- [ ] **Step 6: 커밋**

```bash
git add front-dev-home/app/composables/useRecipeTatApi.ts \
        front-dev-home/app/components/ebeam/RecipeTatFleetTable.vue \
        front-dev-home/app/components/ebeam/RecipeTatEquipmentView.vue \
        front-dev-home/app/components/ebeam/RecipeTatView.vue
git commit -m "feat(recipe-tat): 장비별 모드와 플릿 표

RecipeTatView는 모드 토글 항목 하나와 v-if 분기 하나만 늘어납니다. 이미
729줄이라 여기에 얹으면 1100줄이 되고, 동작 중인 두 뷰의 회귀 위험이
생깁니다.

TAT index가 null인 행은 정렬 방향과 무관하게 항상 맨 뒤로 보냅니다 —
'모른다'를 0으로 취급하면 표본 미달 장비가 최상위나 최하위로 몰립니다.

점유율 열 헤더에 툴팁을 답니다: 측정 시간 기준이라 로딩·대기·PM이 빠져
있고 MES 가동률보다 낮게 읽힙니다."
```

---

### Task 9: 비교 패널

**Files:**
- Modify: `front-dev-home/app/composables/useRecipeTatApi.ts`
- Create: `front-dev-home/app/components/ebeam/RecipeTatEquipmentCompare.vue`

**Interfaces:**
- Consumes: Task 5의 `/equipment-compare`, Task 8의 `RecipeTatEquipmentRow`
- Produces: `<EbeamRecipeTatEquipmentCompare>` props `{ toolType, fabs, dateRange, eqpIds, rows }`

- [ ] **Step 1: API 타입 + fetcher 추가**

`useRecipeTatApi.ts`에 추가:

```ts
export interface RecipeTatEquipmentTrendSeries {
  eqp_id: string
  points: RecipeTatDailyTrendPoint[]
}

export interface RecipeTatEquipmentRecipeCell {
  eqp_id: string
  meas_counts: number
  total_meastime: number
  avg_meastime: number
}

export interface RecipeTatEquipmentRecipeRow {
  class_name: string
  recipe_name: string
  full_name: string
  total_meastime: number
  // 선택 장비 수만큼, 요청 순서 그대로. 미실행 장비는 0으로 채워집니다.
  cells: RecipeTatEquipmentRecipeCell[]
}

export interface RecipeTatEquipmentCompareResponse {
  tool_type: RecipeTatToolType
  fab_names: string[]
  start_date: string | null
  end_date: string | null
  // 실제로 사용된 목록(상한 적용 후). 요청보다 짧으면 절단된 것입니다.
  eqp_ids: string[]
  trends: RecipeTatEquipmentTrendSeries[]
  recipes: RecipeTatEquipmentRecipeRow[]
}
```

`RecipeTatQuery`에 필드를 더합니다:

```ts
  // 장비별 비교 뷰가 최대 MAX_COMPARE_EQPS 대를 쉼표로 보냅니다.
  eqpIds?: string[]
```

`buildQuery`에 추가:

```ts
  if (params.eqpIds?.length) query.eqp_id = params.eqpIds.join(',')
```

fetcher:

```ts
  const fetchRecipeTatEquipmentCompare = async (
    params: RecipeTatQuery
  ): Promise<RecipeTatEquipmentCompareResponse> => {
    return await $fetch<RecipeTatEquipmentCompareResponse>(
      joinApiPath(base, `/${toolSlug(params.toolType)}/recipe-tat/equipment-compare`),
      { query: buildQuery(params) }
    )
  }
```

반환 객체에 `fetchRecipeTatEquipmentCompare`를 더합니다.

- [ ] **Step 2: 비교 컴포넌트 작성**

`front-dev-home/app/components/ebeam/RecipeTatEquipmentCompare.vue`:

```vue
<template>
  <div class="space-y-3">
    <!-- 선택 요약: 플릿 표에서 이미 받은 행으로 계산하므로 추가 요청 없음 -->
    <div class="dashboard-surface flex flex-wrap items-center gap-2 rounded-2xl px-3.5 py-2.5">
      <span
        v-for="(row, index) in rows"
        :key="row.eqp_id"
        class="inline-flex h-7 items-center gap-2 rounded-md px-2.5 text-[11px] ring-1 ring-(--sk-border-soft)"
      >
        <span
          class="h-2 w-2 rounded-full"
          :style="{ backgroundColor: palette[index % palette.length] }"
        />
        <span class="font-mono font-semibold text-(--sk-ink)">{{ row.eqp_id }}</span>
        <span class="text-(--sk-ink-muted)">
          {{ row.exec_count.toLocaleString() }} runs ·
          {{ formatSecondsCompact(row.total_meastime) }} ·
          {{ row.recipe_count }} recipes
        </span>
      </span>
    </div>

    <UCard class="dashboard-surface rounded-2xl">
      <template #header>
        <div class="flex items-center gap-2">
          <UIcon
            name="i-lucide-trending-up"
            class="h-4 w-4 text-(--sk-ink-muted)"
          />
          <h3 class="sk-title">
            장비별 일별 TAT
          </h3>
        </div>
      </template>
      <div
        ref="trendEl"
        class="h-[360px] w-full"
      />
    </UCard>

    <div class="dashboard-surface rounded-2xl px-3.5 py-3">
      <div class="mb-3 flex flex-wrap items-center gap-2">
        <h3 class="sk-title">
          레시피 구성 비교
        </h3>
        <span class="sk-meta">
          선택 장비들이 돈 레시피의 합집합입니다. 돌지 않은 장비는 0으로 표시됩니다.
        </span>
      </div>

      <UTable
        :columns="columns"
        :data="pagedRecipes"
        sticky="header"
        :ui="tableUi"
      />

      <div class="mt-2 flex items-center justify-between text-xs text-(--sk-ink-muted)">
        <span class="tabular-nums">
          {{ pageStart }}–{{ pageEnd }} of {{ recipes.length.toLocaleString() }}
        </span>
        <div class="flex gap-1">
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            icon="i-lucide-chevron-left"
            :disabled="currentPage <= 1"
            @click="currentPage -= 1"
          />
          <UButton
            size="xs"
            color="neutral"
            variant="ghost"
            trailing-icon="i-lucide-chevron-right"
            :disabled="currentPage >= pageCount"
            @click="currentPage += 1"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import type { TableColumn } from '@nuxt/ui'
import {
  formatSecondsAsDuration,
  formatSecondsCompact,
  useRecipeTatApi,
  type RecipeTatEquipmentRecipeRow,
  type RecipeTatEquipmentRow,
  type RecipeTatToolType
} from '~/composables/useRecipeTatApi'

const props = defineProps<{
  toolType: RecipeTatToolType
  fabs: string[]
  dateRange: { start: string, end: string }
  eqpIds: string[]
  rows: RecipeTatEquipmentRow[]
}>()

const { fetchRecipeTatEquipmentCompare } = useRecipeTatApi()
const { palette } = useEchartsTheme()

const queryParams = computed(() => ({
  toolType: props.toolType,
  fabNames: props.fabs.length > 0 ? props.fabs : undefined,
  startDate: props.dateRange.start || undefined,
  endDate: props.dateRange.end || undefined,
  eqpIds: props.eqpIds
}))

// 선택 순서가 캐시 키를 흔들지 않도록 정렬해서 넣습니다 — 같은 3대를
// 다른 순서로 고르면 같은 데이터입니다.
const cacheKey = computed(
  () => `recipe-tat-compare:${props.toolType}:${props.fabs.join(',') || 'ALL'}`
    + `:${props.dateRange.start || 'auto'}:${props.dateRange.end || 'auto'}`
    + `:${[...props.eqpIds].sort().join(',')}`
)

const { data } = await useAsyncData(
  () => cacheKey.value,
  () => fetchRecipeTatEquipmentCompare(queryParams.value),
  { watch: [cacheKey] }
)

const trends = computed(() => data.value?.trends ?? [])
const recipes = computed(() => data.value?.recipes ?? [])

// 트렌드 오버레이

const trendEl = ref<HTMLDivElement | null>(null)

const trendOption = computed<EChartsOption>(() => {
  const dates = trends.value[0]?.points.map(point => point.date) ?? []
  return {
    tooltip: { trigger: 'axis' },
    legend: {
      top: 0,
      textStyle: { fontSize: 10 },
      data: trends.value.map(series => series.eqp_id)
    },
    grid: { left: 8, right: 24, top: 32, bottom: 28, containLabel: true },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: {
        fontSize: 10,
        interval: Math.max(0, Math.floor(dates.length / 8) - 1)
      }
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, formatter: (v: number) => formatSecondsCompact(v) }
    },
    // areaStyle을 쓰지 않습니다: 다중 시리즈에 채움을 주면 hover 시 blur가
    // 채움을 지워서 화면이 깨진 것처럼 보입니다.
    series: trends.value.map((series, index) => ({
      type: 'line' as const,
      name: series.eqp_id,
      smooth: true,
      showSymbol: false,
      itemStyle: { color: palette.value[index % palette.value.length] },
      lineStyle: { color: palette.value[index % palette.value.length] },
      data: series.points.map(point => point.total_meastime)
    }))
  }
})

useEchart(trendEl, trendOption, { exportName: 'equipment-tat-trend' })

// 레시피 매트릭스

const PAGE_SIZE = 25
const currentPage = ref(1)
watch(cacheKey, () => {
  currentPage.value = 1
})

const pageCount = computed(() => Math.max(1, Math.ceil(recipes.value.length / PAGE_SIZE)))
const pageStart = computed(
  () => recipes.value.length === 0 ? 0 : ((currentPage.value - 1) * PAGE_SIZE) + 1
)
const pageEnd = computed(() => Math.min(currentPage.value * PAGE_SIZE, recipes.value.length))
const pagedRecipes = computed(
  () => recipes.value.slice((currentPage.value - 1) * PAGE_SIZE, currentPage.value * PAGE_SIZE)
)

// 열은 응답의 eqp_ids 순서를 그대로 따릅니다. cells가 같은 순서로 0채움되어
// 오므로 인덱스로 바로 꽂습니다 — 백엔드가 길이를 보장합니다.
const columns = computed<TableColumn<RecipeTatEquipmentRecipeRow>[]>(() => [
  { accessorKey: 'full_name', header: 'full name', size: 240 },
  {
    accessorKey: 'total_meastime',
    header: '합계',
    size: 110,
    cell: ({ row }) => formatSecondsAsDuration(row.original.total_meastime)
  },
  ...(data.value?.eqp_ids ?? []).map((eqpId, index) => ({
    id: `eqp-${eqpId}`,
    header: eqpId,
    size: 150,
    cell: ({ row }: { row: { original: RecipeTatEquipmentRecipeRow } }) => {
      const cell = row.original.cells[index]
      if (!cell || cell.meas_counts === 0) return '—'
      return `${cell.meas_counts.toLocaleString()} · ${formatSecondsCompact(cell.total_meastime)}`
    }
  }))
])

const tableUi = {
  tr: 'transition-colors hover:bg-zinc-50 dark:hover:bg-zinc-800/50',
  td: 'py-1.5 px-3 text-[12px] whitespace-nowrap overflow-hidden text-ellipsis tabular-nums text-(--sk-ink)',
  th: 'py-2 px-3 text-[11px] font-medium text-(--sk-ink-muted) bg-zinc-50/60 dark:bg-zinc-900/40'
}
</script>
```

- [ ] **Step 3: 검증**

Run (from `front-dev-home/`): `npm run typecheck && npm run lint && npm test`

Expected: 전부 PASS

- [ ] **Step 4: 커밋**

```bash
git add front-dev-home/app/composables/useRecipeTatApi.ts \
        front-dev-home/app/components/ebeam/RecipeTatEquipmentCompare.vue
git commit -m "feat(recipe-tat): 장비 비교 패널 — 트렌드 오버레이 + 레시피 매트릭스

1대만 골라도 열립니다. '이 장비가 무슨 레시피를 도는가'가 원 요청의 첫
질문이기 때문입니다.

다중 시리즈 라인에 areaStyle을 쓰지 않습니다 — hover 시 blur가 채움을
지워서 화면이 깨진 것처럼 보입니다.

레시피 매트릭스의 열은 응답 eqp_ids 순서를 그대로 따릅니다. 백엔드가
cells를 같은 순서로 0채움해 길이를 보장하므로 인덱스로 바로 꽂습니다."
```

---

### Task 10: 긴 기간 프리셋 · 계약 문서 · 브라우저 검증

**Files:**
- Modify: `front-dev-home/app/components/ebeam/DateRangePopover.vue`
- Modify: `docs/api-contracts/recipe-tat.yaml`
- Modify: `front-dev-home/app/pages/endpoints.vue`

**Interfaces:**
- Consumes: Task 1–9 전부
- Produces: 최종 산출물

- [ ] **Step 1: 60/90일 프리셋 추가**

`front-dev-home/app/components/ebeam/DateRangePopover.vue`:

```ts
const DEFAULT_PRESETS = [
  { label: 'Today', days: 0 },
  { label: 'Last 7 days', days: 7 },
  { label: 'Last 14 days', days: 14 },
  { label: 'Last 30 days', days: 30 },
  { label: 'Last 60 days', days: 60 },
  { label: 'Last 90 days', days: 90 }
]
```

소비처는 `RecipeTatView`와 `FailIssueView` 둘뿐입니다 (skewvoir `FilterBar`는 자체 프리셋을 넘깁니다). 둘 다 같은 `meas_hist` 행을 읽으므로 Task 2의 밀도 개선을 함께 받습니다.

- [ ] **Step 2: API 계약 문서 갱신**

`docs/api-contracts/recipe-tat.yaml`에 두 엔드포인트를 기존 항목과 같은 형식으로 추가합니다. 필드는 Task 4·5의 TypedDict와 1:1로 맞춥니다 — `EquipmentRow`(12필드), `FleetReference`(8필드, `percentiles`는 `object`), `EquipmentsPayload`, `EquipmentTrendSeries`, `EquipmentRecipeCell`, `EquipmentRecipeRow`, `EquipmentComparePayload`. `tat_index`는 `nullable: true`, `top_recipe`도 `nullable: true`입니다.

`front-dev-home/app/pages/endpoints.vue`의 recipe-tat 블록에 두 항목을 추가합니다:

```ts
      {
        path: '/api/{tool_slug}/recipe-tat/equipments',
        example: { path: '/cdsem/recipe-tat/equipments', query: { fab_name: 'R3' } }
      },
      {
        path: '/api/{tool_slug}/recipe-tat/equipment-compare',
        example: {
          path: '/cdsem/recipe-tat/equipment-compare',
          query: { fab_name: 'R3', eqp_id: 'ECXDX123,ECDX456' }
        }
      }
```

(주변 항목의 `label`/`description` 필드 형태를 그대로 따라 채웁니다.)

- [ ] **Step 3: 전체 자동 검증**

```bash
.venv/bin/python -m pytest -q
npm run lint:md
cd front-dev-home && npm test && npm run typecheck && npm run lint && cd ..
```

Expected: 전부 PASS. worktree에는 gitignore된 `office.py` 사본이 없으므로 **skip 수가 main 체크아웃과 다릅니다** — passed 수만 비교하지 말고 passed+skipped 합계로 비교하세요.

- [ ] **Step 4: 브라우저 검증**

`.venv/bin/python index.py`와 `npm run dev`를 띄우고 Playwright MCP로 확인합니다. 스크린샷은 `.playwright-mcp/screenshots/` 아래에 저장합니다.

**자동 검사로는 절대 잡히지 않는 것부터 봅니다.** 자동 임포트 태그가 틀리면 컴포넌트가 **에러 없이 빈 영역**으로 렌더됩니다 — typecheck도 lint도 통과합니다.

- [ ] `/ebeam/cd-sem/r3/recipe-status` → `장비별` 탭이 보이고, 클릭하면 표에 행이 **실제로** 그려지는가 (빈 영역이면 태그 이름 확인)
- [ ] 표에 `eqp_id`가 `ECXDX123` 형식으로 나오는가 (`CG63-04`가 보이면 Task 2가 반영되지 않은 것)
- [ ] 한 `eqp_id`가 여러 fab에 중복해 나오지 않는가
- [ ] 배지 4종이 최소 1개씩 보이는가 (느림 / 저사용 / 편중 / TAT index `—`)
- [ ] `점유율` 헤더 툴팁에 "MES 가동률보다 낮게 읽힙니다" 문장이 뜨는가
- [ ] 체크박스 5대까지 선택되고 6대째는 비활성화되는가
- [ ] 2대 이상 선택 시 트렌드 라인이 겹쳐 그려지는가, **hover 했을 때 라인이 사라지지 않는가** (스크린샷은 hover 상태로 찍습니다)
- [ ] 레시피 매트릭스에서 한 장비만 돈 레시피의 다른 장비 칸이 `—`인가
- [ ] 기간을 `Last 90 days`로 바꾸면 표와 트렌드가 갱신되는가
- [ ] fab을 바꾸면 선택이 초기화되는가
- [ ] `/ebeam/hv-sem/r3/recipe-status`에서도 장비별이 동작하는가 (HV-SEM 페이지는 실재합니다)
- [ ] `전체 요약`과 `디바이스별` 탭이 예전 그대로 동작하는가 (회귀 확인)
- [ ] 콘솔에 에러가 없는가

- [ ] **Step 5: 커밋**

```bash
git add front-dev-home/app/components/ebeam/DateRangePopover.vue \
        front-dev-home/app/pages/endpoints.vue \
        docs/api-contracts/recipe-tat.yaml
git commit -m "feat(recipe-tat): 60/90일 프리셋 + 장비별 엔드포인트 계약 문서

장비별 뷰가 더 긴 기간 조회를 지원하므로 프리셋을 넓힙니다. 소비처는
RecipeTatView와 FailIssueView 둘뿐이고, 둘 다 같은 meas_hist 행을 읽어
밀도 개선을 함께 받습니다."
```

- [ ] **Step 6: main 병합 + worktree 정리**

```bash
git -C . merge --ff-only work/recipe-tat-eqp && git push
git worktree remove ../skewnono-eqp-view && git branch -d work/recipe-tat-eqp
git worktree list          # main 트리 하나만 남아야 합니다
```

worktree 정리는 선택이 아닙니다. 남겨두면 낡은 체크아웃이 쌓이고 병합된
브랜치를 붙들며, 다음 세션에 어떤 작업이 열려 있는지를 오해하게 만듭니다.

---

## Self-Review

**Spec coverage** — 설계 문서의 각 절이 어느 task에 들어갔는가:

| 스펙 절 | Task |
| --- | --- |
| 3.1 `tat_index` (간접표준화, 표본 하한) | 4 |
| 3.2 `occupancy`/`usage_ratio` (시간 기준), MES 가동률과의 구분 | 4, 8(툴팁) |
| 3.3 빈 범위 | 4 (`test_get_equipments_is_empty_outside_the_data_window`), 7 (빈 분위수) |
| 3.4 배지 = 분위수 ∧ 절대 | 7 |
| 3.5 사무실 확인 절차 | 6 (MIGRATION.md) |
| 4.1–4.2 엔드포인트 2개, 계약 | 4, 5 |
| 4.3 office 어댑터, `composite_buckets` 확장 | 6 |
| 5.1 컴포넌트 배치 | 8, 9 |
| 5.2 화면 (표 열, 비교 패널, areaStyle 금지) | 8, 9 |
| 5.3 캐시 키와 선택 초기화 | 8, 9 |
| 6.1 생성 순서 뒤집기 | 2 |
| 6.2 장비별 스칼라 | 2 |
| 6.3 밀도 · 프리셋 | 2, 10 |
| 6.4 파급 (fail_issue, 문서) | 1, 2, 6 |
| 6.5 구현 전 확인 사항 | 1(fac 어휘), 2(플릿 부족 칸 폴백) |
| 7 테스트 | 각 task + 10 |
| 8.1 HV-SEM | 2 (docstring 정정), 10 (브라우저 확인) |

**스펙에서 벗어난 결정 2건 (의도적):**

1. `MAX_COMPARE_EQPS`를 `contracts.py`가 아니라 `_analytics_routes.py`에 `MAX_EQP_IDS`로 둡니다. 요청 형태에 관한 값이지 응답 계약이 아니고, 계약에 두면 공유 파서가 recipe_tat 계약을 import 하게 되어 fail_issue까지 끌려옵니다. 프론트엔드는 자체 상수(`MAX_COMPARE_EQPS`)를 갖습니다.
2. payload 조립을 `providers/_shape.py`로 분리합니다(Task 6). 스펙은 각 provider가 조립한다고만 적었지만, mock과 office가 지수·중앙값·분위수를 각자 계산하면 언젠가 어긋납니다.

**스펙이 예상하지 못했고 조사로 드러난 것 (Task 1로 흡수):** `device_statistics`의 lot 풀이 아직 M12를 쓰고 M10 lot을 만들지 않아, 장비(M10 보유)와 lot(M12 보유)이 fac_id로 만날 수 없었습니다. `docs/datatables/sem_list.txt`가 *"M12 는 실재하지 않는 값이었습니다 (user-confirmed 2026-08-03)"*로 이미 판정해 둔 사안입니다.

**Placeholder scan** — "TBD"/"적절히 처리"/"위 내용에 대한 테스트 작성" 없음. 모든 코드 단계에 실제 코드 블록이 있습니다. Task 6의 `_shape.py` 두 함수는 시그니처와 입력 격자 형태를 명시하고 본문은 Task 4·5에서 이미 쓴 로직을 옮기는 것으로 정의했습니다. Task 10 Step 2의 YAML은 필드 목록을 Task 4·5의 TypedDict와 1:1로 지정했습니다.

**Type consistency** — task 사이를 넘는 이름을 대조했습니다: `percentile_summary`(3→4), `_filter_rows`/`_window_seconds`(4→5), `TAT_INDEX_MIN_SAMPLE`(4→7 개념), `MAX_EQP_IDS`(5) ↔ `MAX_COMPARE_EQPS`(8, 프론트엔드), `equipmentSignals`/`SIGNAL_META`/`FleetPercentiles`(7→8), `RecipeTatEquipmentRow`(8→9), `fetchRecipeTatEquipments`(8) / `fetchRecipeTatEquipmentCompare`(9). Task 2가 삭제하는 이름(`FAB_NAMES_BY_FAC`, `_build_eqp_id`, `TOOL_MODELS`, `_lot_pool`, `_pick_recipe_for_fab`)은 이후 어느 task도 참조하지 않습니다.
