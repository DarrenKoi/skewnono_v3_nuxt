# 미연결 장비(방화벽 해제 대기) 조회 화면 설계

- 날짜: 2026-07-30
- 상태: 검토 대기
- 영역: `back_dev_home/sem_list` 어댑터, `front-dev-home` 신규 전사 화면

## 문제

현재 skewnono 는 사무실 Redis 의 `v3_df_sem_avail` 만 명부로 사용합니다. 이
키는 이미 접속이 확인된 장비의 부분집합이므로, **fab 에 새로 반입된 장비는
화면에 전혀 나타나지 않습니다**.

모든 장비는 fab 에 최초 반입될 때 네트워크 방화벽에 막힌 상태입니다. 따라서
장비가 skewnono 에서 보이려면 IT 서비스팀에 해당 IP 의 방화벽 해제를
요청해야 합니다. 즉 "명부에는 있으나 접속되지 않는 상태"는 오류가 아니라
**모든 장비가 반드시 한 번 거치는 초기 상태**입니다.

지금은 어떤 장비가 해제 대기 중인지 확인할 화면이 없습니다. 신규 장비의
존재를 알 수 있는 경로가 없으므로, 요청 누락된 장비는 아무도 인지하지 못한
채 계속 미연결로 남습니다.

## 목표

전사 명부와 접속 확인 명부의 차집합을 조회하여, IT 서비스팀에 제출할 방화벽
해제 요청 목록을 그대로 만들 수 있게 합니다.

- `fab_name` × `eqp_model_cd` 집계로 어느 fab 에 어떤 모델이 들어왔는지
  한 화면에서 파악합니다.
- 요청에 바로 사용할 수 있도록 IP 목록 복사와 CSV 내보내기를 제공합니다.
- 전사 명부는 **사용자가 요청할 때만** 조회합니다. 페이지 진입만으로
  자동 호출하지 않습니다.

## 확인된 사무실 데이터 사실

아래는 이번 대화에서 사용자가 확인해 준 사실입니다
(`user-confirmed 2026-07-30`).

| 사실 | 설계에 미치는 영향 |
| --- | --- |
| Redis 키는 2개가 아니라 **3개**이며 `v3_df_sem_list` 가 전사 명부입니다 | 기존 문서·어댑터 docstring 의 "두 개의 key" 서술을 정정합니다 |
| `v3_df_sem_avail` 은 접속이 확인된 부분집합입니다 | `roster − avail` 이 방화벽 해제 대기 목록입니다 |
| `v3_df_sem_list` 에는 VeritySEM 과 Provision 도 포함됩니다 | 화면에서 tool type 별로 구분하며, 제외하지 않습니다 |
| 모든 장비는 반입 시점에 `eqp_ip` 를 가집니다 | `eqp_ip` 는 계약의 필수 컬럼입니다 |
| 모든 장비는 최초 반입 시 방화벽에 막혀 있습니다 | 미연결은 결함이 아니라 정상 초기 상태입니다 |
| `updt_dt` 는 **장비 최초 반입 시각**입니다 | 기존 문서의 "명부 갱신 시각" 서술은 오류이므로 정정합니다 |
| `updt_dt` 는 구 장비에서는 부정확하고 최근 장비에서는 신뢰 가능합니다 | 반입일을 신규 여부 판단 근거로 쓰되 숨김 조건으로는 쓰지 않습니다 |
| `v3_df_sem_list` 는 fab 에 **현재 연결된** 장비의 스냅샷이며 누적 이력이 아닙니다 (`user-confirmed 2026-07-30`, 아래 "정정" 참고) | 명부에는 폐기·방치된 row 가 존재하지 않으므로 `roster − avail` 의 모든 row 는 반입 시점과 무관하게 actionable 합니다 — 반입일 기준 오래됨(staleness) 필터링은 폐기합니다 |

