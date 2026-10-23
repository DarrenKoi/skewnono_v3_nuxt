# Provision 데이터 테이블 (stub)

이 폴더는 Provision (Applied Materials) CD-SEM 의 office 데이터 스키마
문서를 담을 자리입니다. 현재는 stub 상태 — vendor 가 추가되지 않았습니다.

## 추가 절차

`.claude/skills/add-vendor/SKILL.md` 의 절차를 따릅니다. 그 스킬은
`backend/<feature>/providers/<family>/` 골격을 만들고 mock/office
adapter 를 도입하며, 이 폴더에 스키마 문서를 추가하는 작업까지 한 흐름으로
처리합니다.

## 현재까지 확인된 사실 (user-confirmed 2026-10-13)

| 항목 | 상태 |
| --- | --- |
| 장비 명부 | 있습니다. `sem_list` 소스에 포함되며 `eqp_model_cd` 접두사 `PROVISION*` 로 구분합니다 (`../hitachi/sem_list.txt`) |
| FTP | 사내에서 접속할 수 있습니다. 계정은 Hitachi 와 다른 이 계열 전용 `wf…` 계정입니다(전체 이름은 사무실 `.env` 에만 둡니다, user-confirmed 2026-10-14). 측정 결과는 FTP 의 `/I_Drive` 와 `/D_drive/` 두 곳에 쌓입니다(같은 날 확인). 두 곳의 역할 차이와 하위 구조·파일 형식은 `OFFICE-VERIFY` 입니다 |
| 측정 단위 | 측정 1회가 파일 또는 폴더 1개입니다 (user-confirmed 2026-10-14) |
| Redis · OpenSearch 소스 | 측정 데이터 소스는 **없습니다.** 읽을 대상이 아니라 적재(loader)부터 만들어 나가야 합니다. 단, 장비별 data host 명부 Redis `v3_df_provision_hosts` 가 있습니다 (`provision_hosts.txt`, user-confirmed 2026-10-23) |
| data host | 이 계열은 데이터를 장비 IP 가 아닌 **별도 data host IP** 에서 꺼냅니다. `sem_list` 의 `eqp_ip` 는 장비 IP 이므로 데이터 추출에 쓰지 않습니다. 측정 CSV export 는 data host FTP 의 P-drive(`spreadsheet_path`)에 있습니다 (user-confirmed 2026-10-23) |
| 측정 이력 | **없습니다.** `meas_hist` 에 이 계열 문서가 없으며 적재부터 만들어야 합니다 |
| 알람 ALID | Hitachi(9006 / 9007 / 9035)와 다릅니다. 실제 코드는 `OFFICE-VERIFY` (추후 확인 예정) |

따라서 이 계열의 feature 는 "기존 소스에 어댑터를 붙이는" 작업이 아니라
"FTP 에서 소스를 만드는" 작업이 먼저입니다.
