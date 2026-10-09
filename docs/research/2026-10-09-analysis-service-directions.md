# 스큐노노, 보여주기에서 기준 세우기로 나아갑니다

> - 작성일은 2026-10-09 입니다. 코드와 문서를 읽고 쓴 조사 보고서이며, 그날 오전의
>   상태를 기준으로 합니다.
> - 근거가 된 조사 노트 6개는
>   [`2026-10-09-analysis-service-directions-notes/`](2026-10-09-analysis-service-directions-notes/)
>   에 있습니다.
> - 이 보고서의 권고 가운데 스큐보아 0~3단계와 AFM 1~5·7·8번은 같은 날 구현했습니다.
>   구현 기록은 [`2026-10-06-page-value-plans.md`](2026-10-06-page-value-plans.md) 의
>   "built 2026-10-09" 주석과 `docs/afm/service-recommendations.md` 3.5 절에, 리뷰 기록은
>   `.scratch/skewvoir-afm-batch-261009/` 에 있습니다. AFM 6번(loader 요약값 적재)은
>   요청하지 않기로 했고, notch 위치는 추적하지 않기로 했습니다(사용자 결정 2026-10-09).

스큐노노에 지금 더 필요한 것은 새 차트가 아니라 세 가지 토대입니다. 선택과 함께 움직이지 않는 **고정 기준**, 손으로 고른 수십 건을 넘어서는 **측정 단위 전수 이력**, 그리고 CD 값 자체가 아니라 **그 측정을 믿어도 되는지 알려 주는 품질 신호**입니다. 스큐보아는 이미 채택된 S7(기준·대상 고정 비교)과 S8(검토 영수증)을 먼저 짓되, S7을 숫자 하나가 아니라 위치 맵·사이트별 차이·같은 위치 이미지로 이어지는 "비교 모드"로 키우고, 응답에 이미 실려 오지만 버려지는 `measurement_score`, `addressing1/2_score`, `alignment.offset`, `start_time`/`end_time` 을 "장비 쪽 문제인지 recipe 쪽 문제인지"를 가르는 표시 전용 축으로 올리는 것이 가장 값집니다. AFM 은 수치 분석이 "손으로 담은 20건"에 묶여 있다는 구조적 한계가 본질이므로, 팁 열을 적재했던 선례대로 측정당 요약값을 목록에 싣는 loader 변경 하나가 recipe 전수 추세, 팁 변경 추정 전후 분리, 이상 측정 후보 찾기를 한꺼번에 엽니다. 그 전에 집에서 바로 지을 수 있는 것은 S6 고정 기준선, Lot·Slot 이력 자동 연결, 측정 컬럼 간 관계 보기입니다. UI/UX 에서는 공유 링크가 보낸 사람의 화면을 재현하지 못하는 것이 가장 큰 손실입니다. 다만 이 우선순위는 코드와 문서만 읽고 세운 것이고 저장소에는 사용 로그도 엔지니어 인터뷰도 없으므로, 사무실에서 `/activity` 순위를 읽는 일이 어떤 구현보다 먼저입니다.

이 보고서의 근거 표기는 조사 노트의 등급을 그대로 따릅니다. **[확인]** 은 조사자가 코드나 원문을 직접 읽은 것, **[요약만]** 은 검색 결과 요약이나 초록만 본 것, **[벤더]** 는 벤더 홍보 자료, **[특허]** 는 방법만 기술하고 성능은 검증하지 않은 특허 본문, **[추론]** 은 조사자 또는 이 보고서의 추론입니다. 모든 내부 사실은 코드를 읽어 얻은 것이며 브라우저 실행이나 사무실 데이터 접속은 없었습니다.

## 화면은 깊지만 기준·이력·사용 근거 세 가지가 비어 있습니다

스큐노노의 분석 깊이는 이미 상당합니다. 스큐보아는 판정 문장, wafer map, 반경 다항 적합과 신뢰·예측 띠, 공간 레이어, sequence 별 FDC 행렬, 쌍별 상관, 이미지 검토 대기열까지 갖춘 6개 view 워크스페이스이고(`frontend/app/composables/useSkewvoirWorkspace.ts:36-43`), AFM 은 2주 사이에 측정 검색·상세·시계열 비교·팁 모니터링·가동 현황·Recipe 현황 6개 화면이 섰습니다. Recipe 현황은 recipe 구성을 보정한 장비 지수와 Byar 95% 구간을, TTTM 은 브라우저에서 계산하는 maximal clique 묶음과 MDS 지도를 냅니다. 내부 브레인스톰의 자기 진단이 정확합니다. **"보여주기는 깊고 묻기는 얕다"** — 비교 기준이 없고(통계가 선택과 함께 움직임), 판정의 이유와 범위가 없고, 다음 결정을 받쳐 주지 못합니다(`docs/research/2026-10-05-page-value-brainstorm.md` 요약 1).

이 진단에서 나온 9개 항목 가운데 **S2, S5, S1, S3 네 개가 2026-10-06 에 출시**됐고, S4, S7, S13, S8, S6, S17, S16, S10, S11 과 장비 상태 → H/W 링크 교체는 파일·함수 이름까지 설계된 채 미구현입니다. 그 뒤 커밋은 거의 전부 AFM 이었습니다. 따라서 이 항목들은 새 제안이 아니라 "준비된 작업"이며, 이 보고서는 그것을 반복하지 않고 평가하고 그 위에 얹을 것을 다룹니다. 소유자가 이미 거절한 것 — Cp/Cpk 와 합격 판정, 사용자가 고른 세트에서 뽑은 SPC 관리 한계, 포인트 축소(S15), 장비 요약 허브와 홈 브리핑, 건강 점수, AFM ↔ SEM 자동 연결, 새 OpenSearch 인덱스, 알람 인수·종결 흐름, AFM 관리 한계선 — 은 다시 꺼내지 않습니다.

두 도메인이 부딪힌 벽은 같은 모양입니다. 스큐보아는 pickle 이 61일, 검색 창이 60일이라 공유 링크가 결국 재현되지 않고(`docs/datatables/hitachi/msr_file_pickle.txt:24-28`), 세트는 30건에서 잘립니다(`frontend/app/utils/skewvoirAnalysis/curatedSet.ts:17`). AFM 은 측정값이 목록에 없어 상세를 건당 1요청으로 읽어야 하고 그룹이 20건으로 막힙니다(`frontend/app/composables/useAfmCart.ts:38-43`). **측정 한 건을 한 줄로 요약한 이력 층이 없다**는 것이 공통 원인이고, AFM 은 2026-10-07 팁 열 적재로 그 해법의 선례를 이미 만들었습니다. e-beam 쪽에서는 TTTM 타당성 연구가 같은 결론 — 야간 run-grain rollup 이 가장 먼저 — 을 냈으나(`docs/research/2026-08-16-skew-tttm-feasibility.md` §9), 그것이 지어졌는지는 조사에서 확인하지 못했습니다.

