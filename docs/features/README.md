# 화면별 기능 설명

상단 탭마다 사용자에게 제공하는 기능을 화면 단위로 정리하는 폴더입니다. 팀원
공유용 문서이므로 개발 세부 사항(API 형태, adapter 선택, office DB 스키마)은
다루지 않고, 각각 `docs/api-contracts/`, `docs/back-end/`, `docs/datatables/`
를 참조합니다.

## 파일 규칙

- 파일 이름은 페이지 경로의 기능 slug 를 그대로 씁니다(`/recipe-search` →
  `recipe-search.md`). 한글 탭 이름은 문서 제목에 씁니다.
- 형식은 [AFM 기능 요약](../afm/feature-summary.md)을 따릅니다. 배경 → 대상
  장비·Fab → 화면 구성 → 주요 기능 → 데이터 출처 → 제한 사항 순서입니다.

## 탭 목록

| 탭 | 페이지 경로 | 문서 | 대상 장비 |
| --- | --- | --- | --- |
| 장비 상태 | `/ebeam/<type>/<fab>` | 작성 예정 | CD-SEM, HV-SEM |
| Recipe 현황 | `/ebeam/<type>/<fab>/recipe-status` | 작성 예정 | CD-SEM, HV-SEM |
| Recipe 검색 | `/ebeam/<type>/<fab>/recipe-search` | 작성 예정 | CD-SEM, HV-SEM |
| H/W 관리 | `/ebeam/<type>/<fab>/hardware` | 작성 예정 | CD-SEM, HV-SEM |
| 디바이스 통계 | `/ebeam/cd-sem/device-statistics` | 작성 예정 | CD-SEM |
| 스큐보아 | `/ebeam/<type>/skewvoir` | 작성 예정 | CD-SEM, HV-SEM |
| AFM | `/afm/<tool>` | [기능 요약](../afm/feature-summary.md) | AFM |

탭 구성의 기준은 `frontend/app/components/nav/FeatureTabs.vue` 입니다. 탭을
추가하거나 숨기면 이 표도 함께 고칩니다.
