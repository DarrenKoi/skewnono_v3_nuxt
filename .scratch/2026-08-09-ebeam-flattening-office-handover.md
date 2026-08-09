# [사무실 필독] ebeam 폴더 평탄화 — 첫 pull 직후 손으로 해야 하는 일

작성일: 2026-08-09 · 대상: 사무실 체크아웃(Phase 2) 및 클라우드 배포(Phase 3)

> **가장 중요한 한 줄**: `storage` 는 사무실에서 실제 운영 중인 두 기능 중
> 하나입니다. 아래 §2 를 건너뛰면 `storage` 가 **오류 없이 mock 데이터로
> 되돌아갑니다.** 화면은 정상으로 보이고, 숫자만 가짜입니다.

## 1. 무엇이 바뀌었나

`back_dev_home/ebeam/` 아래의 벤더/계열 중간 폴더를 없앴습니다.

| 이전 | 이후 |
| --- | --- |
| `ebeam/hitachi/storage/` | `ebeam/storage/` |
| `ebeam/hitachi/hardware/` | `ebeam/hardware/` |
| `ebeam/hitachi/skew/` | `ebeam/skew/` |
| `ebeam/hitachi/recipe_tat/` | `ebeam/recipe_tat/` |
| `ebeam/hitachi/recipe_search/` | `ebeam/recipe_search/` |
| `ebeam/hitachi/lateral_recipe/` | `ebeam/lateral_recipe/` |
| `ebeam/hitachi/pm_planning/` | `ebeam/pm_planning/` |
| `ebeam/hitachi/fail_issue/` | `ebeam/fail_issue/` |
| `ebeam/hitachi/live_alarm/` | `ebeam/live_alarm/` |
| `ebeam/cdsem/device_statistics/` | `ebeam/device_statistics/` |
| `ebeam/hitachi/_tool_specs.py` 등 공용 모듈 | `ebeam/_tool_specs.py` 등 |

**이유**: `back_dev_home/_runtime/office_registry.py` 는 feature 를
디렉터리 이름 **하나로만** 식별하고 전역 유일성을 강제합니다. 계열이
`hitachi` 하나가 아니게 되는 순간(VeritySEM·Provision 추가) 벤더 폴더 구조는
`ebeam/amat/storage/` 와 `ebeam/hitachi/storage/` 같은 중복 슬러그를 만들고,
그때는 앱이 `RuntimeError: Duplicate feature slug 'storage'` 로 **부팅에
실패합니다.** 계열 축은 앞으로 `providers/<family>/` 하위 폴더로 표현합니다 —
규약은 [`docs/back-end/vendor-onboarding.md`](../docs/back-end/vendor-onboarding.md).

## 2. 사무실 체크아웃에서 반드시 해야 하는 일 — 고아 `office.py` 이동

`office.py` 와 `office.py.bak` 은 **gitignored** 입니다. 즉 병합에 딸려 오지
않고, 여러분의 체크아웃에는 **옛 경로에 그대로 남습니다.** git 은 이 파일들을
따라 옮겨 주지 않습니다.

### 2.1 왜 조용한 사고인가

`office.py` 의 **존재 자체가 스위치**입니다(readiness). 새 경로에 파일이 없으면
readiness 는 false 이고, 그 feature 는 아무 경고 없이 mock 으로 응답합니다.
부팅 로그의 `STALE office.py` 검사는 **낡은 사본**을 잡는 것이지 **없는 사본**을
잡지 않습니다.

`storage` 는 사무실 live 기능(2026-07-21 검증)입니다. 이 절차를 건너뛰면
`/api/cdsem/storage` 가 200 을 계속 돌려주지만 내용은 홈 mock 이 지어낸
행입니다. `sem_list` 는 위치가 바뀌지 않았으므로 영향이 없습니다.

### 2.2 절차

