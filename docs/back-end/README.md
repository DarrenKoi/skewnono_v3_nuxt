# 백엔드 개념 문서

`back_dev_home/`의 구조 자체는 코드를 보면 알 수 있지만, **여러 모듈을 가로지르는 개념**은 따로 설명이 필요합니다. 이 폴더는 그런 가로축 문서를 모아둡니다.

| 문서 | 다루는 주제 |
| --- | --- |
| [api-tokens.md](api-tokens.md) | API 엔드포인트와 사용자/토큰의 관계, 인증 경로, 로깅 흐름 |
| [office-data-adapters.md](office-data-adapters.md) | Phase 2 데이터 adapter seam, 피처별 연결 명세, 사무실 LLM 프롬프트 |
| [provider-selection.md](provider-selection.md) | mock/office adapter 선택 규칙, site 감지 순서, 환경 변수 우선순위 |
| [vendor-onboarding.md](vendor-onboarding.md) | 신규 장비 계열(VeritySEM/Provision)을 붙이는 레이아웃 규약과 Phase 1 8단계 |

## 어떤 내용을 여기에 두는가

- 한 피처 폴더 안에서 끝나지 않는 흐름(예: 인증 미들웨어 → 로깅 → OpenSearch 인덱싱)
- 여러 모듈이 공유하는 규약(예: `g.user_id`, `g.api_token_id` 같은 요청 컨텍스트 속성)
- 댁/사무실 스왑 시 **유지되어야 하는 의미론**

## 어떤 내용을 여기에 두지 않는가

- 한 피처에만 해당하는 데이터 모양 → `docs/api-contracts/<feature>.yaml`
- 사무실 원본 테이블 스키마 → `docs/datatables/*.txt`
- 의사 결정 기록 → `docs/adr/`
- 환경 스왑 자체 전략 → `docs/swap-strategy.md`
