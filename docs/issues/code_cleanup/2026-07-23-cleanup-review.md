# 2026-07-23 작업 코드 정리 리뷰

> _작업 일시: 2026-07-24 02:10 ~_ · 리뷰 대상: 2026-07-23 커밋 전체
> (`abdf080..db5e39d`, 93개 파일, +5,225/-774)

본 문서는 2026-07-23에 작업한 코드를 다시 읽고, 죽은 코드와 불필요한 코드를
보수적으로 제거한 결과를 정리한 것입니다. `/simplify` 스킬의 4개 관점(재사용 ·
단순화 · 효율 · 고도)으로 병렬 리뷰한 뒤, 검증을 통과한 항목만 반영했습니다.

## 1. 리뷰 범위에서 제외한 영역

| 영역 | 제외 사유 |
| --- | --- |
| `back_dev_home/msr_image/**` | SDD 플랜이 17개 중 15번 과제에서 **진행 중 일시정지** 상태입니다. 남은 과제와 충돌하므로 손대지 않았습니다. |
| `front-dev-home/app/composables/useMsrImageApi*` | 위와 같은 플랜에 속합니다. |
| `openwiki/**` | 01:00 launchd 스케줄이 자동 생성한 결과물입니다. CLAUDE.md 규칙에 따라 수정하지 않았습니다. |

## 2. 기준선 (변경 전)

정리 작업이 무언가를 깨뜨렸는지 판단하려면 먼저 "원래 상태"를 기록해야 합니다.

| 항목 | 결과 |
| --- | --- |
| 백엔드 pytest | 393 passed · 5 skipped · **10 failed** |
| 백엔드 수집 오류 | `tests/test_office_provider_dispatch.py` 1건 |
| 프런트 `node --test` | 508 passed · 0 failed |
| 프런트 eslint | 오류 없음 |
| 프런트 `nuxt typecheck` | 오류 2건 (`skewvoir/RadiusChart.vue`) |

**기존 실패 10건은 어제 작업과 무관합니다.** 로컬에만 존재하는 gitignore 대상
`office.py` 어댑터들이 실제 Redis 접속을 시도하다 타임아웃하는 환경 문제입니다.
2026-07-23 이전 커밋으로 worktree를 만들어 확인한 결과, 그 시점에는 해당
테스트들이 수집조차 되지 않았습니다(untracked 어댑터가 worktree에 없기 때문).
typecheck 오류 2건도 어제 수정하지 않은 파일에서 발생한 기존 오류입니다.

## 3. 변경한 코드

### 3.1 meas_hist — 파생 로직을 `data.py`에서 어댑터 계층으로 이동

가장 핵심적인 변경입니다. 어제 커밋 `3726433`이 `fail_ratio`를 이미지 개수에서
파생시키는 로직을 `data.py`에 넣었는데, 이는 프로젝트 규약을 위반합니다.
CLAUDE.md는 `data.py`를 **어댑터를 고르기만 하는 안정적인 디스패처**로 규정하고
수정을 금지합니다.

실제 피해도 있었습니다. office 어댑터가 인덱스에서 `fail_ratio`를 읽어오지만
(`_float(src.get("fail_ratio"))`), 그 값은 바로 위 계층에서 조용히 덮어써지고
있었습니다. 즉 **office 어댑터는 틀린 값을 반환하고, 상위 계층이 우연히
고쳐주는** 구조였습니다. 어댑터를 직접 호출하는 코드가 생기면 그대로 깨집니다.

| 파일 | 변경 내용 |
| --- | --- |
| `back_dev_home/meas_hist/providers/_shared.py` | **신규.** `derive_fail_ratio()` 한 곳에 파생 · 클램프 · 반올림을 모았습니다. |
| `back_dev_home/meas_hist/providers/mock.py` | 직접 계산하던 식을 `derive_fail_ratio()` 호출로 교체했습니다. |
| `back_dev_home/meas_hist/providers/office_example.py` | 인덱스의 `fail_ratio` 필드를 읽지 않고 개수에서 파생하도록 바꿨습니다. |
| `back_dev_home/meas_hist/data.py` | `_normalize_row()`와 세 함수의 래핑을 제거해 순수 디스패처로 되돌렸습니다. |
| `back_dev_home/meas_hist/tests/test_ratio_normalization.py` | `data.py`를 monkeypatch하던 테스트를 공유 헬퍼 검증으로 옮기고 경계 사례를 추가했습니다. |

`_shared.py`라는 형태는 어제 같은 날 만들어진
`hardware/providers/bm_pm/_shared.py` 선례를 그대로 따랐습니다. 덕분에 구현은 한
곳에 유지하면서도 적용은 각 어댑터가 명시적으로 하게 됩니다.

### 3.2 meas_hist — 고아가 된 `_float()` 제거

위 변경으로 `office_example.py`의 `_float()` 헬퍼를 쓰는 곳이 사라졌습니다.
백엔드 전체 grep으로 다른 참조가 없음을 확인하고 삭제했습니다.

### 3.3 live-alarm — 쓰이지 않는 `export` 제거

| 파일 | 변경 내용 |
| --- | --- |
| `front-dev-home/app/composables/useLiveAlarmFeed.ts` | `HIGHLIGHT_MS`의 `export`를 뗐습니다. 파일 내부에서만 쓰이고 테스트도 참조하지 않습니다. |