`v3_df_sem_list` 의 컬럼은 `v3_df_sem_avail` 과 동일한 identity 컬럼 8 개이며
`available` 컬럼이 없습니다 — `fac_id`, `eqp_id`, `eqp_model_cd`, `eqp_grp_id`,
`vendor_nm`, `eqp_ip`, `fab_name`, `updt_dt` (`user-confirmed 2026-07-30`).
설계 당시에는 `OFFICE-VERIFY` 가정이었으나 담당자 확인으로 승격되었습니다.
아직 실제 실행으로 검증한 것은 아니므로 사무실 첫 실행 때 한 번 확인하고
`office 확인 <날짜>` 로 표기를 올립니다. 그래도 어댑터는 컬럼이 다를 경우
누락 컬럼 목록과 함께 실패하도록 유지합니다 — 빈 화면이 아니라 진단 가능한
오류가 나와야 하기 때문입니다. 확인은 `scripts/inspect_redis_key.py` 로
수행합니다.

```bash
.venv/bin/python -m scripts.inspect_redis_key v3_df_sem_list --unique fab_name,eqp_model_cd
```

## 선택한 설계

### 별도 엔드포인트

`GET /api/sem-list/pending` 을 새로 추가하고 기존 `GET /api/sem-list` 는
**변경하지 않습니다**.

`docs/datatables/sem_list.txt` 가 기록하듯 이 명부는 장비 identity 의 단일
진실 원천이며, `storage`, `lateral_recipe`, `hardware/sharpness`,
`hardware/reso_center`, `hardware/mdc`, `meas_hist` 가 모두
`eqp_id → eqp_ip / fab_name` 해석을 `/api/sem-list` 응답에 의존합니다.

여기에 미연결 장비 row 를 추가하면 앱의 모든 장비 선택 UI 에 접속 불가
장비가 등장합니다. 사용자가 그 장비를 선택하면 각 feature 는 존재하지 않는
`eqp_ip` 로 조회하여 개별적으로 "데이터 없음"을 표시하므로, 실제 원인인
"이 장비는 아직 연결되지 않았습니다"가 어디에도 나타나지 않습니다. 따라서
기존 응답의 의미를 그대로 보존합니다.

### 계약

`sem_list/contracts.py` 에 별도 타입을 추가합니다. `SemListRow` 를 확장하지
않습니다.

```python
class PendingToolRow(TypedDict):
    fac_id: str
    eqp_id: str
    eqp_model_cd: str
    eqp_grp_id: str
    vendor_nm: str      # SemListRow 와 달리 Literal 제약을 두지 않습니다
    eqp_ip: str         # 필수. 반입 시점에 항상 부여됩니다
    fab_name: str       # 미배정 시 "" 이며 화면에서 미배정으로 묶습니다
    updt_dt: str        # ISO 문자열. 장비 최초 반입 시각입니다
```

`available` 과 `version` 필드는 두지 않습니다. 두 값은 이 장비가 아직 속하지
않은 키에서 오므로, 사무실이 만들어 낼 수 없는 sentinel 값을 계약에 넣지
않습니다.

`vendor_nm` 은 `Literal["HITACHI", "AMAT"]` 제약을 의도적으로 뺍니다.
`office_example.py` 의 기존 어댑터는 세 번째 vendor 값에 대해 예외를
발생시키며, 이는 접속 확인된 fleet 에는 옳은 동작입니다. 그러나 아직
온보딩하지 않은 장비를 보여 주는 것이 목적인 화면에서 신규 vendor 가
502 를 유발하면 목적과 충돌합니다. 신규 vendor 는 화면에 나타나야 합니다.

### 차집합 기준은 `eqp_id`

`eqp_ip` 가 아니라 `eqp_id` 로 차집합을 계산합니다. `eqp_id` 는 장비의
이름이므로 명부에 존재하는 모든 장비가 반드시 가지고 있습니다.

```text
v3_df_sem_list   →  roster     (필수: eqp_id, eqp_ip, eqp_model_cd, fab_name)
v3_df_sem_avail  →  connected  (필수: eqp_id)

pending = roster[~roster.eqp_id.isin(connected.eqp_id)]
```

필수 컬럼 누락 시 기존 `_REQUIRED_COLUMNS` 패턴과 같이 실제 컬럼 목록을 담아
예외를 발생시킵니다.

### 백엔드 구성

