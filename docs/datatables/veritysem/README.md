# VeritySEM 데이터 테이블 (stub)

이 폴더는 VeritySEM (Applied Materials) CD-SEM 의 office 데이터 스키마
문서를 담을 자리입니다. 현재는 stub 상태 — vendor 가 추가되지 않았습니다.

## 추가 절차

`.claude/skills/add-vendor/SKILL.md` 의 절차를 따릅니다. 그 스킬은
`backend/<feature>/providers/<family>/` 골격을 만들고 mock/office
adapter 를 도입하며, 이 폴더에 스키마 문서를 추가하는 작업까지 한 흐름으로
처리합니다.

## 현재까지 확인된 사실 (user-confirmed 2026-10-13)

| 항목 | 상태 |
| --- | --- |
| 장비 명부 | 있습니다. `sem_list` 소스에 포함되며 `eqp_model_cd` 접두사 `VERITY*` 로 구분합니다 (`../hitachi/sem_list.txt`) |
| FTP | 사내에서 접속할 수 있습니다. 계정은 Hitachi 와 다른 이 계열 전용 `rtauser` 입니다 (user-confirmed 2026-10-14). 측정 결과는 장비의 `D:\Output` 에 쌓이며(같은 날 확인), FTP 에서는 `/D_Drive/Output` 입니다 (user-confirmed 2026-10-23). 하위 구조·파일 형식은 `OFFICE-VERIFY` 입니다 |
| tool version | 장비의 `/D_drive/Qrelease/current_version.ini` 원문 문자열이며 형식은 `Ver_<maj>_<min>_<pat>_<build>_Win7` 입니다. Provision(`16.10.33.40755`)과 정규화하지 않습니다 (user-confirmed 2026-10-23). Provision 의 `v3_df_provision_version` 과 같은 key 계열이지만, 이 계열의 정확한 key 이름은 `OFFICE-VERIFY` 입니다 (`../provision/provision_hosts.txt`) |
| 측정 단위 | 측정 1회가 파일 또는 폴더 1개입니다 (user-confirmed 2026-10-14) |
| Redis · OpenSearch 소스 | 측정 데이터 소스는 **없습니다.** 적재(loader)부터 만들어야 합니다. 단, 장비별 host 명부 Redis `v3_df_verity_hosts` 가 있습니다 — tool IP 가 곧 data IP 이며, 결과 폴더와 Veridity 리포트 폴더의 접속 여부를 담습니다 (`verity_hosts.txt`, user-confirmed 2026-10-23) |
| 측정 이력 | **없습니다.** `meas_hist` 에 이 계열 문서가 없으며 적재부터 만들어야 합니다 |
| 알람 ALID | Hitachi(9006 / 9007 / 9035)와 다릅니다. 실제 코드는 `OFFICE-VERIFY` (추후 확인 예정) |

따라서 이 계열의 feature 는 "기존 소스에 어댑터를 붙이는" 작업이 아니라
"FTP 에서 소스를 만드는" 작업이 먼저입니다.