같은 파일의 `POLL_INTERVAL_MS` · `nextDelay` · `applyPoll` 등은 테스트가 실제로
가져다 쓰는 의도된 이음새이므로 그대로 두었습니다.

## 4. 검토했으나 반영하지 않은 항목

정리 대상으로 지목됐지만, 확인 결과 **고치지 않는 편이 맞다고 판단한** 것들입니다.

| 항목 | 판단 |
| --- | --- |
| cd-sem / hv-sem `live-alarm.vue` 중복 | 29줄 중 6줄만 다른 중복이지만, 5개 페이지 쌍이 **모두** 같은 얇은 shim 구조입니다(`fail-issue` 15/2, `hardware` 28/6, `index` 31/6, `recipe-status` 28/6). 이것만 합치면 오히려 혼자 예외가 됩니다. |
| `FeatureTabs.vue`의 `live-alarm` 분기 | 탭은 뺐지만 분기는 "그 페이지에서 다른 탭이 활성화되지 않도록" 의도적으로 남긴 것이며 주석에도 명시돼 있습니다. |
| `live_alarm` writer의 상수 중복 | writer는 별도 스케줄러 서비스로 배포되어 `contracts.py`를 import할 수 없습니다. 각 파일 docstring에 의도가 설명돼 있는 **설계된 중복**입니다. |
| `live_alarm/providers/office_example.py`의 `_TOOL_SLUG` | 항등 매핑이지만, writer와 reader의 철자 계약을 검증하는 지점이라는 주석이 붙어 있습니다. 테스트 불가능한 office 코드에서 문서화된 가드를 걷어내는 것은 보수적이지 않습니다. |
| `useLiveAlarmFeed.ts`의 `apiSlug` | 사내 6번째 복사본이 맞습니다. 다만 이 파일은 `node --test`가 `~` 별칭을 풀지 못해 **상대 경로 import만** 쓸 수 있다는 제약이 있고, 새 파일 하나만 공용 헬퍼로 바꾸면 나머지 5곳과 오히려 불일치가 커집니다. 별도 과제로 남깁니다. |

## 5. 후속 과제 (이번에 하지 않음)

| 과제 | 내용 |
| --- | --- |
| `_diagnose()` 4중 중복 | `fdc/office_example.py` · `bm_pm/office_example.py` · `scripts/diagnose_fdc_office.py` · `scripts/diagnose_fdc_standalone.py`가 같은 "어느 절이 결과를 0으로 만드는가" 진단을 각자 구현합니다. standalone은 **repo import 없이 사무실에서 돌아야 한다**는 제약 때문에 정당한 복사본이지만, 나머지 두 office 어댑터는 이미 `_office_search.py`를 공유하므로 합칠 수 있습니다. 사무실 배포 코드라 홈에서 검증이 불가능해 미뤘습니다. |
| `scripts/diagnose_fdc_office.py` 존치 여부 | standalone이 진단 범위 상 상위집합이고(`check_clauses` 보유), office 스크립트는 repo import·cp949 인코딩 문제로 **정작 사무실에서 실행되지 않습니다**. 다만 템플릿 드리프트 검사(`check_adapter_copy`)는 이쪽에만 있고, 형제 스크립트(`diagnose_recipe_tat_office.py`)도 조사 종료 후 존치된 선례가 있어 임의 삭제하지 않았습니다. |
| office 어댑터 I/O 직렬 실행 | `live_alarm` `get_board()`의 Redis 왕복 4회, `bm_pm`의 OpenSearch 순차 조회 2건을 각각 파이프라인·병렬화할 수 있습니다. 다만 홈에서 검증 불가능하고 hot path도 아니라 미뤘습니다. |
| hv-sem mock의 `vendor_nm="AMAT"` | `meas_hist/providers/mock.py`의 TP3000 픽스처가 AMAT으로 돼 있으나 TP 계열은 HITACHI입니다. 어제 작업 범위 밖의 기존 데이터 오류라 이번에는 건드리지 않았습니다. |

## 6. 검증 결과 (변경 후)

| 항목 | 기준선 | 변경 후 | 판정 |
| --- | --- | --- | --- |
| 백엔드 pytest | 393 passed · 10 failed | **396 passed · 10 failed** | 통과 +3(신규 테스트), 실패 목록 **완전 동일** |
| 프런트 `node --test` | 508 passed | **508 passed** | 동일 |
| 프런트 eslint | 오류 없음 | **오류 없음** | 동일 |
| 프런트 `nuxt typecheck` | 오류 2건 | **오류 2건** | 신규 오류 0 |

추가로 `data.py`의 정규화를 걷어낸 뒤에도 결과가 달라지지 않는지 확인하기 위해,
네 개 진입점(`get_meas_hist` · `search_meas_hist` · `find_meas_hist_by_msr` ·
`MOCK_SEARCH_FIXTURES`)의 모든 행에 대해 `fail_ratio`가 개수에서 파생한 값과
일치하는지 대조했고, 불일치는 없었습니다. office 템플릿은 홈에서 import되지
않으므로 `py_compile`로 문법을 확인했습니다.
