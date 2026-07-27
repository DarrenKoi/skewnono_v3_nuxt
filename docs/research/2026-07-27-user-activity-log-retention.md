# 사용자 활동 로그 보존 기간 조사

조사일은 2026-07-27입니다. 이 문서는 `/activity`와 `/admin/logs`가
OpenSearch 로그를 사용할 때의 보존 기간을 검토합니다. 법률 자문이 아니라
설계 판단을 위한 자료입니다.

## 결론

일반 사용자 활동 원본 로그를 **최근 180일 동안 검색 가능하게 보존**하는
정책은 제품 사용 분석의 합리적인 출발점입니다. 30일은 최근 운영 현황에는
유용하지만, 반기 추세와 낮은 빈도의 기능 사용을 분석하기에는 짧습니다.

다만 모든 로그에 통용되는 단일 기간은 없습니다. NIST SP 800-92와 OWASP는
법적·규제·조직 요구, 조사 필요 기간, 저장 용량과 접근성을 함께 고려해
보존·순환·보관·삭제 정책을 정하도록 안내합니다.

국내 「개인정보의 안전성 확보조치 기준」 제8조가 적용되는
개인정보처리시스템 접속기록이라면 180일은 부족합니다. 해당 기록은
일반적으로 1년 이상, 특정 조건에서는 2년 이상 보관해야 하며 위·변조,
도난, 분실 방지 조치도 필요합니다. 이 규정은 모든 제품 활동 로그에
자동 적용되지 않으므로 실제 시스템과 이벤트의 해당 여부를 먼저
확인해야 합니다.

## 공식 사례

| 사례 | 공식 보존 방식 | 판단 |
| --- | --- | --- |
| Google Analytics 4 | 사용자 단위 데이터는 2개월 또는 14개월, 기타 이벤트는 제품 등급에 따라 더 긴 기간도 선택합니다. | 제품 활동 원본을 수개월 보존하는 사례이며 180일은 그 범위 안의 보수적 시작점입니다. |
| GitHub Enterprise Cloud | 일반 enterprise audit event를 최근 180일 동안 제공합니다. | 180일 검색 가능한 감사 조회 사례가 존재합니다. |
| AWS CloudTrail | 기본 검색 가능한 management event history는 90일이며 장기 기록은 별도 trail 또는 event data store를 사용합니다. | 최근 검색과 장기 보존을 분리할 수 있습니다. |
| PCI DSS 4.0 | 적용 대상 audit log는 최소 12개월, 최근 3개월은 즉시 분석 가능해야 합니다. | 특정 규제가 적용되면 180일보다 길어야 합니다. 일반 제품 로그에 그대로 적용하는 규칙은 아닙니다. |

따라서 180일은 “관행상 정답”이 아니라 SKEWNONO의 일반 활동 분석 목적에
적합한 초기 정책입니다. 사고 조사, 내부 감사, 계약, 산업 규제 또는
개인정보 관련 의무가 더 긴 기간을 요구하면 해당 요구가 우선합니다.

## 개인정보와 로그 분류

GDPR 제5조는 목적에 필요한 범위로 개인정보를 제한하고, 식별 가능한
형태로 필요한 기간보다 오래 보관하지 않도록 규정합니다. `user_id`,
`remote_addr`, `query_string`, 예외 메시지 등은 개인정보나 업무 데이터를
포함할 수 있으므로 다음 원칙이 필요합니다.

- 요청·응답 본문, 인증 정보, 토큰, 비밀번호는 기록하지 않습니다.
- query와 예외 필드는 허용 목록, 마스킹, 최대 길이를 적용합니다.
- 조회 권한과 삭제 권한을 분리하고 관리자 조회 행위의 감사 여부를 정합니다.
- 목적을 달성했거나 법적 보존 기간이 끝난 식별 데이터는 자동 삭제합니다.

`/admin/logs`에서 보인다는 이유만으로 모든 행이 규제상 감사 기록이 되는
것은 아닙니다. 화면이 아니라 이벤트의 의미로 분류해야 합니다.

| 로그 범주 | 권장 검색 가능 기간 | 권장 총 보존 |
| --- | --- | --- |
| 제품 사용 활동 | 180일 | 180일 |
| 일반 오류·성능 로그 | 90~180일 | 180일 이하 |
| 보안·권한 감사 | 최근 조사 구간 | 내부 정책 또는 적용 법령 기준 |
| 제8조 적용 접속기록 | 운영상 필요한 구간 | 1년 또는 조건부 2년 이상 |

