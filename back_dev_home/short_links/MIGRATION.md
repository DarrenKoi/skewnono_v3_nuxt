# short_links — office migration

## Status: WRITTEN — activate by copying, no implementation left to do

`create_short_link` / `resolve_short_link` are implemented in the tracked
template against expiring Redis strings. The file holds no in-house address or
secret, so the copy is verbatim:

```bash
cp providers/office_example.py providers/office.py
```

- `office.py` is gitignored, so `git pull` never conflicts on it. It is also a
  **copy** — refresh it with `python -m scripts.sync_office_adapters
  short_links` if a later `git pull` moves the template, or the boot log will
  report `STALE office.py: short_links`.
- `REDIS_HOST` / `REDIS_PORT` / `REDIS_PASSWORD` 가 `back_dev_home/.env` 에
  있어야 하며, `_runtime/office_redis.py` 를 통해 해석됩니다.
- 사내 접속 정보를 조정할 때만 복사본을 수정하십시오. `routes.py`, `data.py`,
  `providers/mock.py`, `contracts.py`, `targets.py`, `tests/` 는 건드리지
  마십시오.

## 이 피처가 다른 피처와 다른 점: 읽기가 아니라 쓰기입니다

이 저장소의 office 어댑터는 대부분 사내가 이미 관리하는 테이블을 **읽습니다**.
short_links 에는 그런 원본이 없습니다. 행 자체를 이 앱이 만들어 내는 상태이므로
매핑할 사내 스키마가 존재하지 않으며, office 측은 질의 대상이 아니라 저장소입니다.

그래서 이 피처에는 `docs/datatables/` 항목이 **없습니다**. 그 폴더는 사내 DB 에
대해 우리가 아는 사실을 기록하는 곳인데, 여기에는 기록할 사내 DB 사실이 없습니다.
같은 이유로 `announcements` 와 `api_tokens` 에도 항목이 없습니다.

앱이 소유한 상태를 Redis 에 쓰는 기존 선례는 `_scheduler/runlog.py` 입니다.

## 키 배치

```text
skewnono:short_link:<code>   STRING  JSON {code, target, created_at}, TTL 365d
```

`<code>` 는 target 의 SHA-256 을 base32 로 인코딩한 앞 10자입니다. 즉 **코드는
저장소가 아니라 target 에서 유도됩니다.** 같은 화면을 두 번 공유해도 같은 코드가
나오므로, 동료가 이미 가진 링크가 두 번째 항목으로 갈라지지 않습니다.

base32 인 이유는 사람이 화면 캡처를 보고 코드를 다시 입력할 수 있기 때문입니다.
알파벳에 0/1/8/9 가 없어 O/0 나 l/1 처럼 잘못 읽을 짝이 생기지 않고, 대소문자나
문장 부호가 없어 메신저가 "교정"하며 망가뜨릴 여지도 없습니다.

## 홈 mock 이 대변하지 못하는 것

mock 은 프로세스 메모리의 dict 입니다. 다음 두 가지가 office 와 다르며, 둘 다
홈에서는 재현되지 않습니다.

| 항목 | mock (홈) | office |
| --- | --- | --- |
| 수명 | 프로세스 재시작 시 소멸 | TTL 365일, 재공유할 때마다 갱신 |
| 공유 범위 | 프로세스 1개 | 모든 uWSGI worker |

그러므로 홈에서 "링크가 만료되었다" 는 화면을 보는 것은 정상이며, office 에서
같은 일이 일어난다면 그것은 별개의 문제입니다.

## 장애 시 동작 — 인프라 장애를 데이터 판정으로 보고하지 않습니다

`access_control` 과 같은 규칙을 따릅니다. 두 함수 모두 저장소 실패를
`back_dev_home/__init__.py` 가 JSON 503 으로 매핑하는 맨 `RuntimeError` 로
변환합니다.

- `create_short_link` — **raise**. 저장하지 못한 코드를 돌려주면 영원히 404 가
  나는 링크를 사용자에게 쥐여 주는 셈이고, 사용자는 그것을 보고서에 붙여 넣은
  뒤에야 알게 됩니다. 프런트엔드는 이 호출이 실패하면 긴 URL 을 대신 복사하도록
  되어 있는데, 그 대비책은 오류가 실제로 도달해야만 동작합니다.
- `resolve_short_link` — `None` 이 아니라 **raise**. `None` 은 "이 링크는
  존재하지 않는다" 라는 뜻이어서, 장애 중에 그것을 돌려주면 멀쩡한 링크를 두고
  다시 만들라고 안내하는 꼴이 됩니다. 503 은 "다시 시도하라" 라고 말합니다.

## 보안 — 이 피처는 리다이렉터입니다

`/s/<code>` 는 저장된 target 으로 브라우저를 보냅니다. 따라서 `targets.py` 의
`normalize_target` 은 정리용 검사가 아니라 이 기능의 보안 경계입니다. 빠진
경우 하나가 곧 오픈 리다이렉트이며, 이는 사내 직원이 신뢰하도록 교육받은
호스트명을 뒤집어쓴 피싱 수단이 됩니다.

검사는 **쓰기 시점에만** 이루어집니다. 저장된 target 은 정의상 신뢰되므로
읽기 경로에는 두 번째 관문이 없고, 따라서 어긋날 관문도 없습니다. office
어댑터에 검증을 추가하지 마십시오 — 추가하는 순간 서로 어긋날 수 있는 관문이
두 개가 됩니다.