가장 약한 고리는 근거 자체입니다. 계획 문서가 스스로 **"사용 로그도, 엔지니어 인터뷰도 근거에 없습니다"** 라고 적었고(`docs/research/2026-10-06-page-value-plans.md:27-29`), 1차 출시 뒤 `/activity` 건수 비교와 세 가지 직접 질문으로 확인하겠다던 계획이 실행됐다는 기록도 없습니다. 실제 페이지 순위는 사무실 OpenSearch 에만 있습니다. 외부 문헌도 같은 방향을 가리킵니다. 대시보드 사용자의 필요는 설계자가 가정한 것보다 훨씬 다양하다는 면담 연구가 있고([Tory et al. 2021](https://www.tableau.com/research/publications/finding-their-data-voice-practices-and-challenges-dashboard-users), [요약만]), 수백 명 이하 전문가 집단에서는 긴 작업 목록에서 다섯 개를 고르게 하는 top-tasks 투표가 적은 표본으로도 쏠림을 드러낸다는 실무 방법론이 있습니다([Center Centre](https://articles.centercentre.com/?p=207), [요약만], 실무자 의견).

## 스큐보아는 S7·S8 위에 '측정 품질' 축을 얹어야 합니다

스큐보아의 문서상 목적은 "개별 측정 결과, 장비 상태, 측정 실행 및 데이터 품질 정보를 연결"하는 것인데(`docs/project-overview.md:76-78`), 현재 화면은 그중 측정 결과(CD)와 FDC 에 치우쳐 있고 실행·품질 정보는 받아 놓고 쓰지 않습니다. 발전 방향은 네 단계로 정리됩니다.

### 먼저 같은 링크가 같은 판정을 내도록 고칩니다

새 기능보다 앞서는 것은 판정의 일관성입니다. 이상 판정 임계값 편집기는 Time-Series view 의 한 lens 안에만 있는데, 같은 `anomalyCfg` 객체가 측정 개요의 site 판정과 feature 행에도 들어갑니다(`frontend/app/composables/useSkewvoirAnalysis.ts:418,421,750`). 이 값은 URL 에도 없고 저장되지도 않으므로 **같은 링크를 연 두 엔지니어가 다른 판정을 볼 수 있습니다** [추론, 코드 판독 기반]. "분석 대상을 바꾸는 컨트롤은 rail 에 둔다"는 `DESIGN.md:442` 규칙대로 rail 로 옮기고 URL 에 실어야 합니다. 기본 탐지기도 재검토 대상입니다. 기본값인 leave-one-out 평균 ±10%/±20% 는 30 nm CD 에서 20% 가 6 nm 이므로 CD 작업에는 거칩니다 [추론]. `.scratch/skewvoir-msr-review` issue 01 은 이미 "품질 게이트 다음 leave-candidate-out median/MAD"로 결론을 냈고 `frontend/app/utils/stats.ts` 에 MAD 원시 함수가 있으므로, 탐색용 탐지기를 그 방향으로 맞추고 비교 대상(peer)을 같은 recipe 로 한정하는 것이 내부 결정과 일치합니다.

같은 부류의 불일치가 더 있습니다. 위치 비교의 residual 레이어는 항상 1차 적합을 쓰고 측정 개요는 1·2·3차를 고를 수 있어 두 화면이 같은 wafer 를 다르게 말할 수 있고(`frontend/app/utils/skewvoirAnalysis/spatial.ts:215`), 분포 패널의 σ 는 백엔드 `std`, 판정의 σ 는 클라이언트 `sampleStd` 이며, Time-Series y축은 기준이 recipe 별일 때도 "Δ vs 세트 기준"으로 고정돼 있습니다. 세트 일괄 조회 실패는 조용히 삼켜지고(`useSkewvoirAnalysis.ts:529-531`), `focusError` 와 재시도 버튼은 두 view 에서만 읽으며, 40건을 골라도 30건만 남는다는 사실은 검색 화면의 작은 문구가 전부입니다. mock 의 FDC key `ObjectSem`·`Vrd` 가 실물 `ObjectSEM`·`VRD` 와 대소문자가 다른 점도 고칠 대상입니다. 사무실 adapter 가 이름을 정확히 맞춘다면 두 채널이 요약에서 빠진다는 결과는 [추론]이지만, mock 을 실물 철자에 맞추는 것은 프로젝트 규칙 그대로입니다. 이 항목들은 모두 집에서 백엔드 변경 없이 끝납니다.

### S7 을 숫자가 아니라 세 화면의 비교 모드로 키웁니다

소유자가 10월에 직접 적은 "빠진 것" 셋은 고정 기준 대비 이동량, 결론을 남기는 방법, 포인트 축소였고(`docs/research/2026-10-05-page-value-brainstorm.md:438-440`), S7 과 S8 이 앞의 둘을 맡고 셋째는 2026-10-06 에 제외됐습니다. S7 → S8 순서는 옳습니다. 영수증은 무엇과 비교했는지가 고정돼야 의미가 있기 때문입니다. 보탤 평가는 **S7 이 요약 수치 하나로 끝나면 가치의 절반만 얻는다**는 점입니다. 보류 목록에 따로 흩어져 있는 세 항목 — 세트 기준 중앙값·부호 있는 delta·coverage 맵(`docs/issues/skewvoir/analysis-coverage-gap-analysis.md` §3.2), 같은 site 의 시간순 이미지 띠(§3.6), 세트 범위가 placeholder 인 갤러리 — 은 사실 모두 "기준 대 대상"의 서로 다른 그림입니다. S7 의 `base=` 키를 한 번 정하면 위치 비교는 기준 대비 delta 맵을, 상관/분포는 site 별 (기준+대상)/2 대 (대상−기준) 산점도를, 갤러리는 같은 site 의 기준·대상 이미지 쌍을 그릴 수 있습니다.

외부 근거는 방향만 받쳐 주고 강도는 약합니다. 두 측정의 일치를 볼 때 상관계수가 아니라 평균-차이(Bland-Altman) 그림과 bias ± 1.96·SD 를 쓰라는 것은 계측 일치 분야의 표준 권고이나 조사에서는 요약으로만 확인했습니다([Analyse-it](https://analyse-it.com/learn/bland-altman-limits-of-agreement), [요약만]). 두 이미지의 차이를 찾을 때 나란히 놓기보다 같은 자리에서 번갈아 보여 주는 쪽이 적중률과 시간에서 나았다는 실험은 **항공 영상, 참가자 12명**짜리이고 SEM 이미지로의 전이는 검증되지 않았습니다([Fraunhofer Publica](https://publica.fraunhofer.de/entities/publication/550fbe2f-a76e-471d-9cc1-5a67e50454f1), [요약만]). 따라서 이미지 쌍에는 동기화된 나란히 보기와 한 키로 바꾸는 깜빡임 보기를 둘 다 두고 어느 쪽이 쓰이는지 보는 것이 맞습니다. delta 맵의 색은 0 을 중심으로 한 발산형이어야 하는데, 색은 `--sk-*` 토큰에서만 온다는 규칙이 있으므로 이는 코드가 아니라 `DESIGN.md` 에 올릴 질문입니다.

S8 에는 한 가지를 붙입니다. 장비 skew 표, across-MSR 점, 쌍별 근거, 공간 site 표, FDC 상태 행렬, 반경 적합 지표는 지금 데이터로 내보낼 길이 없고 Measurement Points 표만 Excel 이 됩니다. 영수증 xlsx 의 시트를 이 표들로 채우면 `useTableDownload` 경로를 재사용하면서 두 일이 하나가 됩니다. 호출자가 없는 `POST /api/msr-files/download`(zip, 100건 이하)도 같은 버튼에 붙일 수 있습니다. pickle 이 61일에 지워지므로 영수증은 링크가 아니라 수치를 담은 파일이어야 한다는 S8 의 설계 판단은 그대로 타당합니다.

### 이미 도착했지만 버려지는 품질·실행 신호를 축으로 올립니다

이 보고서가 내부 문서에 **새로 보태는 핵심 제안**입니다. `MsrFileRow` 는 측정마다 `measurement_score`, `addressing1_score`, `addressing2_score` 를 싣고 오지만 갤러리 배지와 boolean 점 하나에만 쓰이고, `alignment.offset` x/y 는 method 요소만 읽히며, `MeasHistRow` 의 `start_time`·`end_time`·`meastime` 은 스큐보아의 어떤 파일도 읽지 않습니다(`frontend/app/utils/skewvoirAnalysis/gallery.ts:174-175`, `frontend/app/components/ebeam/skewvoir/overview/VerdictBlock.vue:386`).

외부에서 가장 구체적인 설계가 바로 이 신호들을 쓰는 것입니다. GlobalFoundries 특허는 CD-SEM 이 측정마다 남기는 pattern-recognition 점수와 벡터, measurement-model 점수와 offset, autofocus 등급을 FDC 센서처럼 다루어 target 별로 wafer 를 가로질러 추세를 보고, 지표별로 조치(stigmation 보정, stage PM, recipe 수정)를 짝짓습니다([US 10,185,312 B2](https://patents.google.com/patent/US10185312B2/en), [특허], 조사자가 원문 확인). 다만 이 특허는 임계값을 주지 않고, 탐지율이나 오경보를 평가한 동료 심사 문헌은 찾지 못했습니다. "같은 지표가 한 장비의 모든 recipe 에서 떨어지면 장비, 한 recipe 의 모든 장비에서 떨어지면 recipe"라는 분리 규칙과 "연속 점수는 hard fail 전에 먼저 내려간다"는 조기 경보 논리는 특허 본문이 아니라 조사자의 [추론]입니다.

스큐보아에 옮기면 세 조각입니다. 단일 범위에서는 위치 맵의 다섯 번째 레이어로 score 를 그리고, 세트 범위에서는 Time-Series 에 score 중앙값과 측정당 소요 초(`meastime` ÷ sequence 수)를 lane 으로 더하고, across-MSR feature registry 에 score·alignment offset·소요시간을 축으로 등록합니다. 그러면 "CD 가 움직인 측정에서 addressing 점수도 같이 내려갔는가"를 한 화면에서 읽을 수 있습니다. 제약은 분명합니다. 방법 연구는 vendor score 를 **판정 경로에서 제외**했으므로(`docs/issues/skewvoir/wafer-analysis-method-research.md:74-81,521`) 이 축은 표시 전용이어야 하고 `확인 필요` 배지에 영향을 주면 안 됩니다. score 의 척도와 alignment offset 의 단위는 저장소에 기록이 없어 `OFFICE-VERIFY` 이며, 집의 mock 은 `health` seed 하나가 FDC drift·CD 이동·품질 점수를 함께 움직이므로 집에서 보이는 score ↔ CD 관계는 생성기가 만든 것입니다. 기존 `DemoDataNote` 를 이 축에도 띄워야 합니다.

같은 이유로 **쓰지 말아야 할 도착 데이터**도 있습니다. `fdc_params[].drift_sigma` 와 `.status` 는 매 파일에 오지만 mock 이 지어낸 nominal·sigma 에 기대고 있어, 사무실 기준선이 합의되기 전에는 숨겨 두는 편이 옳습니다. `fixed_fdc` 는 MSR 당 스칼라 하나이므로 단일 범위 FDC view 에 "측정 전 조건" 작은 표로 보여 주는 것까지가 적정선입니다. `ProvenanceDrawer` 는 데이터 층이 완성돼 있으나 커밋 `358f3fe8` 이 의도적으로 내렸고, cond.txt crosshair 도 `0bbd102e` 로 스큐보아에서 제거됐으므로, 이유를 확인하기 전에는 되살리기를 권하지 않습니다.

### 계약이 필요한 것은 범위를 따로 잡고, 이미지 파생 지표는 조사부터 합니다

다음 표는 스큐보아 항목을 지을 수 있는 곳과 근거 수준으로 나눈 것입니다.

| 순서 | 항목 | 쓰는 데이터 | 집(mock)에서 | 사무실·계약 의존 | 근거 수준 |
| --- | --- | --- | --- | --- | --- |
| 0 | 판정 일관성(임계값 rail·URL, 적합 차수, σ 정의, 상한·실패 고지, FDC key 철자) | 기존 응답 | 전부 가능 | 없음 | 코드 판독, 일부 추론 |
| 1 | S7 비교 모드(delta 맵, 평균-차이, 이미지 쌍) | 기존 pickle·이미지 | 가능 | 이미지 FTP 지연은 사무실 실측 | 내부 채택 + 외부 요약만 |
| 2 | S8 영수증 + 표 내보내기 + 세트 원본 zip | 기존 계산값 | 가능 | 없음 | 내부 채택 |
| 3 | 품질·실행 축(score, alignment, 소요시간) | 기존 응답의 미사용 필드 | 화면 가능, 관계는 mock 조작 | score 척도·offset 단위 확인 | 특허(성능 미검증) + 추론 |
| 4 | 장비 skew 표에 n 과 구간 표시 | 기존 계산값 | 가능 | 없음 | 내부 규칙(후보만 표시) |
| 5 | 이벤트 겹쳐 보기(BM/PM, MDC epoch) | `hardware/bm_pm`, `tttm` `EpochMarker` | 백엔드 없이는 불가 | 이벤트 계약, KST/UTC 정합 | 내부 "계약 대기" + 외부 요약만 |
| 6 | 설계값 기준선 | `recipe_idp` `Design_Value` | 불확실 | parser 반환 여부부터 확인 | 문서끼리 충돌, 미확인 |
| 7 | wafer / die 내부 / 잔차 분산 분해 | `stage_coordinate`, `mp_number`, `chip_pitch` | 계산 가능 | 같은 recipe = 같은 map 인지 확인 | 특허 요약만 + 추론 |
| 8 | 이미지 파생 지표(noise floor, sharpness) | 원본 이미지 bytes | 불가 | 보관 이미지 적합성 조사 | 외부 문헌, 조건부 |

5번은 가치가 크지만 성격이 다릅니다. BM/PM, 알람, MDC epoch 는 모두 `eqp_id` 와 시각을 세트의 각 측정과 공유하고, 모든 추세 차트에 사건을 공통 세로선으로 긋는 것은 인접 분야 도구의 기본 관행입니다([Grafana 문서](https://grafana.com/docs/grafana/v13.1/dashboards/build-dashboards/annotate-visualizations/), [요약만], 벤더 문서). 그러나 9개 항목의 규칙은 "백엔드를 고치고 싶어지면 그 항목의 범위가 틀린 것"이고, 사무실 timestamp 는 offset 없는 KST 가 UTC 로 취급되는데 `live_alarm` 은 `+09:00` 을 명시하므로 조인이 9시간 어긋나기 쉽습니다. 이 항목은 내부 문서의 "계약 대기" 그대로 두고, 지을 때는 TTTM 이 이미 가진 `EpochMarker{eqp_id, date, kind}` 모양을 재사용하는 것이 새 계약을 줄이는 길입니다. Recipe 현황 추세에 사건 표식을 넣는 안은 이미 거절됐고 S9(H/W 정비 전후 비교)가 그 질문을 H/W 쪽에서 답하기로 돼 있으므로, 스큐보아의 이벤트 띠는 S9 가 정한 계약을 받아 쓰는 후속이어야 합니다.

7번은 현재의 반경 다항식 + 90° 네 구역을 넘는 공간 서명입니다. 특허 문헌은 wafer 수준을 Zernike 다항식으로 맞추고 BIC 가 최소가 되는 차수(한 사례에서 4차)에서 멈춘 뒤 필드 내부 성분을 따로 떼는 방법을 기술합니다([US 11,092,901](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/11092901), [특허], 발췌만 확인, 성능 검증 없음). 스큐보아 데이터에서 die 내부 위치를 `mp_number` 로 대신할 수 있다는 것은 이 보고서의 [추론]이고, notch 방향이 `notchValidated: false` 인 채 기본값 `'bottom'` 이며 "같은 recipe 면 같은 wafer map"이 `OFFICE-VERIFY` 이므로 지금은 후보로만 둡니다. 코드에서는 반경·구역 접근이 엔지니어가 실제로 찾는 서명과 맞는지조차 판단할 수 없었습니다.

8번은 외부 근거가 가장 강한 영역이면서 스큐노노 데이터에서 가장 먼 영역입니다. 이미 수집된 양산 이미지에서 장비별 scan-error 서명을 뽑아 6대 중 문제 장비 1대를 찾아냈다는 imec·Fractilia 논문([SPIE 11611](https://biomedicaloptics.spiedigitallibrary.org/conference-proceedings-of-spie/11611/116111B/Diagnosing-and-removing-CD-SEM-metrology-artifacts/10.1117/12.2585311.full), 초록·발췌 수준 확인)과, 엔지니어 눈에 보이지 않는 약 0.1 nm 상당의 sharpness 변화를 잡는다는 Hitachi 저자 논문([SPIE 7272](https://opticalengineering.spiedigitallibrary.org/conference-proceedings-of-spie/7272/727210/CD-SEM-tool-stability-and-tool-to-tool-matching-management/10.1117/12.813993.full), 2009, 초록만)이 있습니다. 그러나 PSD noise floor 방식은 **장비 쪽 필터가 걸리지 않은 이미지**에서만 성립하고 y 픽셀이 상관 길이의 약 20% 이하여야 하며([US 10,488,188](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10488188), [특허], 발췌), 스큐노노에는 이미지 bytes 를 처리하는 코드가 전혀 없고 이미지는 장비 FTP 에만 있다가 72시간 캐시됩니다. 미리보기는 WebP 입니다. "5–20배 매칭 개선", "30% 이상 처리량" 같은 수치는 기준선을 밝히지 않은 [벤더] 주장입니다. 따라서 지금 할 일은 구현이 아니라 원본 TIFF 의 픽셀 크기·프레임 수·장비 측 필터 여부를 확인하는 적합성 조사 한 번입니다. TMP/FMP 매칭 분해([US 7,340,374](https://patents.google.com/patent/US7340374B2/en), [특허], 원문 확인, 선행 계수 3 은 조사자가 FMP 식에서 유추)는 "가장 큰 제곱항이 원인 유형"이라는 구현 가능한 규칙을 주지만, 기준 artifact 와 분포 통계가 선행돼야 한다는 내부 게이트에 걸리므로 스큐보아가 아니라 TTTM 계약 확장(B-0) 뒤의 일입니다. 그 사이 스큐보아의 장비 skew 표는 판정 대신 **표본 수와 불확실 구간을 같이 보여 주는 것**으로 "tool 차이 후보만 표시" 원칙을 더 정직하게 지킬 수 있습니다.

## AFM 은 20건 상한을 푸는 적재 열 하나가 나머지를 엽니다

AFM 에는 `docs/afm/service-recommendations.md`(2026-10-08)의 7개 추천이 이미 있습니다. Lot·웨이퍼 이력 자동 연결, 소요시간 분석, 팁 변경 전후 비교, 프로파일 비교, 측정 항목 간 관계, 이상 측정 조사 묶음, 반복 회차 분석 순입니다. 이 가운데 출시된 것은 소요시간의 "선택 그룹" 단계 하나이고, 사용자가 나머지 중 무엇을 승인했는지는 저장소에 기록이 없습니다. 이 목록의 방향은 옳지만 **순위를 정하는 축이 하나 빠져 있습니다.** 일곱 개 대부분이 "손으로 담은 최대 20건"이라는 같은 상한 안에서 동작한다는 점입니다.

### 측정당 요약값을 목록에 싣는 것이 가장 큰 지렛대입니다

엔지니어가 "이 recipe 의 `Dishing_H` 가 지난 3개월 어떻게 움직였나"를 보려면 지금은 20건을 손으로 담아야 하고, 사무실에서는 상세 한 건이 5–8초입니다(원인 미상, `docs/datatables/afm/afm_redis.txt:403-420`). 목록에는 3개월 전수 이력이 있으나 측정값이 없어 건수 집계와 팁 판정에만 쓰입니다. 팁 요약 10열을 2026-10-07 에 과거분까지 소급 적재한 선례가 있으므로, 같은 방식으로 **측정당 block × 컬럼의 MEAN·STDEV 를 목록에 싣도록 loader(Office agent, 수신자 한 곳)에 요청**하면 recipe 전수 추세가 목록 한 번 조회로 가능해집니다 [추론, 조사 노트]. 컬럼이 recipe 마다 다르고 최대 51개이므로 넓은 열이 아니라 중첩 또는 긴 형태여야 하고, 프로젝트 규칙대로 계약·office template·mock·`docs/datatables/afm/` 를 한 변경에서 함께 맞춰야 합니다. Summary 통계는 장비가 쓴 값 그대로이므로 loader 가 새로 계산할 것이 없다는 점이 이 요청을 가볍게 만듭니다. `compact=1` 로 줄여 놓은 응답 크기를 다시 키우지 않도록 opt-in 필드로 받는 것이 안전합니다.

이 열이 생기면 추천 3번(팁 변경 전후)의 성격이 바뀝니다. 지금 구조에서는 팁 화면과 수치 추세가 분리돼 있어 전후 비교도 20건 안에서만 가능하지만, 전수 추세 위에 기존 `tipChanges`(팁 변경 추정)를 세로선으로 겹치면 "값의 계단이 팁 변경 추정 시점과 맞는가"를 3개월 전체에서 볼 수 있습니다. 벤더 공개 자료에서 장기 추세를 팁·장비 사건과 묶어 보는 기능을 찾지 못했다는 조사 결과는 이 자리가 사내 도구의 빈칸일 가능성을 시사하지만, 그것은 공개 페이지에 없다는 뜻일 뿐 확인된 부재가 아닙니다 [추론].

### 팁 분석은 '제품 값만으로는 마모가 안 보인다'는 사실에서 출발합니다

팁 관련 서비스에는 외부 근거가 분명한 한계를 그어 줍니다. NIST 의 CD-AFM 팁 마모 연구에서 마모율이 서로 다른 팁들 사이에도 평균 선폭은 **114.0–114.9 nm, 표준편차 0.41–0.61 nm** 로 유지됐고, 마모는 제품 측정값이 아니라 10회마다의 팁 qualification 과 고정 monitor site 재측정으로 추적했습니다([Orji et al. 2020, PMC7724968](https://pmc.ncbi.nlm.nih.gov/articles/PMC7724968), 동료 심사, 조사자가 원문 확인). 이 수치는 측벽 접촉 방식의 flared 팁에 대한 것이고, CMP·거칠기 recipe 의 원뿔형 팁에 대한 동급 공개 수치는 찾지 못했으므로 스큐노노의 recipe 에 그대로 옮길 수는 없습니다. 그래도 방향은 내부 실측과 맞습니다. MCNT 계열 `Tip Width` 가 같은 슬롯에서 오르내리는 것은 마모가 아니라 측정 오차로 추정됐고(`docs/datatables/afm/afm_raw_files.txt:178-202`), 교체 이벤트·사유·수명 기준은 데이터에 없습니다.

여기서 나오는 판단은 세 가지입니다. 첫째, 팁 변경 추정 전후 비교는 지을 가치가 있지만 화면이 말할 수 있는 것은 "팁이 바뀐 것으로 보이는 시점 앞뒤로 값이 이만큼 달랐다"까지이며, 계단은 팁 간 offset, 한 팁 수명 안의 기울기는 마모라는 구분은 조사자의 [추론]입니다. 추천 보고서가 이벤트 이름을 "팁 변경 추정"으로 제한한 것은 그대로 지켜야 합니다. 둘째, `Mileage` 는 팁 단위 누적값이고 교체 시 리셋되므로 한 팁 안에서 "값 대 Mileage" 산점도를 그릴 사용량 축이 이미 있습니다. 다만 단위가 미정(um 추정)이라 축 이름은 원본 그대로 두어야 합니다. 셋째, 팁 건강의 가장 좋은 지표는 제품이 아니라 **주기적으로 재는 기준 시료의 추세**입니다. Park 의 브로셔도 팁 보존의 증거로 반복 횟수에 따른 Rq(1회 0.669 nm → 15,000회 0.642 nm)를 제시합니다([Park NX-Wafer 브로셔](https://www.parksystems.com/content/dam/parksystems/product/in-line-metrology-afm/nx-wafer/ParkNXWafer230719E08A4.pdf), [벤더], 원문 확인). MAPC01 의 lot 실측 예에 `MON69683` 이 있는데, 이것이 monitor wafer 를 뜻하는지는 저장소에 근거가 없는 이 보고서의 추측입니다. 그런 recipe 나 lot 이 실제로 있다면 "기준 시료 recipe 를 팁별로 색칠한 전수 추세"가 팁 모니터링 화면에서 가장 값진 한 장이 되고, 없다면 팁 잔여 수명 류의 서비스는 계속 보류가 맞습니다. 팁 이미지(`_C_PR`, `C_Result`)는 무엇을 찍은 것인지가 미정(Q53)이고, AFM 팁 상태를 이미지로 분류하는 것을 주제로 한 논문은 조사에서 찾지 못했으므로 이미지 기반 팁 판정은 제안하지 않습니다.

### 집에서 지금 지을 수 있는 것과 순서

| 순서 | 서비스 | 쓰는 데이터 | 집(mock)에서 | loader·사무실 의존 | 기존 문서와의 관계 |
| --- | --- | --- | --- | --- | --- |
| 1 | 고정 기준선(이전 측정을 기준으로 고정) | 그룹 상세 | 가능 | 없음 | S6, 보류 전제가 바뀜 |
| 2 | Lot·Slot 이력 자동 연결 | 목록 열 | 가능 | `Sample ID` 는 목록에 없음 → 요청 | 추천 1번, 동의 |
| 3 | 측정 컬럼 간 관계, 값 대 Mileage·Approach | 그룹 상세 | 가능, 값은 가짜 | 컬럼 의미 확인 | 추천 5번 확장 |
| 4 | 포인트당 소요 초(소요시간 ÷ `point_count`) | Info `Start/End Time`, 목록 | 가능 | 값이 있는 측정만 | 추천 2번 보강 |
| 5 | 값으로 색칠한 Site 인덱스 격자 | `Site X`·`Site Y` | 가능 | 방향(Q24) 미확정 | 신규, 표시 한정 |
| 6 | recipe 전수 추세 + 팁 변경 추정 겹치기 | 측정당 요약 열 | mock 확장 후 가능 | **loader 변경 필요** | 추천 3번의 전제 |
| 7 | 1D 프로파일 겹쳐 보기 | profile X/Y/Z | 가능 | 단위·leveling 정책 합의 | 추천 4번, 범위 축소 |
| 8 | 이상 측정 조사 묶음(xlsx) | 위 결과물 | 가능 | 없음 | 추천 6번, 1번 뒤 |
| 9 | 반복 회차 분석 | point 행 | 보류 | 회차 매핑 확인, 사무실 미해결 (b) | 추천 7번, 순서 유지 |

1번을 맨 앞에 두는 이유는 두 가지입니다. S6 는 2026-10-06 계획에서 "AFM 사내 어댑터 뒤로 보류"됐는데, `backend/afm/MIGRATION.md:12` 에 따르면 어댑터는 2026-10-07 에 사무실에서 실행돼 31개 확인 항목 중 26개가 기대대로 나왔습니다. 그리고 바꿀 이음매가 `trendRows` 의 `centres` 한 곳입니다(`docs/research/2026-10-06-page-value-plans.md:505-541`). 덧붙여 짚을 불일치가 있습니다. 브레인스톰은 "AFM 관리 한계선"을 데이터가 주장을 받쳐 주지 못한다며 철회했는데, 시계열 비교의 01 추세 차트는 지금도 그룹 자신에서 계산한 μ ± 3σ 를 **UCL/LCL** 이라는 이름으로 그립니다(`frontend/app/utils/afmTrend.ts:91-99`). NIST 핸드북의 구분대로 관리 한계와 규격 한계는 다른 질문에 답하는 다른 선이고([NIST e-Handbook 6.3.2](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc32.htm)), 선택 그룹에서 다시 계산되는 띠는 그 어느 쪽도 아니므로, 이름을 "그룹 기준 범위"에 가깝게 바꾸고 고정 기준선이 생기면 그것을 기본으로 삼는 것이 철회 결정과 화면을 일치시킵니다. 같은 핸드북은 3σ 차트에 WECO run rule 네 개를 더하면 오경보가 약 371점당 1회에서 약 92점당 1회로 늘어난다고 적고 있어, 전수 추세가 생기더라도 규칙을 쌓기보다 범위 밖 한 가지만 표시하는 편이 맞습니다.

3번과 5번은 PKG fab 장비의 맥락에서 의미가 큽니다. 최근 외부 자료에서 inline AFM 의 성장 동인으로 가장 자주 등장하는 것은 hybrid bonding 이고, Bruker 응용 노트는 Cu pad recess 약 1–5 nm, 유전체 Rq 0.1–0.2 nm 를 관리 대상으로 제시합니다([Bruker AN5001](https://www.bruker.com/en/products-and-solutions/semiconductor-solutions/automated-afm-metrology/resource-library/an-5001-surface-metrology-for-hybrid-bonding-in-advanced-semiconductor-packaging.html), [벤더], 원문 확인; 성장세 판단은 시장 수치가 아니라 2024–2026 자료의 밀도에 기댄 것). MAP608 의 `Pad_1_H …`, `Dishing_H`, `Left_H / Right_H` 같은 컬럼 이름은 이 계열의 측정으로 보이지만, 컬럼 사전이 없어 이름만으로 한 [추론]입니다. 그 창이 팁에 의한 bias 와 가까운 크기라면 wafer 평균이 아니라 site 별 분포와 좌우 비대칭이 질문이 되고, 같은 point 의 `Left_H` 대 `Right_H` 산점도와 값으로 색칠한 격자가 바로 그 그림입니다. 다만 `Site X`·`Site Y` 는 단위 없는 정수 인덱스이고 방향 정보가 원본에 없으므로 **인덱스 격자까지만** 그리고 반경·center-edge 분해는 Q24 가 답해진 뒤로 미룹니다. 지금 "웨이퍼 히트맵"이라는 제목의 카드는 실제로 한 point 의 스캔 높이맵이므로(`frontend/app/components/afm/detail/HeatmapChart.vue:4`), 진짜 wafer 내 맵이 생기기 전에 이름부터 바로잡아야 혼동이 없습니다.

7번은 추천 4번의 범위를 줄인 것입니다. raw 높이 표본이 실제로 있다는 점은 AFM 의 가장 큰 미활용 자산이지만, Z 는 leveling 하지 않은 원본이고 단위가 파일마다 um/nm/pm/Pixel 로 다르며 5EAP1501 에는 profile 이 없고 모든 point 에 있지도 않습니다. 외부 문헌은 leveling 선택이 단차·dishing 의 숨은 매개변수이고 Rq 는 scan 길이와 표본 간격에 따라 달라져 대역이 다른 값끼리 직접 비교할 수 없다고 지적합니다([SPIE 7656](https://spiedigitallibrary.org/conference-proceedings-of-spie/7656/76562D/Comparison-of-optical-surface-roughness-measured-by-stylus-profiler-AFM/10.1117/12.863268.full), [요약만]; leveling 에 관한 부분은 조사자 추론). 그래서 첫 단계는 같은 recipe·같은 point·같은 단위의 1D 프로파일을 실제 축척으로 겹쳐 그리고 leveling 을 "없음 / 직선 제거" 중 무엇으로 했는지 화면에 적는 것까지입니다. 단차나 거칠기를 다시 계산해 장비가 쓴 `(nm)` 컬럼과 나란히 놓는 일은, 두 값이 어긋날 때의 해석 책임이 생기므로 leveling 정책이 합의되기 전에는 하지 않습니다. ISO 25178 매개변수와 Mandel/TMU 식은 조사에서 표준과 1차 논문을 읽지 못한 "미검증 배경지식"으로 분류됐으므로 구현 전에 원문 대조가 필요합니다.

하지 않을 것도 분명히 합니다. Spec 합격·Cp/Cpk, 팁 잔여 수명·교체 권고, 실제 가동률·OEE, 장비 간 matching, 정식 GRR 은 추천 보고서가 "추가 데이터 필요"로 보류했고 그 사유는 그대로입니다. AFM 은 업계에서 OCD·CD-SEM 을 검증하는 기준 계측으로 쓰이지만(여러 [요약만]·[벤더] 자료), 스큐노노의 AFM 데이터에는 device·step·oper 가 없고 AFM `lot_id` 가 e-beam 과 같은 체계인지도 근거가 없으며 MAP608 은 e-beam 장비와 fab 이 다릅니다. AFM ↔ CD-SEM 연결은 거절된 상태 그대로 두고, 풀리려면 lot 체계 일치 확인과 측정 시각을 공정 step 에 사상하는 규칙이 먼저라는 조건만 기록합니다. 한 가지 값싼 질문은 남습니다. 추출 실패가 목록에 보이지 않아 "측정이 없었다"와 "적재가 실패했다"를 구분할 수 없는데, 웹이 읽지 않는 Redis key `afm_download_history` 가 무엇을 담는지는 문서에 없습니다. 그 내용에 따라 보류된 "적재 건강" 항목이 새 로그 없이 풀릴 수도 있으나 이는 확인할 질문이지 제안이 아닙니다.

## 공유 링크가 보낸 사람의 화면을 재현하지 못하는 것이 가장 큰 UI/UX 손실입니다

UI/UX 에서 가장 먼저 손댈 곳은 미관이 아니라 **상태의 수명**입니다. 스큐보아는 "URL 이 유일한 진실"이라는 원칙을 세워 두었지만 view 를 `v-if` 로 갈아 끼우기 때문에 wafer map 의 Field/Die 와 색 범위, 반경 차수, 표의 필터와 정렬, 분포 모드, 공간 레이어, FDC 행렬 모드, 상관의 X/Y 축과 그룹화가 view 를 바꿀 때마다 초기화되고 URL 에도 없습니다(`frontend/app/components/ebeam/skewvoir/Workspace.vue:43-70`). 세트 범위 상관 링크는 기본 축으로 다시 열립니다. AFM 은 그룹·조회 기록·저장 그룹이 localStorage 에만 있고 검색과 시계열 비교 화면이 `route.query` 를 읽지 않아, 링크 복사는 측정 한 건만 됩니다. e-beam 의 스토리지, TTTM, 라이브 알람, 장비 상태, 디바이스 통계는 URL 계약이 아예 없고 Recipe 현황의 날짜 범위도 컴포넌트 지역 상태입니다. 분석 제품 사용자들이 필터 상태를 URL 에 넣어 달라고 명시적으로 요청한다는 사례([Adobe Experience League](https://experienceleaguecommunities.adobe.com/adobe-analytics-3/analysis-workspace-deep-linking-to-shared-dashboards-with-preselection-2941), [요약만])와, 전문가 도구는 사용자가 한 일과 생각을 기록하게 하고 Excel·PowerPoint 로의 이동을 의도적으로 설계하라는 NN/g 지침([NN/g](https://www.nngroup.com/articles/complex-application-design/), 전문가 의견, 원문 확인, 근거 연구는 얇음)이 같은 방향입니다. 처방은 단순합니다. "무엇을 분석하는가"를 바꾸는 선택은 URL 에, 개인 취향(썸네일 크기, 차트 테마)은 `usePersistedState` 에 둡니다. AFM 그룹은 20개 파일명을 URL 에 넣기 길므로 이미 있는 `/s/` 단축 주소에 싣는 것이 맞습니다.

두 번째는 **연결된 선택을 눈에 띄게 유지하는 것**입니다. 스큐보아의 `focusedSequence` 는 wafer map·반경 차트·표·이미지·FDC 커서를 묶지만, 연동 강조는 작으면 놓친다는 소규모 연구가 있습니다(11명 중 6명만 동작을 설명, [arXiv 1209.2244](https://arxiv.org/pdf/1209.2244), [요약만], 표본 작음). 선택된 site 를 rail 의 칩으로 고정해 보여 주고 비선택 점을 흐리게 하는 쪽이 윤곽선만 긋는 것보다 안전합니다. 여러 계열을 한 차트에 겹칠지 나눌지는 통제 실험 근거가 있습니다. 같은 x 위치의 국소 비교는 겹쳐 그리기가, 흩어진 구간의 모양 비교는 small multiples 가 빨랐고, 계열이 늘수록 정확도가 떨어졌으며 본 실험은 8계열까지였습니다([Javed et al. 2010](https://cs.au.dk/~elm/pdf/multilinevis.pdf), 통제 실험, 원문 확인). 스큐보아의 Sequence Trend 는 측정마다 선 하나라 세트 30건이면 30줄이고, H/W 관리의 장비 비교도 같은 문제를 가집니다. 선택한 계열만 강조하고 나머지를 회색 맥락으로 내리는 방식이 30색 범례보다 낫습니다.

세 번째는 **불균등한 마감**입니다. 측정 개요·상관·갤러리는 focus 조회가 실패하면 빈 문구로 떨어지고, 판정 블록 등 다섯 컴포넌트는 loading 상태가 없어 다음 MSR 을 읽는 동안 이전 수치를 계속 보여 줄 가능성이 있습니다 [추론]. 내보내기는 한 페이지군 안에서도 들쭉날쭉해서 H/W 관리는 7개 패널 중 BSM·Sharpness 둘만 되고, 교대 근무자가 인계에 쓸 법한 라이브 알람·측정 이력·TTTM 에는 없습니다 [추론]. AFM 상세의 5–8초는 어댑터 호출이 모두 1초 미만인데도 나오므로 요청 수·응답 크기·렌더링 중 어디인지 측정이 먼저이고, 10초가 주의를 붙잡는 한계라는 오래된 기준([NN/g](https://www.nngroup.com/topic/response-time/), [요약만])에 비추면 지금은 그 경계 바로 아래입니다. 이미지가 측정당 최대 133장인 AFM 과 HV-SEM 의 `-U/-T/-M/-L` 변형에는, 방사선 판독에서 유형별 자동 배치 규칙이 판독 시간을 줄였다는 근거(설문 추정 10–20%, 통제 실험 15%)가 참고가 됩니다([Journal of Digital Imaging 2004](https://link.springer.com/doi/10.1007/s10278-004-1003-9), [SFU 학위논문](https://summit.sfu.ca/item/8691), 둘 다 [요약만], 후자는 초보자 20명). 파일 순서가 point 순서가 아니라는 것이 이미 확인됐으므로 기본 배치는 메타데이터(point, 종류, variant)에서 와야 하고, 사용자가 바꾼 배치는 기억해야 합니다.

스큐보아·AFM 밖의 e-beam 페이지에 대해서는 새 아이디어보다 **남은 backlog 의 순서**가 답입니다. 측정 이력의 장비별 P50/P90(S4), 알람 → 스큐보아 검색(S17), 장비 상태 → H/W 링크를 전역 상태 변경에서 URL 로 교체하는 일은 모두 백엔드 변경이 없고 스큐보아 진입 경로를 넓히므로 스큐보아 0–2 단계와 함께 가는 것이 자연스럽습니다. 외부 문헌이 recipe 품질을 pattern-recognition 성공률과 측정 성공률, 다섯 가지 실패 분류로 보고한다는 점([US 7,716,009](https://patents.google.com/patent/US7716009), [특허])은 Recipe 현황의 Align Fail·Meas Fail 탭이 이미 같은 축 위에 있음을 확인해 줍니다. 다만 fail 배지는 mock 에 장비별 차이가 없어 집에서 재현되지 않고 상수가 모두 `OFFICE-VERIFY` 이므로, 이 페이지군에서 가장 검증이 덜 된 분석이라는 점은 사무실에서 먼저 확인할 일입니다. 채팅에 대해서는 검증이 병목이라는 연구([Kazemitabaar et al. 2024](https://arxiv.org/abs/2407.02651), 형성 연구 15명 + 피험자 내 18명)에 비추어, 현재의 "집계 먼저, 원시 행은 나중" 원칙과 출처 인용 구조를 유지하고 차트 이미지를 자유 서술로 해석시키는 기능은 피하는 것이 타당합니다.

## 코드 없이 사무실에서 먼저 답할 수 있는 질문들

위 권고의 여러 갈래는 구현이 아니라 확인 하나에 달려 있습니다. 답안지 형식으로 정리하면 다음과 같습니다.

| 질문 | 답에 따라 달라지는 것 |
| --- | --- |
| `/activity` 의 `top_features_30d` 와 장비 계열별 순위는 어떻게 나옵니까 | 스큐보아·AFM·backlog 사이의 전체 우선순위 |
| `measurement_score`·`addressing*_score` 의 척도와 `alignment.offset` 의 단위는 무엇입니까 | 스큐보아 품질 축의 축 이름과 색 범위 |
| 같은 recipe 는 항상 같은 wafer map 과 parameter 집합을 가집니까 | S7 delta 맵의 site 짝짓기, 분산 분해 후보 |
| 원본 measurement TIFF 는 장비 측 필터 없이 저장됩니까, 픽셀 크기와 프레임 수는 얼마입니까 | 이미지 파생 지표를 검토할지 여부 |
| AFM 에 주기적으로 재는 기준 시료 recipe 나 lot(`MON…`)이 있습니까 | 팁 건강 추세를 지을 수 있는지 |
| `afm_download_history` 에는 무엇이 들어 있습니까 | 적재 건강 가시성을 새 로그 없이 풀 수 있는지 |
| AFM 상세 5–8초는 요청 수·응답 크기·렌더링 중 어디에서 나옵니까 | 20건 상한을 클라이언트에서 올릴 수 있는지 |

per-view 사용 비콘은 문서끼리 어긋난 채 남아 있습니다. 10월 계획은 "인덱스 변경이 필요하므로 만들지 않습니다"라고 적었지만 8월 설계는 인덱스 변경 없이 동작하도록 만들어졌고(`docs/superpowers/specs/2026-08-04-skewvoir-view-usage-design.md:228-233`), 장비 계열 사용량은 실제로 비콘 URL 에 실어 인덱스 변경 없이 출시됐습니다. 스큐보아 6개 view 중 무엇이 쓰이는지 모르는 채로 세트 범위를 두껍게 하는 것은 추측에 투자하는 일이므로, 거절 사유가 사실과 맞는지 한 번 다시 볼 가치가 있습니다. 이것은 거절된 안의 재제안이 아니라 거절 근거에 대한 사실 확인 요청입니다.

## 결론

조사에서 얻은 가장 큰 전환은, 스큐노노가 다음에 얻을 가치가 "어떤 분석을 더 넣을까"가 아니라 "기존 분석이 무엇을 기준으로, 얼마나 오래, 얼마나 믿을 만하게 말하는가"에서 나온다는 점입니다. 스큐보아의 S7 과 AFM 의 S6 는 같은 결핍(선택과 함께 움직이는 통계)에 대한 같은 처방이고, 스큐보아의 61일 pickle 과 AFM 의 20건 상한은 같은 결핍(측정 단위 이력 층)의 두 얼굴입니다. AFM 이 팁 열 적재로 먼저 보여 준 해법 — 판정은 프런트 순수 함수에 두고 loader 가 측정당 요약 한 줄을 싣는다 — 은 e-beam 의 야간 rollup 논의에도 그대로 본보기가 되며, 영수증이 만료되지 않게 하려면 결국 그 층이 필요합니다.

외부 문헌이 주는 교훈은 화려한 쪽이 아니라 수수한 쪽에 있습니다. 근거가 탄탄했던 결과들의 공통점은 재사용, 즉 장비가 어차피 남기는 데이터에서 매칭·건강·recipe 품질 신호를 꺼내는 것이었고, 스큐노노는 그 데이터를 이미 응답에 싣고 있습니다. 반대로 숫자가 큰 주장(5–20배, 30%, 6개월)은 전부 기준선 없는 벤더 수치였고, 엔지니어 시간 절감을 독립적으로 측정한 연구는 찾지 못했습니다. 그러므로 다음 한 걸음의 성패를 가를 것은 문헌이 아니라 사무실의 `/activity` 숫자와 엔지니어 몇 사람의 답입니다.
