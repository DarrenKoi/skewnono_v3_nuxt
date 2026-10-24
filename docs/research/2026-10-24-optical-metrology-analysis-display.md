# 광학 계측(두께 · 분광 엘립소미터)은 무엇을 재고 어떻게 보여줄 것인가

> - 작성일은 2026-10-24 입니다. 코드와 문서를 읽고 웹 원자료를 확인해 쓴 조사 보고서이며,
>   구현은 하지 않았습니다.
> - 근거가 된 조사 노트 3개는
>   [`2026-10-24-optical-metrology-analysis-display-notes/`](2026-10-24-optical-metrology-analysis-display-notes/)
>   에 있습니다 — 로컬 코드 정찰, 외부 근거(물리·표준·분석 방법), 표시 방식 트레이드오프.
> - 근거 표기는 기존 보고서와 같습니다. **[확인]** 은 코드·원문을 직접 읽은 것,
>   **[요약만]** 은 검색 결과나 초록만 본 것, **[벤더]** 는 벤더 자료(홍보 포함),
>   **[추론]** 은 이 보고서의 추론입니다. 사무실 데이터 접속과 브라우저 실험은 없었습니다.
> - **2026-10-24 리뷰 개정.** 사용자 목표(두께 **와 OCD** 를 모두 다루고, 스큐보아와 같은 분석 방법과
>   recipe 기반 정보를 제공)에 맞춰 다시 읽고 고쳤습니다. 무엇을 왜 바꿨는지는 바로 아래
>   [리뷰 결과](#리뷰-결과-2026-10-24) 에 모았습니다.

## 리뷰 결과 (2026-10-24)

초판은 **두께(박막) 엘립소미터 한 가지만** 보고 썼습니다. 사용자의 목표와 비교하면 빈 곳이 셋, 틀을 바꿔야 하는
곳이 하나 있었습니다.

| # | 초판의 상태 | 고친 내용 | 위치 |
| --- | --- | --- | --- |
| 1 | OCD(scatterometry)가 한 줄도 없음 | 두께와 OCD 를 같은 광학·다른 모델로 나눠 비교하고, OCD 전용 품질 신호와 분석을 추가 | §1-5, §4 |
| 2 | "스큐보아에 얹는 것은 막혔고 막힌 게 맞다" 에서 멈춤 | **코드 울타리**와 **분석 방법**을 분리. 스큐보아의 개념(검토 후보·기준 집단·검토 근거 패밀리)을 광학 도메인에 옮기는 대응표 추가 | 요약, §3-1 |
| 3 | recipe 기반 정보가 없음 | 이미 있는 e-beam recipe 화면(recipe 검색·lateral·TAT·device-statistics)을 광학 recipe 에 대응시키고, 광학 recipe 에만 있는 것(스택/OCD 모델·라이브러리 개정판)을 정리 | §3-2 |
| 4 | D′(장비 매칭)이 저장소의 기존 TTTM 기능과 연결되지 않음 | D′ 을 "광학 TTTM" 으로 부르고, D(편차 감시)와의 구분을 저장소 용어에 맞춤 | §3 표 |

작은 수정: §3 제목의 후보 수(여섯 → 일곱, D′ 포함), §4 제목 오타("팩" → "팹"), §7-2 의 목 프로토타입이
이제 존재하므로(`.scratch/optical-metrology-preview/index.html`) 그 결과를 반영했습니다.

**리뷰어 판단 하나 [추론].** 초판 권장 순서(A+D → B → C)와 codex 반대안(질문지 → 상세+품질 → A → C) 사이에서,
이 리뷰는 §3 끝에 **세 번째 안**을 적었습니다 — 스큐보아식 검토 흐름을 먼저 세우되 적합 품질을 그 흐름의
"실행/데이터 품질" 게이트로 넣는 안입니다. 두 안을 덮지 않고 나란히 둡니다. 결정은 사용자 몫입니다.

## 요약

광학 계측은 **두께**(평판 막의 층 두께·n·k)와 **OCD**(주기 패턴의 CD·높이·측벽각 같은 형상)
두 가지이고, 같은 Ψ/Δ·반사율 신호에서 출발하지만 모델·타깃·품질 신호·쓰는 사람이 다릅니다(§1-5).
아래 첫 문단은 **코드** 이야기입니다 — 스큐보아의 **분석 방법**은 그대로 옮길 수 있고, 그래야 합니다(§3-1).

두께·엘립소미터 데이터를 스큐보아 **코드**에 얹는 것은 **막혀 있고, 그래서 막힌 게 맞습니다**. 스큐보아는 `cd-sem`·`hv-sem`
두 SEM 계열에만 열리도록 코드에서 명시적으로 울타리를 쳐 두었고(`frontend/app/utils/skewvoirLinks.ts:11-16`,
`utils/toolType.ts:47-53`) [확인], 그 데이터 계약에는 **파장 축이 없습니다** — `MsrParamSummary` 는 파라미터당
`mean/std/min/max/unit` 스칼라 다섯 개뿐이라(`backend/msr_file/contracts.py:66-83`) [확인] Ψ/Δ 스펙트럼을 담을
자리가 없습니다. 따라서 답은 "스큐보아를 확장"이 아니라 **AFM 이 걸었던 길**입니다: 자기 도메인, 자기 feature
폴더, 자기 화면, 공통 차트 래퍼(`useEchart`)와 디자인 토큰만 공유(ADR 0006 이 Thickness 를 이미 독립 도메인으로
판정했습니다 — `docs/adr/0006-page-grouping-by-domain-and-object.md:40-70`) [확인].

그 위에서의 권장 구성은 **두 개의 층**입니다. 첫 번째 층은 소유자가 이미 스큐보아에서 묻는 질문을 그대로
옮긴 것입니다 — 시간 · lot · eqp_id · recipe · site 축으로 **파생값(두께, n, k)** 을 비교하는 추세와 장비 편차.
이 축들은 저장소에 전부 이미 있고, 스큐보아의 `tsx=eqp`("장비 편차" 렌즈)와 `tsb=resid`(기준선 대비 잔차)가
그 모양을 증명합니다 [확인]. 두 번째 층이 광학 계측에서 **절대 생략하면 안 되는** 것입니다: 어떤 두께 숫자 옆에도
그 숫자를 만든 **적합 품질(MSE 또는 χ², 잔차, 파라미터 오차한계, 상관 플래그)** 을 붙이는 일. 엘립소미터의 파생값은
측정값이 아니라 회귀 결과이고, 두께↔n 상관이 퇴화하면 **핏이 틀렸을 때 숫자가 가장 그럴듯해 보이기 때문입니다**
[벤더: Horiba·Woollam·OptiLayer] [확인: 문헌]. 이미징 분광 엘립소미터(이하 이미징 SE)의 원시 큐브는 브라우저에
실을 수 없는 규모이므로(1회 취득당 스펙트럼 1,000만 개 이상 [확인: Nature Communications 2025, 삼성전자]),
**전체 큐브 전송**은 배제하되 **선택한 ROI·픽셀의 지연 조회**는 별개의 문제입니다. 서버 축소 계약을 먼저 정해야 합니다.

가장 큰 위험은 UI 가 아니라 **근거의 부재**입니다. `docs/datatables/` 에 두께·엘립소미터 소스가 하나도 없고 [확인],
내부 브레인스톰은 이미 "측정 소스와 식별자가 확인되기 전에는 보류", "AFM ↔ SEM ↔ Thickness 자동 연결 — 같은
웨이퍼·같은 스텝이라는 식별자 검증이 없습니다" 라고 거절을 기록했습니다(`docs/research/2026-10-05-page-value-brainstorm.md:493,516`)
[확인]. 그러니 장비 도입 전에 할 수 있는 가장 값진 작업은 화면이 아니라 **벤더 질문지 한 장**과, 그 답을 기다리지
않고 집에서 검토할 수 있는 **정직한 목 스펙트럼 프로토타입**입니다.

## 1. 이 데이터는 실제로 무엇인가

광학 계측은 한 종류의 데이터가 아니라 **서로 다른 세 층**이고, 이 셋을 섞으면 화면이 거짓말을 합니다.

### RAW — 스펙트럼

측정되는 물리량은 각 파장(그리고 각 입사각 AOI)에서의 Ψ 와 Δ 입니다. ρ = r_p/r_s = tan(Ψ)·e^(iΔ)
[벤더/확인: Woollam 튜토리얼, 교과서]. 일반화 엘립소메트리나 뮬러 행렬 장비는 여기에 행렬 성분(m11..m33 등)과
탈편광(depolarization)이 더해집니다. 취득 조건 — 파장 범위·분해능, 입사각, 방위각, 스팟 크기 또는 픽셀 크기·시야,
적분 시간, 평균 횟수 — 도 RAW 의 일부입니다.

### DERIVED — 회귀로 뽑은 값과 그 값의 신뢰도

두께는 층별 nm 값, 광학 상수는 n·k(또는 ε1·ε2)를 파장 함수로 냅니다. Cauchy(투명막), Tauc-Lorentz(흡수 비정질·반도체),
Drude(금속), B-spline(Kramers-Kronig 일관 기저, 오실레이터 개수를 짐작하지 않아도 됨) 같은 분산 모델에 최소자승
회귀를 돌려 얻습니다 [벤더: Horiba, JVST B 2020].

**여기가 핵심입니다.** 이 값들은 측정값이 아니라 **모델이 주어졌을 때의 추정치**입니다. 그래서 함께 오는 것들이
있습니다: MSE(Woollam 계열 관례) 또는 χ²(Horiba 계열 관례), 잔차 배열, 파라미터 오차한계, 상관 행렬, 수렴 정보.
Horiba 는 "χ² ≈ 1 이면 단순 단일막에서 매우 좋은 것, 복잡한 시료는 결과가 물리적이라는 조건으로 ~10 까지 허용" 이라는
가이드를 주지만 **동시에** 잔차의 육안 비교, 물리적 타당성, 오차한계(크면 모델 문제), 상관 행렬(강하면 모델 문제 —
각도를 늘리거나, R/T 데이터를 더하거나, 파라미터를 고정해서 푼다), 빠른 수렴(유일핏의 징후)을 전부 보라고 합니다
[벤더: Horiba 데이터 분석 페이지] [확인: 원문 판독]. Woollam 도 MSE 가 낮다고 좋은 모델이 아니며 복잡도를 올리면
MSE 는 신뢰도 없이 내려간다고 명시합니다 [벤더: CompleteEASE 매뉴얼]. NIST 는 **같은 엘립소메트리 데이터에서도
분석 알고리즘이 다르면 두께가 다르게 나온다**고 기록합니다 — 모델 의존성 자체가 소급성 문제라는 뜻입니다 [확인].

**설계 규칙 [추론]:** MSE 임계값 숫자를 코드에 하드코딩하지 말 것. 관례가 벤더마다 다르고 정의도 다릅니다.
대신 "fit_status" 같은 **범주 플래그**를 계약에 두고, 그 값이 장비·레시피마다 정해지도록 할 것.

### CONTEXT — 그 숫자가 누구의 것인가

lot_id, wafer_id(+slot), recipe 이름 **그리고 개정판**, 광학 스택 모델의 식별자와 개정판(모델이 결과의 일부이므로),
장비 ID · 소프트웨어 버전, site/pixel 좌표(원점·방향 규칙과 edge exclusion 포함), 타임스탬프, 층 정의, 운영자,
교정 상태, 사용한 AOI, 측정 상태 플래그.

### 이미징 SE 는 다른 동물입니다

점 스팟 SE 는 "사이트 N 개 × 각 사이트 스펙트럼" 이지만, 이미징 SE 는 **픽셀당 스펙트럼의 하이퍼스펙트럴 큐브**입니다.
삼성전자가 발표한 이미징 뮬러행렬 SE 시스템은 20×20 mm 시야를 3200×3200 픽셀(6.5 µm)로, 35개 파장에서 잡아
**1회 취득당 스펙트럼 1,000만 개 이상**을 만듭니다 [확인: Nature Communications 2025, 원문 직접 판독].
이 시스템은 **스테핑 없이 전 웨이퍼를 잡는 게 아닙니다** — shot 영역 단위로 스테이지가 이동하고, shot 하나를
20×20 mm 시야 때문에 2×2 사분면으로 나눠 사분면 사이를 스테핑하며, shot mark 인식으로 정렬해 다음 shot 으로
넘어갑니다 [확인: 원문 인용 "Wafer-level data acquisition is performed using a stepping-stage approach…"].
따라서 표시 단위에도 shot / 사분면 계층이 자연스럽게 존재합니다.

위 논문에서 확인한 차이 둘, 그리고 **이것이 한 시스템의 사례일 뿐 이미징 SE 전체의 특성이 아니라는** 단서입니다:

1. 그 논문은 픽셀마다 물리 모델 회귀를 돌리지 않고 **기준 계측(SEM)으로 훈련한 ridge regression** 을 씁니다
   [확인: 원문 인용]. 그러면 픽셀별 "핏 진단(MSE)" 이 존재하지 않고, 신뢰 신호가 **모델 훈련 품질과 RMSE,
   기준 계측과의 상관**으로 옮겨 갑니다. 그러나 **물리 모델을 쓰는 이미징 SE 도 있습니다** [벤더: Park Systems
   학습 자료]. 그래서 "이미징 SE 에는 MSE 레이어가 없다" 는 일반화는 틀립니다 — **계약이 두 경우를 다 표현해야
   합니다**: 적합 진단이 있으면 싣고, 없으면 `fit_status` 를 `not-applicable` 로 두어 **진단 부재를 정상으로
   꾸미지 않아야** 합니다 [추론].
2. 그 논문이 실제로 보여주는 것은 원시 스펙트럼이 아니라 **두께·CD·오버레이의 웨이퍼 맵, shot 단위 맵, 히스토그램,
   에러 맵**입니다. 즉 이미징 SE 의 가치는 밀도 자체(CVD 노즐 육각 패턴, 동심 CD 변화, shot 단위 오버레이 같은
   희박 샘플링으로는 안 보이는 공간 서명)에 있고, 표시 대상은 파생값 맵입니다 [확인].

### 1-5. 두께와 OCD — 같은 광학, 다른 모델

위 RAW/DERIVED/CONTEXT 세 층은 두 방식에 똑같이 있습니다. 다른 것은 **DERIVED 를 만드는 모델과 그 모델이
틀리는 방식**입니다. 그래서 화면도 "같은 뼈대, 다른 품질 패널" 이 됩니다 [추론].

| 항목 | 두께(박막) 계측 | OCD(scatterometry) |
| --- | --- | --- |
| 타깃 | 패턴 없는 막 또는 패드(넓은 평판 영역) | 주기 패턴 — scribe line 테스트 키 또는 in-die 셀 |
| 광학 모델 | 1-D 다층 스택(Fresnel/Airy 재귀), 분산 모델(Cauchy·Tauc-Lorentz·B-spline) | 격자 단면의 전자기 계산(RCWA 등), 막 스택 + 기하 프로파일 |
| 측정 신호 | Ψ/Δ(SE), R(λ)(반사율계) | Ψ/Δ, 뮬러 행렬 성분, 편광·방위각별 반사율 — 신호 종류가 더 많음 |
| 결과 파라미터 | 층별 두께, n·k | top/mid/bottom CD, 높이, 측벽각(SWA), recess, 경우에 따라 overlay·tilt |
| 푸는 방법 | 실시간 회귀가 기본 | **라이브러리 매칭**(미리 계산한 스펙트럼 표) 또는 실시간 회귀, 최근에는 **기준 계측으로 훈련한 ML** [요약만: 특허 US7716003 계열, SPIE 2024 GAA, KLA SpectraShape DRAM 사례] |
| 핏 품질 신호 | MSE/χ², 잔차, 오차한계, 두께↔n 상관 | 위 전부 + **GOF**(벤더별 정의), **라이브러리 경계 걸림**(플로팅 파라미터가 범위 끝에 붙음), 파라미터 간 상관(CD↔SWA↔높이) [요약만: 상관이 정밀·정확도를 제한한다는 특허·SPIE 서술] |
| 정확도의 근거 | XRR·TEM 단면과의 일치 | **CD-SEM·HV-SEM·TEM·AFM 기준 계측과의 상관**(기울기·오프셋·R²) — ML 방식이면 훈련 품질 자체 [요약만] |
| 주 사용자·질문 | 증착·CMP·식각 공정: "막이 원하는 두께로, 고르게 올라갔나" | 포토·식각 공정: "패턴 형상이 원하는 모양으로 나왔나" |

여기서 저장소에 중요한 사실이 둘 나옵니다.

1. **OCD 는 이 저장소의 SEM 데이터와 같은 질문을 다른 장비로 답합니다.** CD 는 CD-SEM 이 재고, OCD 는 그
   CD 를 광학으로 잽니다. KLA 의 DRAM in-die 사례는 OCD ML 모델을 **HV-SEM 기준값으로 훈련**했다고 보고합니다
   [요약만: SPIE 12955 초록]. 그러니 "OCD ↔ CD-SEM/HV-SEM 상관" 화면은 SKEWNONO 만 줄 수 있는 가치가
   될 수 있습니다. 다만 내부 브레인스톰이 **같은 웨이퍼·같은 스텝 식별자 검증 없는 자동 연결을 이미 거절**했으므로
   (`2026-10-05-page-value-brainstorm.md:516`) [확인], 이것은 식별자 결합이 확인된 뒤의 일입니다.
2. **OCD 의 핏 품질은 두께보다 더 숨기 쉽습니다** [추론]. 플로팅 파라미터가 많고 서로 강하게 상관하며,
   라이브러리 방식은 "범위 안에서 가장 가까운 점" 을 항상 돌려주므로 범위 끝에 붙은 값도 정상 숫자처럼 보입니다.
   계약에 `fit_status` 외에 **경계 걸림 플래그**와 **모델/라이브러리 개정판**이 있어야 하는 이유입니다. ML 방식이면
   §1 이미징 SE 와 같은 경우가 되어 픽셀별 MSE 가 없고, `fit_status = not-applicable` + 모델 훈련 정보로 대체합니다.

두께와 OCD 를 **한 feature 의 두 측정 종류**로 둘지 **두 feature** 로 둘지는 벤더 답을 본 뒤 정합니다.
장비가 같고(같은 SE 가 두 recipe 를 다 돌리는 경우가 흔함) 계약 뼈대가 같으므로 한 feature + `measurement_kind`
(`film` / `ocd`) 축이 기본안입니다 [추론]. 화면 분리는 그 축을 보고 하면 됩니다.

## 2. 저장소가 말하는 것

- **Thickness 는 stub 입니다.** `frontend/app/pages/thickness/index.vue:1-27` 은 "coming soon" 안내문 한 장이고,
  AFM 교체(2026-05) 때 내비게이션에서 숨겼으며, 데이터 경로는 없습니다 [확인].
- **스큐보아는 제3 계열에 대해 배선만 안 된 게 아니라 명시적으로 차단돼 있습니다.** `hasSkewvoir()` 는
  `cd-sem`·`hv-sem` 만 통과시키고 [확인], 그래서 광학 계측을 스큐보아 워크스페이스에 태우는 일은 "재사용" 이 아니라
  **울타리를 허무는 변경**입니다. 허물 이유가 없는 것도 아닙니다(아래 §3 참고) — 다만 그 비용을 알아야 합니다:
  스큐보아의 호환성 서명은 `msr_file` 응답 구조에서 추출되고, readiness 매트릭스가 `site_layout_hash` 같은
  사무실 전용 키를 씁니다(`utils/skewvoirAnalysis/types.ts:100-118`) [확인]. 단 "해시가 없으면 통째로 잠긴다" 는
  뜻은 **아닙니다** — `layoutReadiness()` 는 해시가 없어도 좌표 충돌이 없고 사이트 교집합이 있으면
  `ready`/`limited` 를 허용하고, 그 경우 교집합 개수를 근거로 실어 보냅니다
  (`frontend/app/utils/skewvoirAnalysis/compatibility.ts:275-291`) [확인]. 즉 광학 도메인이 배울 것은
  "해시를 반드시 받아야 한다" 가 아니라 **해시가 없을 때 무엇을 근거로 비교를 허용하고 그 근거를 어떻게
  표시할 것인가** 라는 설계입니다 [추론].
  파장 축을 가진 소스를 이 구조에 넣으면 그 잠금장치 전체를 다시 설계해야 합니다 [추론].
- **AFM 이 선례입니다.** 별도 `backend/afm/`(routes · contracts · data · providers · MIGRATION · tests), 별도
  페이지 트리, 별도 컴포넌트 트리(38 파일), 별도 순수 utils(19 모듈 + 각자 colocated `.test.ts`), 별도 내비,
  `_logging/feature_map.py:44-48` 의 `AFM_FAMILY` 상수, 레이트리밋 면제 목록 [확인]. 공통으로 쓴 것은 `useEchart`,
  `usePersistedState`, `useTableDownload`, `--sk-*` 토큰, `/s/` 단축링크뿐입니다 [확인].
- **AFM 계약에서 배울 것 하나.** AFM 상세는 `data[]` 가 **타입 없는 파일별 컬럼 dict** 입니다 — 레시피마다 컬럼이
  달라서(최대 51개) 그렇고, 프로파일 점은 `{x, y, z|null}` + 메타에 `x_unit/y_unit/z_unit` 을 **데이터와 함께**
  실어 절대 통일하지 않습니다(`backend/afm/contracts.py:80-114`) [확인]. 광학 계측도 같은 문제를 가집니다:
  레시피(스택 모델)마다 나오는 파라미터 집합이 다르고, 단위도 nm/Å/무차원이 섞입니다. **스키마를 레시피별로
  열어 두되, 스펙트럼 한 곡선은 AFM 프로파일과 구조적으로 같은 물건**이라는 점이 중요합니다
  (x = 위치 ↔ 파장, y = 높이 ↔ Ψ/Δ) [추론].
- **재사용 가능한 차트는 거의 다 있습니다.** line 65곳, scatter 37, bar 16, heatmap 5, boxplot 3, custom 2 [확인: grep 계수].
  스펙트럼 뷰에 가장 가까운 기존 부품은 `components/afm/trend/ProfileOverlay.vue`(다중 곡선 1-D 오버레이 +
  레벨링 컨트롤)이고 [확인], 웨이퍼 맵은 `ebeam/skewvoir/WaferMap.vue`(`type: 'custom'`)와
  `utils/waferMapOptions.ts` 의 공유 옵션 계약(crosshair · grid · dieGrid · notch · colorMode · colorMin/Max)이
  있습니다 [확인]. **스펙트럼 전용(이중 Y축 Ψ & Δ vs 파장) 컴포넌트는 트리에 없습니다** [확인].
- **`msr_file` mock 에 이미 THICK 파라미터 계열이 있습니다** — `PARAMETER_MAPPING["THICK"] = ("THICKNESS",
  "UNIFORMITY", "REFRACTIVE_INDEX")`, 스펙 `10.0~100.0 nm`(`backend/msr_file/providers/mock.py:266,406`) [확인].
  이건 SEM pickle 모양 안의 mock 전용 계열일 뿐 광학 소스가 아니고, 게다가 `UNIFORMITY`·`REFRACTIVE_INDEX` 는
  `_DEFAULT_SPEC`(nm)으로 떨어져 **단위가 이미 틀려 있습니다** [확인]. 광학 도메인을 만들 때 이 가짜 계열을
  광학 데이터의 근거로 오해하지 말 것 — 오히려 정리 대상입니다 [추론].
- **두 개의 grain 이 구조의 경첩입니다.** `meas_hist` 는 측정당 한 줄의 이력 색인(축), `msr_file` 은 건별 전체
  페이로드(값·이미지·FDC) [확인]. 기존 보고서가 스큐보아와 AFM 의 공통 벽으로 지목한 것이 정확히 이 요약 층의
  부재입니다 — "측정 한 건을 한 줄로 요약한 이력 층이 없다는 것이 공통 원인"
  (`docs/research/2026-10-09-analysis-service-directions.md`, §공통 벽) [확인]. **광학 계측은 이 함정을 처음부터
  피할 수 있는 유일한 기회입니다**: 새 계약을 짤 때 목록 응답에 측정당 요약(두께, n, k, fit_status)을 실으면
  건별 상세 요청 없이 추세·장비 편차가 섭니다. AFM 이 팁 열 적재(2026-10-07)로 사후에 얻은 것을 여기서는
  사전에 얻을 수 있습니다 [추론].

## 3. 후보 일곱 개 — 무엇을 답하고 얼마가 드나

| # | 방식 | 답하는 질문 | 필요한 축(**신규**) | 비용 | 데이터량 위험 | 목 검증 |
| --- | --- | --- | --- | --- | --- | --- |
| A | 파생값만 스큐보아식 비교(두께·n·k 를 "파라미터" 로) | 이 장비·lot·recipe 가 시간 따라 흐르는가 | 기존 전부(시간·lot·eqp·recipe·site) + **fit_status** | 최저 — AFM 시계열 비교 복제 | 없음(사이트당 스칼라) | meas_hist 모양 행 + 사이트별 값 |
| B | 스펙트럼 우선 상세(측정 Ψ/Δ + 모델 핏 + 잔차, site별, AOI 토글) | 이 두께 숫자를 믿어도 되는가 | **파장 · AOI · 스택모델 식별자 · 적합 메타(MSE, 파라미터, 오차한계, 상관)** | 중간 — 다중 시리즈 line + 잔차 패널, 곡선당 ~10³ 점이라 렌더 부담은 작을 것으로 예상 [추론·미측정] | 낮음 — 사이트별 지연 로딩이면 건당 수백 KB | 목 스펙트럼 생성(§7-2) + **높은 MSE 핏과 MSE 는 낮으나 비유일한 핏 둘 다** 포함 |
| C | 웨이퍼 맵 우선 공간 뷰(두께/MSE 균일도 히트맵, 점 도구는 사이트 그리드, WTW 는 맵 나란히) | 웨이퍼 어디가 규격 밖이고 그 서명이 장비 모양인가 | site x-y(기존) + 이미징 SE 용 **고밀도 픽셀 그리드** | 중간 — heatmap + visualMap, ≤10⁴ 셀 무난 | 점 SE 는 낮음, 이미징 SE 는 **서버 축소·바이닝 선행 필수** | 49-site 그리드 + 바이닝된 200×200 그리드에 center-edge 서명 조작, 전부 `OFFICE-VERIFY` |
| D | **장비 편차 감시**(같은 제품·같은 층, eqp 로 그룹, 골든 중앙값 대비 delta) | 플릿 중 어느 장비가 언제부터 어긋나는 **것처럼 보이는가** | 기존 + **골든/기준 지정** | 낮음 — A 에 기준선 하나. 스큐보아에 이미 baseline + `tsb=resid` + `tsx=eqp` 있음 | 없음 | 4~6 장비 중 하나에 bias, 하나에 drift |
| D′ | **광학 TTTM / 장비 매칭**(동일 웨이퍼·동일 사이트를 각 장비로 짝 측정, offset+scale 회귀, crossed Gauge R&R) | 장비를 서로 바꿔 쓸 수 있는가, 보정계수는 얼마인가 | **짝 측정 계획 + 반복성 데이터** — 기존 데이터로는 안 나옴 | 높음 — 측정 운영이 먼저, 화면이 나중 | 없음 | 짝 측정 짝을 조작해서 만들 수 있으나 **그건 검증이 아니라 꾸며 낸 것** |
| E | SPC · 적합품질 패널(히스토그램 + Cpk, 모든 파생값에 MSE 색, 상관 경고) | 공정이 관리 상태이고 핏은 신뢰 가능한가 | 기존 + B 의 적합 메타 | 중간 — 통계는 순수 함수라 node:test 가능 | 없음 | 알려진 Cpk 분포 + **null/NaN 케이스 포함** |
| F | 이미징 SE 하이퍼스펙트럴 탐색기(픽셀×파장 브라우저) | 픽셀 단위로 스펙트럼을 봐야 하는 해석 질문 | 전부 | 매우 높음 — SPA·레이트리밋·JSON 전송과 충돌 | **전체 큐브 전송은 불가**(1회 취득 10⁷ 스펙트럼, 축소 후에도 웨이퍼당 10⁷ 값) | 전체 큐브는 배제. 단 **선택한 ROI/픽셀의 스펙트럼 지연 조회**는 별도 설계로 가능 |

**D 와 D′ 을 섞지 말 것 [추론]:** 장비별 중앙값 차이는 **편차 탐지**이지 매칭이 아닙니다. 동일 웨이퍼·동일 사이트의
짝 측정과 반복성 확인 없이는 "바꿔 쓸 수 있는가" 를 말할 수 없습니다. 저장소 데이터로 지금 바로 되는 것은 D 까지이고,
D′ 은 측정 운영(같은 웨이퍼를 두 장비로 돌리는 계획)이 선행돼야 합니다.
이 구분은 저장소 용어와도 맞습니다 — e-beam 쪽 **TTTM** 은 ABBA 시험이라는 짝 측정 절차를 전제로 한 활동이고
(`CONTEXT.md` §TTTM) [확인], 그래서 D′ 을 "광학 TTTM" 으로 부르고 D 는 TTTM 이라고 부르지 않습니다.

**OCD 에서 달라지는 것 [추론].** 표의 A~F 는 OCD 에도 그대로 섭니다. 바뀌는 것은 세 가지입니다.
(1) A·D 의 "파라미터" 가 두께·n·k 대신 CD·높이·SWA 가 됩니다. (2) B 의 상세 화면에 **라이브러리 경계 걸림**과
CD↔SWA↔높이 상관 표시가 더해집니다. (3) C 의 사이트가 패드가 아니라 테스트 키·in-die 셀이므로 사이트 좌표에
**타깃 종류**가 붙어야 하고, 같은 웨이퍼의 다른 타깃끼리는 한 맵에 섞지 않습니다.

숫자 근거 [추론, 자릿수 산수 — **실측 아님**]: 파생값 10⁷ 개는 파라미터당 웨이퍼당 JSON 100–200 MB 입니다.
브라우저에서 viable 할 것으로 **예상되는** 맵은 서버 바이닝·타일링 후 ≲10⁴–10⁵ 셀이거나 서버 렌더 래스터 +
벡터 오버레이입니다. 반면 일반 점 SE 웨이퍼(예: 49 site × ~1000 파장 × Ψ/Δ × AOI 2–3)는 10⁵–10⁶ float ≈
JSON 1–5 MB 로, 건별·사이트별 지연 로딩이면 감당 가능할 것으로 봅니다. 스펙트럼 오버레이(측정 + 모델 + 잔차,
곡선당 ~10³ 점)에 필요한 프리미티브는 ECharts 에 존재합니다 [확인: ECharts 성능 가이드, heatmap 의 progressive
렌더, `sampling: 'lttb'|'minmax'` 다운샘플링] — **다만 이 저장소에서 실제로 그려 본 적은 없으므로** 위 볼륨·셀 수
판단은 전부 [추론·미측정] 이고 §7-3 의 벤치마크로 검증해야 합니다.

ECharts 6.1.0 이 설치돼 있고 [확인: `frontend/node_modules/echarts/package.json`] 필요한 프리미티브는 다 있습니다.
다만 6.0.0 에 large-scatter 성능 회귀 이슈(apache/echarts#21434)가 있었고 6.1.0 이 그 수정을 포함하는지는
확인하지 못했습니다 [요약만]. 그리고 heatmap 셀 수 실측 상한은 **이 저장소에서 벤치마크한 적이 없습니다** —
C 방식의 렌더 전략은 오후 반나절 실험으로 결정할 일입니다.

### 권장 순서 [추론]

1. **A + D 먼저.** 가장 싸지만 "공짜" 는 아닙니다 — 새 feature 폴더, 계약, 목, 화면이 다 들어갑니다. 다만
   **분석 로직을 새로 발명하지 않아도 됩니다**: AFM 시계열 비교와 스큐보아의 `tsx=eqp` · baseline · `tsb=resid`
   패턴을 그대로 쓰고, 소유자가 이미 스큐보아에서 묻는 질문(시간·lot·장비·recipe 비교)을 광학 도메인에서
   답합니다. 단, **목록 응답에 측정당 요약을 싣는 contracts 를 먼저** 정합니다(§2 의 grain 교훈).
2. **B 를 A 가 보여주는 모든 숫자의 신용 층으로.** A 만 만들고 B 를 나중에 하면, 그 사이에 나오는 두께 숫자는
   출처 없는 진실이 됩니다. 최소한 상세 화면에서 "이 값은 Ψ/Δ 곡선에서 왔고 핏 상태는 이것" 을 보여줄 수 있어야
   A 의 숫자가 신뢰를 얻습니다.
3. **C 는 점 도구 사이트 밀도로.** 점 스팟 SE / 반사율계는 수십~수백 site 이므로 기존 wafer-map 부품으로 충분합니다.
4. **C 의 고밀도 타일 버전과 F 는 벤더 수출 포맷을 받은 뒤에만.** 서버 축소 계약(무엇을 어디에서 bin 하는가)을
   정하기 전에 픽셀 그리드 UI 를 만들면 실제 장비가 오는 날 그 뷰가 무너집니다. F 를 통째로 포기하자는 뜻은
   아닙니다 — **전체 큐브 전송**이 안 되는 것이고, 사용자가 고른 ROI 나 픽셀의 스펙트럼을 지연 조회하는 설계는
   남습니다(§3 표 F 행).
5. **E 는 A·B 위에 얹는 것이지 단독 항목이 아닙니다.** 다만 Cpk/합격 판정은 소유자가 이미 거절한 항목 목록에
   있습니다(`2026-10-09-analysis-service-directions.md`, "소유자가 이미 거절한 것") [확인] —
   **적합품질 플래그(믿을 수 있는가)는 관리한계(합격인가)와 다른 질문**이므로 거절에 걸리지 않는다고 봅니다 [추론].
   이 구분을 사용자 확인 없이 넘기지 말 것.

**리뷰 기록 (2026-10-24, codex).** 위 순서에 반대가 하나 있었습니다 — 덮지 않고 그대로 적습니다.
codex 의 권장은 **질문지 → 단일 측정 상세 + 최소 품질 표시 → A → C** 이고, **D 는 기본 묶음에서 빼자** 는
것입니다(비교 가능한 장비·제품·층이 확보돼야 가치가 생기므로; 장비가 한 대여도 C 의 사이트 분포는 쓸모가 있음).
또 "B 전체를 먼저" 가 아니라 **값의 출처·모델·진단 제공 여부를 A 와 함께** 보여주고 스펙트럼은 확보되는 만큼
붙이라는 입장이고, **ROI 선택 → 해당 스펙트럼 조회 흐름은 벤더 포맷 이후로 미룰 필요가 없이 종이 시안으로
먼저** 확인하라고 합니다. 마지막으로 목 프로토타입에 대한 경고: 낮은 MSE·강상관 사례를 넣으면 **경고의 전달력**은
시험할 수 있어도 **실제 비유일성 탐지 능력**은 검증하지 못하며, 지금 완성도 높은 목을 만드는 것은 가정을 굳힐
위험이 큽니다 [추론, 리뷰 의견 — 이 보고서의 판단은 아님].
이 보고서는 순서를 바꾸지 않았습니다. 사용자의 결정이 필요한 지점입니다.

**리뷰어 안 (2026-10-24) [추론].** 사용자의 목표가 "스큐보아와 같은 분석 방법" 이라는 것이 분명해졌으므로,
두 안을 이 목표로 다시 엮으면 이렇게 됩니다. 앞의 두 안을 대체하지 않고 세 번째 선택지로 둡니다.

1. **질문지** — codex 안과 같습니다. 두께·OCD·recipe 질문을 한 장에 넣습니다(§7-1).
2. **2-grain 계약** — 목록 행에 측정당 요약 + `measurement_kind` + `fit_status` + 모델/라이브러리 개정판.
3. **스큐보아식 검토 흐름**(§3-1) — 검색 → 검토 후보 → 개요·웨이퍼 맵·추세. 적합 품질은 별도 화면이 아니라
   이 흐름의 **실행/데이터 품질 게이트**로 들어가고, 선택한 사이트의 스펙트럼(측정 + 모델 + 잔차)은 확보되는
   만큼 붙입니다. 초판의 "B 는 A 의 신용 층" 과 codex 의 "품질 표시를 A 와 함께" 가 여기서 같은 것이 됩니다.
4. **recipe 정보**(§3-2) — recipe·모델 보기와 장비 간 recipe 비교. 장비 recipe 파일에 닿을 수 있는지가 전제입니다.
5. **D(편차 감시)** — 같은 흐름의 장비 렌즈로. 비교 가능한 장비가 두 대 이상일 때만 켭니다(codex 의 조건).
6. 그 뒤: OCD ↔ SEM 상관, 광학 TTTM(D′), 이미징 SE 고밀도 맵(C 타일·F).

### 3-1. 스큐보아의 분석 방법을 광학으로 옮기면

스큐보아에서 옮길 것은 코드가 아니라 **개념**입니다. 스큐보아의 도메인 용어(`CONTEXT.md` §검토 후보 ~ §비교 세트)
[확인] 는 측정 장비 종류에 묶여 있지 않고, 광학에 그대로 대응됩니다. 특히 "실행/데이터 품질이 측정값의 신뢰성을
먼저 제한한다" 는 검토 우선순위 규칙은 **적합 품질 게이트를 위해 만든 것처럼 맞습니다** [추론].

| 스큐보아 개념 | e-beam 에서 | 두께 계측에서 | OCD 에서 |
| --- | --- | --- | --- |
| 검토 후보 | MSR 한 건 | 측정 실행 한 건(wafer × recipe) | 같음 |
| 기준 집단 호환성 | fab·장비 모델·recipe·parameter·사이트 배치 | 위 + **스택 모델 개정판**, AOI·파장 구간 | 위 + **OCD 모델/라이브러리 개정판**, 타깃 종류 |
| 검토 근거 — 측정 결과 | 파라미터 분포·사이트 패턴 | 두께·n·k 분포, 반경 서명 | CD·높이·SWA 분포, 반경 서명 |
| 검토 근거 — 장비 상태 | FDC·드리프트 | 램프·교정 상태 등(어떤 신호가 오는지 `OFFICE-VERIFY`) | 같음 |
| 검토 근거 — 실행/데이터 품질 | 정렬·이미지 실패·누락·측정 점수 | **MSE/χ², 오차한계, 두께↔n 상관**, 적합 실패·누락 사이트 | 위 + **GOF, 라이브러리 경계 걸림**, CD↔SWA 상관 |
| 검토 우선순위 | 품질 게이트 → 최고 심각도 | 같은 규칙. 핏이 나쁜 사이트의 두께는 측정 결과 근거로 쓰지 않음 | 같음 |

여섯 개 뷰도 대응됩니다 [추론].

| 스큐보아 뷰 | 광학에서 |
| --- | --- |
| 측정 개요 | 요약 + 웨이퍼 맵(값 / 적합 품질 레이어 전환, 결측·실패 마스크) |
| 위치 비교 | 사이트별 비교 — 같은 사이트의 여러 wafer·lot |
| FDC 분석 | 장비 상태 신호가 오는 경우에만 |
| Time-Series | 파생값 추세 + 장비 렌즈(D) |
| 상관/분포 | 파라미터 간 상관(두께↔n, CD↔SWA) — **그 자체가 적합 품질 진단**. 식별자 결합이 확인되면 OCD ↔ CD-SEM |
| 이미지 갤러리 | **스펙트럼 갤러리** — 광학의 "원본 이미지" 는 사이트별 측정·모델·잔차 곡선 |

### 3-2. recipe 기반 정보

e-beam 쪽에는 recipe 를 중심에 둔 화면이 이미 다섯 개 있습니다 [확인: `frontend/app/pages/ebeam/cd-sem/[fab]/`] —
recipe 검색(장비 FTP 의 원본 recipe 파일 판독), lateral(같은 recipe 를 여러 장비에서 비교), recipe TAT,
recipe 상태(실패 이슈 + TAT), device-statistics(계측 룰 대비 파라미터·포인트 수). 광학 recipe 에도 같은 질문이
서지만, **광학 recipe 에만 있는 것**이 결과의 일부라는 점이 다릅니다.

| 광학 recipe 에 담긴 것 | 왜 보여줘야 하나 |
| --- | --- |
| 사이트 계획, 타깃 종류(패드 / 테스트 키 / in-die) | 맵·균일도·기준 집단 호환성의 전제 |
| 파장 구간, AOI, 측정 신호 종류 | 같은 시료라도 구간이 다르면 지표가 다름(§7-4) |
| **스택 모델 / OCD 모델** — 층 정의, 플로팅·고정 파라미터, 플로팅 범위 | 이 값이 곧 결과의 정의. 범위는 경계 걸림 판정의 기준 |
| **라이브러리 ID·개정판**(OCD) | 개정판이 바뀌면 같은 웨이퍼도 다른 숫자 |
| 보고 파라미터와 규격 | 무엇이 목록 요약에 오르는지 |

여기서 나오는 분석 둘이 기존 화면에는 없는 광학 고유의 값입니다 [추론].

1. **장비 간 recipe·모델 비교(lateral 의 광학판).** 장비마다 모델이나 라이브러리 개정판이 다르면 그 차이는
   데이터에서 **장비 bias 로 보입니다**. 그러니 D(편차 감시)가 어떤 장비를 짚었을 때 첫 확인은 그 장비의
   recipe·모델 개정판이어야 하고, 두 화면은 서로 링크돼야 합니다.
2. **recipe 별 적합 품질 추세(recipe 상태의 광학판).** recipe 마다 적합 실패율·경계 걸림률이 시간에 따라 오르면,
   공정이 바뀌었는데 모델이 따라가지 못한 것입니다(특히 OCD). 이것은 "어느 recipe 의 모델을 다시 손봐야 하나" 에
   답하고, 관리한계·합격 판정이 아니므로 거절 목록과 부딪히지 않는다고 봅니다 — 단 §7-5 와 같은 확인이 필요합니다.

전제: 광학 장비의 recipe 파일에 e-beam 처럼 FTP 로 닿을 수 있는지, 포맷이 무엇인지 모릅니다. 질문지 항목입니다.

## 4. 팹 사용자가 실제로 돌리는 분석

| 분석 | 필요한 입력 | 답하는 질문 | 근거 |
| --- | --- | --- | --- |
| SPC(개별값-이동범위, Xbar-R, Nelson/Western Electric 런 규칙) | lot·wafer 요약값 + 규격한계 + subgroup 정의 | 공정이 관리 상태인가 | [확인: NIST/SEMATECH e-Handbook ch.6, ASTM E2587-24] |
| 균일도 WIW / WTW / LTL | site x-y + 값 + wafer·lot 그룹 | 증착이 어디서 변하는가, WIW 규격을 만족하는가 | [확인: ASTM F1618 이 WIW·WTW·LTL 을 구분] |
| 웨이퍼 맵 공간 서명(ring · edge · center · sector · scratch; 반경/존 통계, 클러스터링, PCA) | 시간 따라 쌓인 wafer 맵 그리드 | 어떤 공정·장비 고장 서명이고 흐르는가 | [요약만: VLSI Journal 2026 리뷰, IEEE 2021] — 단 이들은 대개 defect bin map 방법이라 연속 두께 맵 적용은 [추론] |
| 장비 매칭 / 챔버 매칭(같은 웨이퍼를 각 장비로, offset+scale 회귀, ANOVA, crossed Gauge R&R) | **동일 웨이퍼·동일 사이트 짝 측정** + 반복성 + 기준값 | 장비를 서로 바꿔 쓸 수 있는가, 보정은 얼마인가 | [확인: MIT 챔버매칭 논문, NIST 오버레이 교정 전략, 성균관대 광학 계측 정밀 매칭] — 짝 측정 없이는 편차 탐지만 가능(§3 D vs D′) |
| Run-to-run APC(EWMA, 계측 지연 반영, MIMO 변형) | 공정 후 두께 + recipe knob + 지연 모델 | 다음 run 에서 무엇을 얼마나 바꿀까 | [확인: Susto 박사논문 2022, ACS MIMO EWMA] |
| 적합 품질 트리아지(MSE/χ² 추세, 오차한계, 상관 플래그, 잔차 구조) | 건별 적합 진단 | 어떤 두께 숫자가 SPC·APC 에 쓰일 수 있고 어떤 게 모델 실패인가 | [벤더: Horiba·Woollam 기준] — 표준화된 임계값은 없음 [확인] |
| 기준 계측과의 상관(SE vs TEM 단면, XRR(ISO 16413:2020), AFM/스티퍼스 단차) | 동일·인접 영역의 짝 측정 | 이 스택에서 SE 모델이 교정·타당한가 | [확인: ISO 16413:2020, NIST, Aalto SE-vs-반사율계 비교] — 일치도는 %가 아니라 합성 불확도와 함께 보고 |
| 방법 간 일치(SE vs 분광 반사율계) | 동일 웨이퍼 이중 방법 | 두께 범위·재료별로 어느 방법이 나은가 | [요약만: Aalto 2026 — SiO2/Al2O3 10–2000 nm 양호, 극박은 SE, 후막은 반사율계] |
| **OCD ↔ 기준 CD 상관**(OCD 대 CD-SEM·HV-SEM·TEM, 기울기·오프셋·R²) | 같은 타깃의 짝 측정 + 식별자 결합 | 이 OCD 모델의 CD 를 믿어도 되는가, 모델을 언제 다시 맞춰야 하나 | [요약만: SPIE 2014 기준 계측 서술, KLA SpectraShape DRAM 사례] — 저장소의 SEM 데이터가 쓰이는 유일한 광학 분석 |
| **OCD 모델 건강도**(recipe 별 경계 걸림률·GOF 추세·파라미터 상관) | 건별 적합 진단 + recipe·모델 개정판 | 어느 recipe 의 모델이 공정 변화를 못 따라가는가 | [추론] — 적합 품질 트리아지의 recipe 단위 roll-up(§3-2) |

OCD 두 행은 리뷰에서 추가했습니다. 초판의 셋은 그대로 두고, OCD 가 들어오면 **OCD 모델 건강도**가 적합 품질
트리아지의 일부로 같이 섭니다 [추론].

이 목록에서 저장소와 가장 잘 맞는 것 셋은 **균일도(WIW/WTW/LTL), 장비 매칭, 적합 품질 트리아지**입니다 [추론].
이유: (a) 균일도는 사이트 x-y 축이 이미 있고 wafer-map 부품이 있으며, Semilab 이 딱 이 세 축("across wafer /
wafer-to-wafer / batch-to-batch uniformity")을 제품 문구로 씁니다 [벤더]; (b) **장비 편차 감시**는 eqp_id 축과
baseline·잔차 렌즈가 이미 있습니다 — 진짜 장비 매칭은 짝 측정 운영이 먼저입니다(§3 D vs D′); (c) 적합 품질
트리아지는 새로울 게 없고, 없으면 나머지 전부가 오염됩니다.
SPC 와 APC 는 **관리한계·합격 판정 거절 결정과 충돌할 수 있으므로 사용자 확인 전 착수 금지** [추론].

## 5. 위험 셋

1. **짐작한 데이터를 상대로 설계하는 것.** 두께·SE 사무실 소스가 `docs/datatables/` 에 하나도 없고, 벤더도
   포맷도 모릅니다 [확인]. 목의 스키마 결정(사이트 레이아웃, 스펙트럼 샘플링, 적합 메타 필드)은 전부 짐작이며
   실제 수출이 그것을 반박할 것입니다. 저장소 규칙(mock 은 사무실 충실도, 모르는 것은 `OFFICE-VERIFY`)은
   **UI 가 목의 편의가 아니라 계약의 모양을 상대로 지어질 때만** 피해를 제한합니다. 스큐보아가 readiness 매트릭스로
   이미 배운 교훈입니다 [추론].
2. **파생 두께를 벌거벗은 진실로 보여주는 것.** 적합 맥락이 없는 두께 숫자는 핏이 훌륭할 때나 퇴화했을 때나
   화면에서 똑같이 보입니다. 심각한 엘립소미터 소프트웨어는 전부(CompleteEASE, WVASE, DeltaPsi2, SpectraRay/4)
   측정 Ψ/Δ 대 모델 오버레이 + MSE/χ² 패널 + 잔차 검사를 중심으로 만들어져 있고 [벤더] [확인], OptiLayer 는
   "보기 좋은 오버레이만으로는 특히 Δ 에서 편차를 숨길 수 있다" 는 이유로 잔차를 별도 기능으로 팝니다 [벤더].
3. **이미징 SE 데이터량 자만.** 원시 큐브는 이 저장소의 JSON · `$fetch` · 50req/5s 아키텍처를 탈 수 없습니다
   [확인: >10⁷ 스펙트럼/취득, 삼성전자 논문 원문]. 축소·바이닝 계약을 정하기 전에 픽셀 UI 를 설계하면 실제 장비
   도입 시 그 뷰가 무너집니다. 다만 이 위험의 정확한 범위는 **전체 큐브 전송**이고, ROI·픽셀 지연 조회까지
   막는 것은 아닙니다 [추론].

## 6. 모순과 갭

조사 노트 사이에서 갈리거나 확인되지 않은 것들입니다. 덮지 않고 그대로 적습니다.

- **SEMI 표준 묶음 소속이 갈립니다.** SEMI 자체 페이지와 Cimetrix 백서는 EDA/Interface A 를
  E120·E125·E128·E132·E134·E138·E164 로 꼽고, E116·E139·E140·E142·E148 은 GEM300 쪽으로 분류합니다 [벤더/확인].
  조사 요청문에 있던 "EDA 에 E142 포함" 은 이 분류와 어긋납니다. 또한 E125 는 "자기 서술(Equipment Self
  Description)" 이지 두께 측정 표준이 아닙니다 [확인]. **실무 결론:** 웨이퍼 맵 교환 표준은 E142(Substrate
  Mapping, 현행 E142-0225, 2026 개정 진행 중), 요약값 전달 채널은 GEM S6F11 이벤트 리포트와 EDA trace(E134),
  그리고 상세 결과·스펙트럼은 벤더 수출(CSV/텍스트 또는 독자 바이너리)입니다.
- **"계측 결과 공통 스키마 표준" 은 못 찾았습니다.** E183 은 존재하지만 RITdb(Rich Interactive Test Database),
  즉 **테스트 데이터** 범위입니다 [확인]. STDF 도 ATE 테스트용이지 공정 계측용이 아닙니다 [확인].
  부재의 증거라 확신도는 중간-높음입니다.
- **적합 지표 관례가 벤더마다 다릅니다**(Woollam MSE vs Horiba χ², 임계값 교차 비교 불가). 숫자 상수를
  코드에 박지 말 것 [벤더/확인].
- **균일도 공식이 하나가 아닙니다.** 3σ% = 100·3s/mean 과 range% = 100·(max−min)/mean (또는 /(max+min))이
  특허·실무에 공존하고, ASTM F1618 은 관행만 정의합니다 [확인: 특허 US7239737B2, US7928019].
  **데이터 모델 함의 [추론]:** 사이트별 원값을 저장하고 공식은 표시 설정으로 둘 것. 샘플링 계획과 edge exclusion 도
  함께 기록해야 비교가 성립합니다.
- **벤더 파일 확장자는 대부분 미검증.** Woollam CompleteEASE/VASE 의 테이블 텍스트 수출(행: AOI × 파장 × Ψ/Δ)은
  FAIRmat `pynxtools-ellips` 파서로 확인됐고 [확인], 중요한 부수 사실이 하나 있습니다 — **원시 수출 파일은 컨텍스트
  메타데이터를 싣지 않아서** 그 도구도 별도 YAML 을 요구합니다. `.dtf`·`.mlf`·`.tkr` 는 어떤 공개 자료에서도
  확인하지 못했고, `.spc` 는 Thermo Galactic GRAMS 바이너리 포맷이지 Semilab 전용으로 확인되지 않았습니다.
- **NXellipsometry 의 필드 목록 원문은 받지 못했습니다**(nxdl fetch 실패). 열린 스키마 선례로 참고할 가치가 있으니
  도입 시 한 번 읽을 것.
- **경쟁 제품 화면 레이아웃은 뷰 종류까지만 확인됐습니다.** Klarity·Exensio 마케팅은 "자동 근본 원인/공간 서명
  분석" 을 약속하지만, fetch 가능한 문서는 맵·추세·오버레이 같은 **뷰 타입**만 증명합니다. 정확한 화면 배치는
  모름으로 둘 것 [벤더].
- **`useSkewvoirAnalysis` 의 교차 계열 해석이 비-SEM `tool_type` 을 견딜지는 미검증**입니다 [확인: 미실행].
  다만 `skewvoirLinks.ts` 와 `toolType.ts` 가 이미 막고 있으므로 실제 문제는 견딜지가 아니라 울타리 비용입니다.
- **이 보고서 자신의 근거 표기가 부분적으로 어긋났습니다.** 초판은 Nature Communications 논문을 본문에서는
  [요약만] 으로 표시하고 출처 목록에서는 "유일한 검증된 1차 근거" 로 승격시켰으며, 벤치마크하지 않은 렌더
  성능을 "무난", "무시 가능" 으로 단정했습니다. 지금은 원문을 직접 읽어 [확인] 으로 올렸고 성능 판단은
  [추론·미측정] 으로 내렸습니다. 규칙: **원문을 읽은 것만 [확인], 제품 주장은 [벤더], 성능·비용 예상은
  [추론·미측정]** [추론].
- **이 보고서는 명령을 하나도 실행하지 않았습니다**(pytest · typecheck · 브라우저 없음). ECharts 셀 수 상한,
  실데이터 볼륨, 사무실 식별자 결합 가능성은 전부 미측정입니다.

## 7. 다음 수

1. **벤더 질문지 한 장을 먼저 만듭니다** — 화면보다 앞섭니다. 물어야 하는 것 [추론, §1·§6 근거]:
   장비 종류(점 스팟 SE 인지 이미징 SE 인지 반사율계 인지), 결과 전달 채널(GEM S6F11 이벤트 리포트? EDA trace?
   파일 수출? DB?), 수출 파일 하나(샘플 웨이퍼 한 장이라도), 사이트 수와 좌표 규칙·edge exclusion, 파장 범위·
   샘플링, AOI 개수, 스택 모델의 정의 위치와 개정판 추적, 적합 지표(MSE 인지 χ² 인지)와 함께 나오는 것
   (잔차? 오차한계? 상관 행렬?), lot/wafer/recipe 식별자 철자와 `lot_id`·`wafer_id` 결합 가능성, 보존 기간.
   **OCD 추가 질문 [리뷰 추가]:** 푸는 방식(라이브러리 / 실시간 회귀 / ML), 결과와 함께 오는 품질 신호(GOF 정의,
   플로팅 파라미터와 범위, 경계 걸림 표시 여부), 모델·라이브러리 개정판이 결과 행에 실리는지, 타깃 종류와 좌표,
   기준 계측(CD-SEM·TEM) 짝 데이터가 어디에 남는지.
   **recipe 질문 [리뷰 추가]:** 광학 장비 recipe 파일에 닿는 경로(FTP·DB·벤더 서버), 파일 포맷, 한 recipe 가
   두께와 OCD 를 함께 담는지, 장비 간 recipe·모델 동기화를 누가 어떻게 하는지.
   답이 오는 대로 `docs/datatables/<vendor>/<src>.txt` 와 해당 feature 의 `providers/mock.py` 를 **같은 커밋에서**
   갱신합니다(저장소 규칙) [확인: CLAUDE.md §Office DB knowledge lands in TWO places].
2. **B 의 목 스펙트럼을 만들어 적합 품질 신호를 시험합니다.** [리뷰 갱신] 이 항목의 단일 파일 시안이
   `.scratch/optical-metrology-preview/index.html` 에 있습니다(조작된 데이터, 의존성 없는 Cauchy 스택 계산 +
   Levenberg–Marquardt 적합). 시안에서 나온 사실 하나가 계약에 영향을 줍니다 — **비유일 사례(2 nm 막)에서
   공분산으로 계산한 두께 1σ 는 0.12 nm 인데 실제 오차는 0.30 nm 였습니다.** 선형 근사 오차한계는 비유일성을
   과소평가하므로, 상관 계수(−0.9998)나 MSE 프로파일(파라미터 하나를 고정하고 나머지를 다시 적합)처럼 **평평한
   해 공간을 직접 보여주는 신호**가 오차한계와 따로 필요합니다 [확인: 시안 실행 결과, 단 조작된 데이터].
   codex 의 경고(경고 전달력 ≠ 탐지 능력)는 이 시안에도 그대로 적용됩니다. 아래는 초판 내용입니다.
    `tmm`(transfer-matrix) 가 후보지만
   **현재 `backend/requirements*.txt` 에 없으므로 즉시 실행 가능한 기존 기능으로 취급하면 안 됩니다** [확인].
   의존성을 넣지 않는 대안은 Cauchy 스택의 간섭 무늬를 직접 계산하는 작은 순수 함수입니다(코사인 위상 항
   하나로도 두께 민감도가 살아 납니다) [추론]. 어떤 방법으로 만들든 두 가지를 반드시 검증할 것:
   (i) **단위·관례 변환** — `tmm` 는 라디안을 쓰고 Δ 관례가 벤더와 다를 수 있습니다 [벤더: tmm 문서];
   (ii) **인수 기준은 "높은 MSE 를 걸러내는가" 가 아닙니다** — 진짜 위험은 **MSE 는 낮은데 두께↔n 이 비유일한
   경우**이고, 그 사례를 목에 넣어야 합니다. Horiba 도 오차한계와 상관 행렬을 보라고 하지 지표만 보라고 하지
   않습니다 [벤더] [확인].
   또한 이 화면은 엘립소미터 전용으로 짜면 안 됩니다 — **반사율계 장비가 오면 측정량은 R(λ) 가 되고 모델·잔차
   구조는 그대로**이므로, 계약은 "스펙트럼 + 모델 + 잔차" 로 놓고 측정량이 Ψ/Δ 인지 R 인지 구분하는 편이 쌉니다
   [추론]. 상세 화면에 빠져서는 안 되는 것: AOI 단위, **Δ 의 분기(branch) 규칙과 위상 래핑을 고려한 잔차**
   (Δ 는 360° 주기라 단순 차이는 무의미해질 수 있습니다) [추론].
3. **ECharts 6.1.0 벤치마크 한 번** — 사무실 대상 브라우저(내부망, http)에서 heatmap 10⁴/10⁵ 셀, scatter-large
   10⁵ 점. C 방식의 렌더 전략이 여기서 결정됩니다. §3 의 모든 볼륨 판단이 [추론·미측정] 인 이유가 이것입니다.
4. **계약 초안을 A+D 로.** 목록 응답에 측정당 요약을 싣는 2-grain 계약을 먼저 쓰고, 스펙트럼은 상세
   엔드포인트로 분리합니다. 요약 행에 들어가야 하는 것 [추론]: **층 ID**(스택 중 어떤 막의 두께인지 —
   층 구분이 없는 두께 값은 의미가 없습니다), **n·k 의 기준 파장**(n 은 파장 함수라 단일 숫자로 요약하려면
   기준이 필요합니다), **적합 지표의 정의·가중치·평가 파장 구간**(같은 스펙트럼도 구간과 가중치가 다르면
   지표가 다릅니다), `fit_status`. 웨이퍼 맵에는 **결측·실패 마스크**와 여러 맵을 비교할 때의 **공통 색 범위**,
   그리고 맵의 한 점에서 **그 위치의 스펙트럼으로 건너가는 연결**이 필요합니다.
   AFM 이 사후에 한 요약을 여기서는 사전에 하는 것이 이 조사의 가장 싼 수익입니다.
5. **사용자 확인 하나.** Cpk·SPC 관리한계 거절 결정과 "적합 품질 플래그" 의 경계를 확인합니다. 이 보고서는
   둘을 다른 질문으로 봤지만(§3-5), 그 구분이 틀렸다면 E 항목 전체가 거절 목록에 들어갑니다.

## 출처

**1차 · 원자료 (확인)**

- Ultra-wide-field imaging Mueller matrix SE, Nature Communications (2025), **저자 전원 삼성전자 반도체연구소** —
  이미징 SE 데이터 모델과 볼륨의 1차 근거. 이번 조사에서 원문을 직접 읽어 소속·스테핑 방식·스펙트럼 수·
  ridge regression 사용을 확인했습니다. <https://www.nature.com/articles/s41467-025-63511-1>
- Horiba 분광 엘립소메트리 데이터 분석 — 적합 품질 체크리스트(χ², 잔차, 오차한계, 상관 행렬). <https://www.horiba.com/int/scientific/technologies/spectroscopic-ellipsometry/data-analysis/>
- Woollam 튜토리얼 · FAQ · CompleteEASE 매뉴얼 — ρ 정의, MSE 관례, 텍스트 수출 구조. <https://www.jawoollam.com/resources/ellipsometry-tutorial> · <https://physlab.org/wp-content/uploads/2016/04/Ellipsometry_manual_2.compressed.pdf>
- OptiLayer OptiChar partial discrepancies — 잔차를 따로 보여주는 이유. <https://optilayer.com/optichar-module-of-optilayer-thin-film-software/partial-discrepancies/>
- NIST thin-film ellipsometry metrology — 모델 의존성 = 소급성 문제. <https://www.nist.gov/publications/thin-film-ellipsometry-metrology>
- Cimetrix Introduction to EDA 백서 + SEMI EDA/GEM300 페이지 — 표준 묶음 소속(§6 모순의 근거). <https://www.cimetrix.com/hubfs/docs/Whitepapers/Introduction-to-EDA-WhitePaper.pdf> · <https://www.semi.org/en/next-gen-semi-eda-standards>
- SEMI E142(Substrate Mapping) · E183(RITdb) · E125(EqSD) 스토어 페이지와 SEMI standards-watch. <https://store-us.semi.org/products/e14200-semi-e142-specification-for-substrate-mapping> · <https://store-us.semi.org/products/e18300-semi-e183-specification-for-rich-interactive-test-database-ritdb>
- STDF V4 명세 + SemiEngineering 테스트 데이터 포맷 소개 — STDF 는 ATE 범위. <https://semiengineering.com/introduction-to-test-data-formats/>
- ASTM F1618(박막 균일도 관행) · ASTM E2587-24(관리도 선택) · NIST/SEMATECH e-Handbook ch.6. <https://store.astm.org/f1618-96.html> · <https://www.nist.gov/publications/nistsematech-engineering-statistics-handbook-chapter-6-process-or-product-monitoring>
- ISO 16413:2020(XRR) — 기준 계측 소급. <https://www.iso.org/obp/ui?_escaped_fragment_=iso%3Astd%3Aiso%3A16413%3Aed-2%3Av1%3Aen>
- JVST B B-spline 유전체 모델 (2020) · aot-2022-0006 스플라인 리뷰 — 분산 모델 문헌. <https://pubs.aip.org/avs/jvb/article/38/1/014001/591812/Application-of-a-B-spline-model-dielectric>
- FAIRmat `pynxtools-ellips` — 벤더 수출 구조의 증거이자 열린 스키마 선례. <https://fairmat-nfdi.github.io/pynxtools-ellips/tutorial/convert_your_first_dataset.html>
- ECharts 성능 가이드 · HeatmapView.ts · issue #21434. <https://www.mintlify.com/apache/echarts/guides/performance> · <https://github.com/apache/echarts/issues/21434>

**교과서**

- Fujiwara, *Spectroscopic Ellipsometry: Principles and Applications* (Wiley 2007)
- Azzam & Bashara, *Ellipsometry and Polarized Light* (1977)
- Tompkins & Hilfiker, *Spectroscopic Ellipsometry: Practical Application to Thin Film Characterization* (Momentum 2016)
- *Handbook of Ellipsometry* (Springer 2018)

**제품 · 플랫폼 (벤더 — 뷰 종류만 증거로 채택)**

- PDF Solutions 웨이퍼 맵 입문(bin · parametric · defect · defect-on-bin, zonal, trend, excursion) 과 fleet matching. <https://www.pdf.com/understanding-semiconductor-data-visualization-with-wafer-maps-an-introduction/> · <https://www.pdf.com/fleet-matching-and-management/>
- Nova Hub(계측 플릿 관리) · Onto Atlas G6(툴 매칭) · KLA Metrology(SpectraFilm, Aleris BBSE) · Filmetrics F50(R-Theta 맵핑) · Klarity SSA. <https://www.novami.com/nova-product/nova-hub/> · <https://ontoinnovation.com/family_group/atlas/> · <https://www.kla.com/products/chip-manufacturing/metrology>
- Semilab µSE/SE-2200 — "across wafer / wafer-to-wafer / batch-to-batch uniformity" 축 표현. <https://semilab.com/product/977/use-se-2200-microspot-spectroscopic-ellipsometer>
- yieldWerx 제품 스위트 · FAQ(Per Site Trend) · yieldHUB — SME 규모 YMS 뷰. <https://yieldwerx.com/products/product-suite/> · <https://www.yieldhub.com/platform>
- Sentech SpectraRay/4(표시 가능량 목록) · Horiba DeltaPsi2 · Park Systems/Accurion EP4 · Axometrics EllipsoStep(이미징 SE). <https://sentech.com/products/spectraray-4/> · <https://alpha.parksystems.com/en/products/ellipsometers/imaging-spectroscopic-ellipsometry-/ep4>

**OCD (리뷰 추가, 전부 [요약만] — 검색 결과·초록 수준)**

- 라이브러리 대 실시간 회귀의 트레이드오프, 파라미터 상관이 정밀·정확도를 제한함 — 광학 계측 특허 US7716003 · US10386729 · US7126700. <https://patents.google.com/patent/US7126700>
- 기준 계측(AFM·TEM)과 주력 계측(CD-SEM·scatterometry)의 관계 — SPIE 2014. <https://electronicimaging.spiedigitallibrary.org/profile/Narender.Rana-101208>
- DRAM in-die OCD, 뮬러 행렬 + ML, HV-SEM 기준 훈련 — SPIE 12955. <https://opticalengineering.spiedigitallibrary.org/conference-proceedings-of-spie/12955/129552B/Optical-in-die-NZO-benefit-for-DRAM-manufacturing/10.1117/12.3009956.full>
- 중적외 CD 엘립소메트리와 ML — Onto CSTIC 2021. <https://ontoinnovation.com/writable/files/Resources/CSTIC-2021-New-Advances-in-Mid-Infrared-Critical-Dimension-Ellipsometry-and-Machine-Learning.pdf>

**분석 방법 문헌**

- MIT 챔버 매칭 논문(R2R + 통계) · NIST 오버레이 교정 전략 · 성균관대 광학 계측 정밀 매칭. <https://dspace.mit.edu/entities/publication/7d97eee4-eccd-42c7-a2e1-36960c1cf33d>
- Susto 박사논문(2022, APC) · ACS MIMO EWMA(계측 지연). <https://automatica.dei.unipd.it/wp-content/uploads/2022/08/SustoGianAntonioPhD_thesis.pdf>
- 웨이퍼 맵 패턴 분류: VLSI Journal 2026 리뷰 · IEEE 2021 · KAIST variational deep clustering. <https://www.sciencedirect.com/science/article/pii/S0167926025002524>
- Aalto SE 대 반사율계 두께 비교. <https://research.aalto.fi/en/publications/comparison-of-thin-film-thickness-measurements-using-ellipsometry/>

**열린 소스 (참고 구현)**

- `wafertools/wafermap`(MIT, 브라우저 순수 ES — 맵 렌더, 공간 통계, 클러스터링, lot 추세) · `uia4w/uia-wafermap`(Apache-2.0) · `Lotheringer/wafermap-viewer`(인라인 파라메트릭 계측용 단일 파일 뷰어) · `tmm`(transfer-matrix, 목 스펙트럼 생성 후보 — **현재 이 저장소 의존성에 없음**, §7-2 참고). <https://github.com/wafertools/wafermap> · <https://github.com/Lotheringer/wafermap-viewer>

**제외**

- scite.ai / abelsci 의 SPIE 사본(페이월·403, 추가 내용 없음), SPIE 13426-05 초록의 잘린 데이터량 수치("exceeding 12…")는 미확인이라 채택하지 않았습니다.
- SEO 블로그(cotocus "top 10 YMS", sibranchwafer, jeez-semicon), 해적판 스캔(djvu.online Azzam), Fabmatic·Bruker·AMAT 광학 박막 UI 는 usable 문서를 찾지 못했거나 약한 선례라 뺐습니다.
