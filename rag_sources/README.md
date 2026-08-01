# RAG 원문 디렉터리 계약

이 디렉터리는 사내 RAG 원문의 배치 위치만 정의하는 Git-safe skeleton입니다.
실제 매뉴얼, 회의 자료, 이메일, 보고서, 추출 텍스트, page image 및 index artifact는
민감도와 관계없이 이 저장소에 commit하지 않습니다. `.gitignore`, 이 문서,
`HANDOFF.md`와 각 source 디렉터리의 `.gitkeep`만 추적합니다.

RAG 데이터를 생성하는 사내 로컬 LLM은 같은 폴더의 [`HANDOFF.md`](HANDOFF.md)를
먼저 읽습니다 — 전체 목표, 데이터 계약 체크포인트, 단계별 프롬프트가 거기에
있습니다.

## 디렉터리 의미

| 디렉터리 | 배치 대상 |
| --- | --- |
| `manuals/` | 승인된 장비 매뉴얼과 별도 ingestion workflow가 만든 page/region provenance입니다. |
| `meetings/` | 접근 권한과 보존 기간이 확인된 회의 요약 또는 색인 입력입니다. |
| `emails/` | 수신자·group·FAB 접근 규칙을 적용할 수 있는 승인된 이메일 색인 입력입니다. |
| `reports/` | revision 또는 기준일을 식별할 수 있는 승인된 업무 보고서 색인 입력입니다. |

운영 경로는 `back_dev_home/.env`의 `SKEWNONO_RAG_SOURCE_ROOT`에 이 디렉터리 또는
승인된 외부 source root의 절대 경로로 지정합니다. 실제 경로, 사내 문서명 및 내부
storage 정보는 `.env`와 사내 운영 문서에만 기록하며 이 저장소에는 기록하지 않습니다.

Flask chat runtime은 원문을 직접 scan하거나 index를 build, rebuild, mutate하지
않습니다. 별도의 offline ingestion workflow가 versioned index와 provenance manifest를
완성하고 원자적으로 배포해야 합니다. Runtime은 office knowledge adapter를 통해
배포가 완료된 read-only index만 조회합니다.
