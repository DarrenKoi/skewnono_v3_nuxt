# device-statistics/comparison — LOT 추이 차트 재설계

작성일: 2026-08-01
대상: `front-dev-home/app/components/cdsem/comparison/TrendChart.vue`

## 배경

`device-statistics/comparison` 페이지의 LOT 요약 표에서 행을 클릭하면
`LotDetailModal` 이 열리고 그 안에 추이 차트가 표시됩니다. 이 차트는 현재
`health` / `composition` / `paras` 세 모드를 제공하지만, **세 모드 모두
파라미터의 실제 개수를 보여주지 않습니다.**

| 모드 | 실제 계산 | 문제 |
| --- | --- | --- |
| `health` | `violation_ratio` = (cap 초과 카테고리 수) / 4 | 값이 0/0.25/0.5/0.75/1 다섯 개뿐인 계단식이며, cap 자체가 프런트엔드 mock (`useLotHealthMock.ts`) 의 잠정 규칙입니다 |
| `composition` | 날짜별 합계로 나눈 누적 영역 (`val / total`) | 날짜마다 0→100% 로 정규화되므로 절대 개수가 수학적으로 소거됩니다. 네 para 가 모두 두 배가 되어도 그래프는 전혀 움직이지 않습니다 |
| `paras` | para 별 폴리라인, **각 선을 자기 최댓값으로 정규화** | 선끼리 크기 비교가 불가능하고 실제 숫자가 어디에도 표시되지 않습니다 |

즉 "이 디바이스의 파라미터 개수가 시계열로 어떻게 변했는가" 라는 질문에
답하는 모드가 하나도 없습니다. 정규화가 근본 원인이며, 두 정규화는 서로 다른
축을 제거합니다. 날짜별 정규화(`composition`)는 **크기** 축을,
시리즈별 정규화(`paras`)는 **시리즈 간 비교** 축을 없앱니다. 두 정규화 모두
60px 높이 스파크라인에서 작은 값을 보이게 하려는 레이아웃 제약에서 나왔지만,
이 차트는 넓은 모달 안에서만 쓰이므로 그 제약은 더 이상 존재하지 않습니다.

## 결정 사항

1. **탭은 `개별` / `누적` 두 개.** `health` 와 `composition` 모드는 삭제합니다.
2. **`누적` = 절대 개수 누적 영역.** 날짜별 정규화를 제거하여 상단 경계선이
   실제 `para_all` 합계가 되도록 합니다.
3. **`개별` = 하나의 실제 개수 축을 공유하는 4개 선.** 범례 클릭으로 특정
   para 만 격리해서 볼 수 있습니다.
4. **ECharts 로 재구현.** 기존 수제 SVG 를 버리고 `useEchart` 를 사용합니다.

`health` 개념 자체는 사라지지 않습니다. `LotTable.vue` 의 health 컬럼, 정렬,
필터, CSV 내보내기와 `StackedBar.vue` 의 cap 초과 표시는 그대로 유지되며,
`classifyHealth` · `healthSwatches` · `useLotHealthMock` 도 모두 남습니다.
삭제되는 것은 정보량이 거의 없던 추이 **선** 하나뿐입니다.

## 변경 대상

| 파일 | 변경 |
| --- | --- |
| `app/utils/paraTrendOptions.ts` | 신규 — 순수 함수. 추이 응답 → ECharts option |
| `app/utils/paraTrendOptions.test.ts` | 신규 — `node --test` |
| `app/components/cdsem/comparison/TrendChart.vue` | ECharts 호스트로 재작성 |
| `app/components/cdsem/comparison/healthTokens.ts` | `paraColors` / `paraColorsDark` 재배치 |
| `app/components/cdsem/comparison/LotDetailModal.vue` | 사라진 prop 정리 |

## 팔레트 — 측정 결과에 근거한 재배치

기존 `paraColors` 는 dataviz 팔레트 검증기에서 **양쪽 모드 모두 실패**합니다.

| 검사 | light | dark |
| --- | --- | --- |
| 정상 시각 최소 분리 | **FAIL** `para_9`↔`para_13` ΔE 10.2 (기준 15) | **FAIL** ΔE 9.1 |
| 색각 이상 분리 | **FAIL** 같은 쌍 ΔE 3.1 (protan) | **FAIL** ΔE 2.1 |
| 채도 하한 | FAIL `para_5` 가 회색으로 읽힘 | FAIL `para_5` |
| 명도 대역 | PASS | FAIL 네 색 모두 대역 밖 |