| 파일 | 변경 |
| --- | --- |
| `sem_list/contracts.py` | `PendingToolRow` 추가 |
| `sem_list/data.py` | `get_pending_tools()` 디스패처 추가 |
| `sem_list/routes.py` | `GET /sem-list/pending` 추가 |
| `sem_list/providers/mock.py` | `get_pending_tools()` 추가, docstring 정정 |
| `sem_list/providers/office_example.py` | `get_pending_tools()` 구현, docstring 정정 |

`data.py` 는 기존 `get_data_provider("sem_list")` 스위치를 그대로 사용하므로
새로운 swap surface 는 생기지 않습니다.

### mock 전략

home 에서 이 기능을 개발할 수 있는지는 mock 이 미연결 장비를 표현하는지에
달려 있습니다. 원칙은 **하나의 생성기, 두 개의 출력, 구조적 분리**입니다.

`_generate_fleet()` 이 314 대를 생성한 뒤 **분할**합니다. 300 대는 접속
장비(`get_sem_list()` 의 반환값)이고 14 대는 미연결 장비
(`get_pending_tools()` 의 반환값)입니다. 두 목록에 같은 `eqp_id` 가 나타나지
않는 불변식은 독립적인 난수 추출이 아니라 분할이라는 구성 자체로
보장됩니다.

값이 바뀌는 것은 허용됩니다. `scripts/check_contract.py` 는 응답의 키 집합과
값의 타입만 비교하며 값의 동등성은 보지 않으므로, `updt_dt` 분포를 넓혀도
`sem-list.json` fixture 는 깨지지 않습니다. 유지해야 하는 것은 접속 장비의
**건수(300)와 계약 형태**이며 개별 값이 아닙니다.

미연결 14 대는 사무실이 실제로 넘겨줄 경계 조건을 의도적으로 포함합니다.

- CD-SEM(`CG*`/`GT*`)과 HV-SEM(`TP*`), VeritySEM, Provision 을 모두 포함합니다.
- `fab_name` 이 `""` 인 장비를 1 대 포함하여 미배정 묶음을 검증합니다.
- 4~5 개의 fab × model 조합에 몰아서 배치합니다. 신규 장비는 batch 로
  반입되므로, 모든 칸이 1 인 매트릭스는 집계 동작을 보여 주지 못합니다.
- `updt_dt` 는 최근 구간에 배치하고, 400 일 전 반입된 미연결 장비 1 대를
  포함합니다. 애초 목적은 아래 "정정" 절에서 폐기된 오래됨(staleness)
  표시를 검증하는 것이었습니다. 이제 이 row 는, 반입 후 오래 지나도 여전히
  방화벽 해제를 기다리는 것 — 이 화면이 존재하는 이유 그 자체인 경계
  조건을 보여 주기 위해 남겨 둡니다.

`eqp_ip` 는 모든 미연결 장비에 부여합니다. 반입 시점에 IP 가 없는 장비는
존재하지 않습니다.

접속 장비의 `updt_dt` 는 현재 0~90 일 균등 분포로 생성되고 있으나, 이 값이
반입 시각이라는 사실과 맞지 않습니다. 명부에 수년 전 반입된 장비가 있는 것이
정상이므로 분포를 수년 범위로 넓힙니다. 이는 현재 값이 실제 데이터에 대해
잘못된 것을 가르치는 경우에 해당하므로 생성 값을 변경합니다.

### 프론트엔드 구성

경로는 tool type 전체를 아우르므로 루트 레벨 `/tool-roster` 로 두고,
`utils/headerNav.ts` 의 `HEADER_LINKS` 를 통해 `AppHeader` 아이콘으로
접근합니다. `FeatureTabs` 에는 넣지 않습니다. 해당 컴포넌트의 모든 탭은
`/ebeam/<toolType>/…` 아래로 해석되므로 전사 화면을 표현할 수 없습니다.

| 파일 | 역할 |
| --- | --- |
| `composables/usePendingToolsApi.ts` | `useAsyncData('pending-tools', fn, { immediate: false })` |
| `utils/pendingToolMatrix.ts` | 순수 집계 함수. `rows → { fabs, models, cells, totals }` |
| `utils/pendingToolMatrix.test.ts` | `node --test` 대상 |
| `pages/tool-roster.vue` | 화면 |
| `utils/headerNav.ts` | 헤더 진입점 추가 |

