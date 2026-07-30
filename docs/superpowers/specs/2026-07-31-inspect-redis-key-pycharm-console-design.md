# Redis 키 검사 스크립트 PyCharm 콘솔 전환 설계

## 목적

`scripts/inspect_redis_key.py`를 PyCharm의 **Run File in Python Console** 기능으로
실행한 뒤 Redis 응답과 역직렬화된 DataFrame을 Variables 창에서 직접 확인할 수
있게 합니다.

## 현재 문제

현재 스크립트는 `argparse`로 입력을 받고 실제 실행을 `main()` 안에서 수행합니다.
따라서 `args`, `client`, `raw`, `df` 같은 조사 대상이 함수의 지역 변수로 끝나며,
실행 후 PyCharm 콘솔에서 바로 조회할 수 없습니다.

## 변경 설계

- 명령행 인자 처리, `main()` 함수, `if __name__ == "__main__"` 실행 가드를
  제거합니다.
- 파일 상단에 사용자가 실행 전에 편집할 수 있는 설정값을 둡니다.
  - `KEY_NAME`: 검사할 Redis 키입니다.
  - `ROWS`: 출력할 표본 행 수입니다.
  - `UNIQUE_COLUMNS`: 전체 값별 건수를 출력할 열 목록입니다.
- Redis 연결과 키 조회를 모듈 최상위에서 수행합니다.
- `client`, `key`, `kind`, `raw`, `df`를 모듈 변수로 유지하여 PyCharm Variables
  창과 콘솔에서 접근할 수 있게 합니다.
- 기존 DataFrame 요약 함수와 안전한 Redis 조회 방식은 유지합니다.

## 실행 흐름

1. 사용자가 `KEY_NAME`과 선택 설정을 편집합니다.
2. PyCharm에서 **Run File in Python Console**을 실행합니다.
3. 스크립트가 Redis 타입을 확인하고 값을 읽습니다.
4. 문자열 값이 DataFrame이면 `df`에 저장하고 기존 요약을 출력합니다.
5. 사용자는 콘솔에서 `df`, `raw`, `kind`, `client` 등을 추가로 조회합니다.

## 오류 처리

Redis 설정 누락, 연결 실패, 키 누락은 예외를 숨기지 않습니다. 오류가 발생하기
전까지 만들어진 모듈 변수는 그대로 남기며, 사용자가 PyCharm 콘솔에서 상태를
확인할 수 있게 합니다. Redis 쓰기, 만료, 삭제 명령은 추가하지 않습니다.

## 호환성과 검증

이 파일은 명령행 도구가 아니라 대화형 조사 스크립트로 전환됩니다. 다른
스크립트가 가져오는 `_human_bytes`와 `describe_dataframe` 함수는 유지합니다.
검증에서는 문법 컴파일, import 사용처, 정적 테스트, Markdown lint를 확인합니다.