원인은 명확합니다. 이 팔레트는 주석에 "heaviest weight → lightest weight" 라고
**순서 척도로 선언**되어 있지만, 실제 명도는 0.62 → 0.72 → 0.66 → 0.62 으로
전혀 단조롭지 않습니다. 선언된 순서가 수치로 강제된 적이 없어서 가운데 두
단계가 충돌합니다.

`para_16 / 13 / 9 / 5` 는 서로 무관한 네 개의 정체성이 아니라 **측정 밀도의
순서 척도**이므로, 단일 색상(warm hue 45°)에 명도를 단조 증가시킨 순서형
램프로 교체합니다.

| | para_16 | para_13 | para_9 | para_5 |
| --- | --- | --- | --- | --- |
| light | `#772e00` | `#a64a18` | `#cc7044` | `#e79d7b` |
| dark | `#a64a18` | `#cf6835` | `#e7936c` | `#fbbea3` |

검증기 결과는 **양쪽 모드 모두 ALL CHECKS PASS** 입니다 (명도 단조 ✓,
인접 ΔL ≥ 0.06 ✓, 밝은 끝 대비 light 2.14:1 / dark 2.79:1 ✓, 단일 색상 ✓).

Okabe-Ito 기반 범주형 팔레트도 시도했으나, light 는 통과하지만 dark 의 좁은
명도 대역 `[0.48, 0.67]` 안에서 protan 분리 기준을 끝내 넘기지 못했습니다.
따라서 순서형 램프는 취향이 아니라 측정 결과로 선택된 안입니다. 명도가
정체성을 전달하므로 색각 이상에 대해 **구조적으로** 안전하다는 이점도 있습니다.

단일 색상 램프는 선이 교차할 때 구분이 약해지므로, 정체성을 색에만 의존하지
않도록 보조 부호화를 셋 추가합니다.

- 항상 표시되는 범례
- 선 끝의 직접 라벨 (`p16` / `p13` / `p9` / `p5`)
- 시리즈별 심볼 구분 (circle / rect / triangle / diamond)

이 색은 `StackedBar.vue` 및 비교 페이지의 ECharts 누적 막대 카드와 공유되므로
네 표면이 함께 갱신되어 색이 계속 동일한 대상을 가리킵니다.

## 모달 안에서의 크기 보정

`useEchart` 는 `onMounted` 시점에 캔버스를 초기화하고 이후에는
`window.resize` 에만 반응합니다 (`useEchart.ts:164-167`). 이 저장소에서
`UModal` 안에 ECharts 를 넣은 선례가 없어, 모달이 열리는 동안 컨테이너 폭이
0 이면 차트가 잘못된 크기로 고정될 수 있습니다.

호스트 `div` 에 `v-if="open"` 을 걸고 컨테이너에 `ResizeObserver` 를 붙여
`chart.resize()` 를 호출합니다. 브라우저 창 크기 변경으로 모달이 재배치되는
경우도 함께 처리됩니다.

## 삭제되는 코드

- `compact` prop 과 320×60 코드 경로 전체 — 모든 호출자가 `false` 를 넘기므로
  실행된 적이 없습니다
- `defaultMode` prop — 호출자 하나, 값 하나
- `healthValues` · `healthDots` · `bandRed*` · `bandYellow*` · `bandGreen*`
- `compositionPaths`

## 테스트

`paraTrendOptions.test.ts` 는 브라우저 없이 순수 함수만 검증합니다
(이 저장소에는 컴포넌트 마운팅 하네스가 없습니다).

- 절대 개수가 보존됩니다 — 정규화가 다시 들어오면 실패합니다
- 누적 모드의 상단 합계가 `para_all` 과 일치합니다
- 데이터가 없는 날짜는 0 이 아니라 결측으로 처리됩니다
- 시리즈 순서가 `paraOrder` 와 일치합니다
- 두 팔레트가 명도 단조성을 유지합니다 — 램프가 다시 조용히 깨지는 것을
  막는 회귀 방지 장치입니다