집계는 순수 함수로 분리합니다. `npm test` 는 순수 함수만 실행하므로, 컴포넌트
자체는 렌더러로 유지하고 집계 규칙에 테스트를 붙입니다.

조회는 사용자 조작으로만 발생합니다. `immediate: false` 이므로 진입 시에는
아무 요청도 나가지 않으며, 조회 버튼이 `execute()` 를 호출하고 결과는 세션
동안 캐시되며 새로고침 버튼이 재조회합니다.

화면 구성은 다음과 같습니다.

```text
미연결 장비   조회됨  14 대                      [ 새로고침 ]

 [ 전체 14 ]  [ CD-SEM 6 ]  [ HV-SEM 5 ]  [ VeritySEM 2 ]  [ Provision 1 ]

                            [ IP 목록 복사 ]  [ CSV 다운로드 ]
        CG6380  GT2000  TP4000  VERITYSEM_4  PROVISION_10   합계
 M16A        2       ·       ·            2             ·      4
 M16B        ·       4       ·            ·             1      5
 M14B        ·       ·       5            ·             ·      5
 ──────────────────────────────────────────────────────────────────
 합계        2       4       5            2             1     14

 ▸ 칸 선택 시 드릴다운 목록
   eqp_id     eqp_ip          eqp_model_cd   fab_name   반입일
```

위 예시는 `전체` 가 선택된 상태입니다. tool type chip 은 단일 선택이며,
`CD-SEM` 을 선택하면 `CG6380` 과 `GT2000` 열만 남아 합계가 6 이 됩니다.
`전체` 에서는 tool type 이 섞인 열이 함께 나타납니다.

- tool type 필터는 `useSemListApi.ts` 의 `classifyToolType` 을 사용합니다.
  `IP 목록 복사` 는 활성 필터 범위로 한정합니다. IT 요청은 tool type 단위로
  제출하므로, 전체를 섞은 하나의 목록은 실제 사용 형태와 맞지 않습니다.
- `classifyToolType` 이 `null` 을 반환하는 모델은 **미분류** 묶음에
  넣습니다. 이 묶음이 비어 있을 때는 렌더링하지 않습니다. 회사가 내년에
  도입할 모델은 현재 prefix 목록에 없으므로, 이 묶음만이 신규 tool type 이
  화면에서 조용히 사라지는 것을 막습니다.
- ~~드릴다운 목록은 반입일 내림차순으로 정렬합니다. 반입일이 **180 일**보다
  오래된 row 는 **오래됨** 으로 흐리게 표시하지만 숨기지 않으며
  `IP 목록 복사` 에서도 제외하지 않습니다. 오래된 row 가 요청에 섞이는 비용은
  IT 의 회신 한 번인데 반해, 신규 장비가 숨는 비용은 아무도 인지하지 못하는
  미연결 장비입니다. 180 일은 명명된 상수 하나로 두어 조정 지점을 한 곳으로
  모읍니다. 반입 후 6 개월이 지나도 연결되지 않은 장비는 해제 대기보다는
  폐기·보류일 가능성이 높다는 판단이며, 근거가 약한 임계값이므로 실제 사용 후
  조정합니다.~~
  **[정정, 2026-07-30]** 위 오래됨(staleness) 설계는 전제가 틀려 폐기합니다.
  전제는 "반입 후 오래도록 미연결인 장비는 폐기·보류일 가능성이 높다"였으나,
  product owner 가 확인한 바로는 `v3_df_sem_list` 가 fab 에 **현재 연결된**
  장비의 스냅샷이며 시간이 지나며 쌓이는 누적 이력이 아닙니다. 즉 명부에는
  폐기·방치된 row 가 애초에 존재하지 않으므로, `roster − avail` 의 모든 row 는
  반입 시점과 무관하게 방화벽 해제가 필요한 actionable 대상입니다. 반입일은
  더 이상 숨김·흐리게 표시의 근거가 아니며, 드릴다운 목록은 반입일
  내림차순 정렬만 유지합니다 — 이는 값을 숨기거나 제외하지 않는 순수한
  표시 순서이므로 이번 정정과 무관하게 그대로 남습니다.