```bash
cd <사무실 체크아웃 루트>
git pull

# 1) 옛 경로에 남은 파일을 찾습니다. .bak 도 함께 찾아야 합니다 —
#    `sync_office_adapters --force` 가 남기는 백업이고, .gitignore 는
#    office.py 와 office.py.bak 을 모두 무시합니다.
find back_dev_home/ebeam/hitachi back_dev_home/ebeam/cdsem \
  \( -name "office.py" -o -name "office.py.bak" \) 2>/dev/null

# 2) 나온 파일을 새 경로로 옮깁니다. 예:
mv back_dev_home/ebeam/hitachi/storage/providers/office.py \
   back_dev_home/ebeam/storage/providers/office.py
mv back_dev_home/ebeam/hitachi/recipe_tat/providers/office.py \
   back_dev_home/ebeam/recipe_tat/providers/office.py
mv back_dev_home/ebeam/hitachi/recipe_search/providers/office.py \
   back_dev_home/ebeam/recipe_search/providers/office.py
mv back_dev_home/ebeam/hitachi/lateral_recipe/providers/office.py \
   back_dev_home/ebeam/lateral_recipe/providers/office.py
# .bak 도 같은 자리로. 필요 없다고 판단하면 지우되, 남길 거면 새 경로에 둡니다.

# 3) 빈 디렉터리를 정리합니다.
find back_dev_home/ebeam/hitachi back_dev_home/ebeam/cdsem -type d -empty -delete 2>/dev/null
```

> `mv` 대신 `cp` 를 쓰면 옛 경로의 사본이 남아 다음 사람이 어느 쪽이 진짜인지
> 알 수 없게 됩니다. 옮기세요.

## 3. 옮긴 뒤 확인 — 세 가지를 모두 봅니다

### 3.1 어댑터 목록 (MISSING / STALE / EDITED)

```bash
.venv/bin/python -m scripts.sync_office_adapters
```

인자 없이 실행하면 전체 상태표만 출력하고 아무것도 복사하지 않습니다.

- `MISSING` — `office.py` 가 없습니다. 옮기기를 빠뜨렸거나 아직 구현 전입니다.
  **`storage` 가 여기 있으면 §2 가 끝나지 않은 것입니다.**
- `STALE` — 템플릿(`office_example.py`)이 앞서 있습니다. `sync_office_adapters
  <feature>` 로 갱신합니다(`--force` 는 기존 파일을 `office.py.bak` 으로
  백업한 뒤 덮어씁니다).
- `EDITED` — 사무실에서 손댄 사본입니다. `--diff` 로 차이를 먼저 봅니다.

### 3.2 실제로 무엇이 선택됐는지

```bash
curl -s http://localhost:5000/api/health/providers | python -m json.tool
```

`storage` 가 `office` 인지 확인합니다. `mock` 이면 §2 로 돌아갑니다.

### 3.3 부팅 로그

앱을 띄울 때 나오는 한 줄을 봅니다.

```text
data providers: site=office mode=office — N/24 features on office
```

여기에 `STALE office.py: <feature>` 경고가 없어야 합니다. 다만 §2.1 대로
**없는 사본은 이 경고에 잡히지 않으므로**, 위 3.1·3.2 를 함께 봐야 합니다.

## 4. 함께 알아두면 좋은 변경

- 장비 계열 레지스트리가 2계열(CD-SEM/HV-SEM)에서 4계열(+ AMAT VeritySEM,
  Provision)로 넓어졌습니다. 단일 원천은 `back_dev_home/ebeam/_tool_specs.py`.
- CD/HV 전용 기능(storage, lateral_recipe, recipe_tat, fail_issue,
  recipe_search, skew, hardware, pm_planning, live_alarm)의 라우트는
  `SEM_TOOL_SLUGS`(`cdsem`, `hvsem`) 밖의 슬러그를 **400** 으로 거절합니다.
  AMAT 어댑터가 생기기 전까지 그 화면에 AMAT 장비는 나타나지 않습니다.
- `model_to_tool_type()` 의 `None` 은 이제 "미지" 만 뜻합니다. 예전처럼
  "AMAT 장비" 를 뜻하지 않으므로, 사무실 어댑터에서 "CD/HV 만" 을 표현할 때
  `is not None` 을 쓰지 말고 `in SEM_TOOL_TYPES` 를 쓰십시오.