국내 제8조의 2년 조건은 5만 명 이상 정보주체의 개인정보를 처리하는
시스템, 고유식별정보·민감정보를 처리하는 시스템, 규정된
기간통신사업자에 해당하는 경우입니다. 개인정보보호 담당자가 적용
여부를 확인해야 합니다.

## 검색 가능 보존과 archive

`/activity`와 `/admin/logs`가 최근 180일을 즉시 조회해야 한다면 그 구간은
OpenSearch에서 검색 가능해야 합니다. OpenSearch의 `close` action은
디스크에는 남기지만 검색할 수 없게 하며, `snapshot` action은 등록된
repository로 백업합니다. 따라서 archive는 정상 화면 범위를 지난
장기 감사 기록에만 적용하는 편이 적합합니다.

localhost office와 cloud production의 동작을 맞추려면 두 환경에 동일한
alias, index template, ISM policy를 설치하고 애플리케이션은 계속
`ops_store`와 논리 alias만 사용해야 합니다. cloud 전용 storage tier는
초기 공통 경로에 넣지 않고, 장기 보관이 확정된 뒤 환경별 snapshot
repository로 추가하는 편이 안전합니다.

## `skewnono_logging` ISM 제안

현재 `ops_index_mgmt/skewnono_logging.py`는 하나의
`skewnono_logging` alias와 여러 번호형 backing index를 사용합니다.
`20gb` 또는 `7d`에 rollover하고 생성 후 `30d`에 삭제합니다. 하나의 논리
family와 여러 backing index를 쓰는 구조는 적절합니다.

최소 180일을 보장하려면 삭제 전이를 다음처럼 rollover 후 180일로
표현하는 안을 우선 검토합니다.

```json
{
  "state_name": "delete",
  "conditions": {
    "min_rollover_age": "180d"
  }
}
```

OpenSearch에서 `min_index_age`는 인덱스 생성 후 경과 시간이고,
`min_rollover_age`는 rollover 후 경과 시간입니다. 최대 7일 동안 기록한
인덱스를 `min_index_age: 180d`에 삭제하면 마지막 이벤트는 약 173일만
남을 수 있습니다. `min_rollover_age: 180d`는 모든 이벤트에 최소
180일을 보장하고 초기 이벤트는 약 180~187일 남깁니다. ISM은 주기적으로
조건을 확인하므로 실제 시점에는 job interval만큼 지연될 수 있습니다.

적용 전 office와 cloud OpenSearch 버전의 `min_rollover_age` 지원,
ISM explain 결과, alias write index, 180일 예상 용량을 확인해야 합니다.

## 하나 또는 여러 논리 인덱스

모든 이벤트가 동일한 180일 정책과 접근 권한을 사용하고 규제상 장기
보존 대상이 없다면 하나의 `skewnono_logging` family가 적합합니다.

개인정보처리시스템 접속기록, 권한 변경, 관리자 작업 등 장기 감사 대상이
포함되면 제품 활동·운영 로그의 180일 family와 감사 로그의 1년·2년
family를 분리하는 편이 적합합니다. 혼합 family는 가장 긴 기간을 모든
문서에 적용해야 하므로 데이터 최소화와 비용 측면에서 불리합니다.

`/activity/me`의 `first_seen`과 lifetime `top_features`는 원본을 180일
후 삭제하면 실제 lifetime 값이 될 수 없습니다. API 의미를 “최근 180일”로
바꾸거나, 별도 summary index와 그에 맞는 개인정보 삭제 정책을 정의해야
합니다.

## 공식 근거 자료

- [개인정보의 안전성 확보조치 기준 제8조](https://www.law.go.kr/LSW/admRulSideInfoP.do?admRulSeq=2100000281400&chrClsCd=010201&dashNo=&docCls=jo&joBrNo=00&joNo=0008&urlMode=admRulScJoRltInfoR)
- [EU GDPR Article 5](https://eur-lex.europa.eu/legal-content/EN/AUTO/?uri=CELEX:32016R0679)
- [NIST SP 800-92](https://csrc.nist.gov/pubs/sp/800/92/final)
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
- [Google Analytics data retention](https://support.google.com/analytics/answer/7667196)
- [GitHub Enterprise Cloud audit log](https://docs.github.com/en/enterprise-cloud@latest/admin/concepts/security-and-compliance/audit-log-for-an-enterprise)
- [AWS CloudTrail event history](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html)
- [PCI DSS v4.0 SAQ C](https://www.pcisecuritystandards.org/documents/PCI-DSS-v4-0-SAQ-C.pdf)
- [OpenSearch ISM policies](https://docs.opensearch.org/latest/im-plugin/ism/policies/)