- 빈 칸은 `0` 이 아니라 `·` 로 표시하여 값이 있는 칸이 눈에 들어오게 합니다.
- 색은 `DESIGN.md` 에 따라 `--sk-*` 토큰만 사용합니다.

tool type 분류는 프론트엔드에 둡니다. 백엔드 `_tool_specs.model_to_tool_type()`
은 AMAT 모델에 `None` 을 반환하는 반면 프론트 `classifyToolType()` 은 네 종류를
모두 해석하는 기존 불일치가 있습니다. 이 화면은 계약에서 `eqp_model_cd` 를
가공 없이 전달하고 프론트가 표시 목적의 분류를 수행합니다. 두 분류기를
통일하는 작업은 실제로 필요하지만 이번 범위가 아니며, 이를 끌어들이면 UI
묶음 결정이 사무실 어댑터 동작에 의존하게 됩니다.

## 검토한 대안

| 대안 | 판단 |
| --- | --- |
| `/api/sem-list` 를 확장하여 전체 명부와 `connected` 플래그를 반환 | 기각. 6 개 feature 의 장비 선택 UI 에 접속 불가 장비가 유입됩니다 |
| 두 키를 각각 노출하고 브라우저에서 차집합 계산 | 기각. "연결됨"의 정의가 도메인 규칙인데 이를 UI 로 옮기며, 전체 명부를 두 번 전송합니다 |
| 기존 fab 별 장비 리스트에 미연결 pill 을 추가 | 이번 범위에서 제외. 엔드포인트와 계약이 생기면 이후 추가 비용이 작습니다 |
| VeritySEM/Provision 을 백엔드에서 제외 | 기각. prefix 를 모르는 신규 모델이 화면에서 사라집니다 |

## 범위에서 제외

- fab 별 장비 리스트의 미연결 pill 및 메타바 카운트
- 백엔드 `_tool_specs.model_to_tool_type()` 과 프론트 `classifyToolType()`
  통일
- 방화벽 해제 요청 자체의 자동화 및 요청 이력 추적

## 테스트

| 대상 | 내용 |
| --- | --- |
| `sem_list/tests/test_contract.py` | `get_pending_tools()` 가 `PendingToolRow` 형태를 반환하는지 |
| 신규 provider 계약 테스트 | mock 과 office 어댑터가 같은 계약을 만족하는지, 필수 컬럼 누락 시 컬럼 목록과 함께 실패하는지 |
| 분리 불변식 테스트 | `get_sem_list()` 와 `get_pending_tools()` 의 `eqp_id` 교집합이 공집합인지 |
| 라우트 테스트 | `GET /api/sem-list/pending` 응답 형태 |
| `utils/pendingToolMatrix.test.ts` | 집계, 미배정 묶음, 미분류 묶음, 합계 |

`.venv/bin/python -m pytest -q` 와 `npm test`, `npm run typecheck`,
`npm run lint`, `npm run lint:md` 를 모두 통과시킵니다.

## 문서 갱신

사무실 DB 지식은 항상 두 곳에 반영합니다.

1. `docs/datatables/sem_list.txt`
   - 키를 3 개로 정정하고 `v3_df_sem_list` 를 전사 명부로 기술합니다.
   - `updt_dt` 서술을 "명부 갱신 시각"에서 "장비 최초 반입 시각"으로
     정정하고, 구 장비에서는 부정확하다는 단서를 남깁니다.
   - 모든 장비가 반입 시 IP 를 가지며 방화벽에 막힌 상태라는 lifecycle 을
     추가합니다.
2. `sem_list/providers/mock.py` docstring
   - 같은 세 가지 사실을 반영합니다.
   - AMAT 관련 주석의 "every tool-scoped view filters them out" 서술을
     정정합니다. 이 화면은 의도적으로 제외하지 않습니다.

`office_example.py` 의 docstring 도 같은 내용으로 갱신합니다.
`office.py` 는 gitignore 대상 복사본이므로 사무실에서
`python -m scripts.sync_office_adapters sem_list` 로 갱신합니다.
