# 학습 질문 모음

이 문서는 질문과 관측을 모으는 수정 가능한 원본입니다. 자동 답변 작업의 현재 실행 여부는 확인되지 않았으므로, 저장했다고 답변이 자동 생성된다고 가정하지 않습니다. [학습 홈](README.md)의 읽는 순서와 아래 연결 문서를 함께 사용합니다.

## 1. 기초 개념: 좋은 질문은 예상과 관측을 연결합니다

‘캐시가 뭔가요?’에서 시작해도 됩니다. 다음 단계에서는 어떤 값이 어디에 남고 언제 사라질지 예상한 뒤 실제 코드와 비교합니다. 이 차이를 설명하는 능력이 안전하게 수정하는 능력으로 이어집니다.

## 2. 용어와 질문 형식

가설은 아직 확인하지 않은 예상입니다. 관측은 실제 검사에서 본 값입니다. 근거는 관측이나 주장을 다시 확인할 수 있는 파일·테스트·공식 문서입니다. 미확인은 특히 사내에서만 검증할 수 있어 현재 결론을 내리지 않은 항목입니다.

```md
## Q번호. 질문 제목

- 배경: 어떤 화면·기능을 이해하려고 합니까?
- 예상: 값·요청·권한이 어떻게 흐른다고 생각합니까?
- 읽은 파일: 저장소 상대 경로와 함수 이름입니다.
- 관측: 사용한 명령·환경과 실제 결과입니다.
- 남은 의문: 어느 단계가 아직 설명되지 않습니까?
- 확인 범위: 일반 개념 / 로컬 mock 확인 / 사내 미확인입니다.
```

## 3. 기존 질문과 현재 구현의 답

### Q1. `$fetch`와 `useFetch`, `useAsyncData`를 언제 무엇을 써야 하나?

**기존 질문:** 사용 맥락이 헷갈립니다. composable 안에서는 `$fetch`만 쓰는 것이 맞는지, page에서는 무조건 `useAsyncData`로 감싸야 하는지 궁금합니다.

`$fetch`는 요청 도구이고, `useAsyncData`는 key 기반의 데이터·pending·error·갱신 상태를 관리합니다. `useFetch`는 둘을 결합한 Nuxt 도구입니다. 위치가 page인지 composable인지보다 자원의 공유·수명·갱신 요구가 선택 기준입니다. 이 저장소의 실제 장비 목록은 `$fetch`를 `useAsyncData`와 cache helper로 감싼 composable이며 성공 Promise를 유지하는 정책이 추가되어 있습니다. 따라서 모든 page에 같은 래퍼를 중복해서 만드는 것이 답은 아닙니다.

- [03 Nuxt의 요청과 캐시](03-nuxt/README.md)
- [07 장비 목록 캐싱의 실제 수명](07-code-patterns/sem-list-caching.md)
- [useSemListApi.ts](../../frontend/app/composables/useSemListApi.ts)

### Q2. Phase 2로 넘어가면 mock-data 폴더는 삭제해야 하는가?

**기존 질문:** Phase 1 전용 데이터를 어디까지 유지할지, 테스트용으로 남겨둘지 기준을 세우고 싶습니다.

현재 API 업무 데이터는 모든 phase에서 Flask를 통하며 home용 mock은 기능의 `providers/mock.py`에 있습니다. 과거 frontend의 `app/mock-data` 설명을 현재 데이터 경로로 읽지 않습니다. mock는 home 개발과 contract 검증의 기반이므로 office 전환했다고 삭제하지 않습니다. frontend `app/data`의 local reference 자료와 업무 API mock도 같은 종류가 아닙니다.

- [10 provider의 환경 선택과 계약](10-backend-providers/README.md)
- [13 검증 범위](13-testing/README.md)
- [16 저장소별 역할](16-storage-deployment/README.md)

## 4. 선택 이유와 한계

질문을 실제 경로와 연결하면 같은 개념을 여러 장에서 반복 설명하는 대신 기존 설명을 다시 사용할 수 있습니다. 그러나 로컬에서 직접 확인하지 않은 사내 현상을 단정적으로 답하지 않습니다. ‘template에 있다’는 근거는 ‘실제 office에서 실행됐다’는 근거와 다릅니다.

## 5. 흔한 실수

secret·token·실제 사번을 관측 예제에 복사하지 않습니다. 에러 로그에서 민감한 값을 지운 뒤 현상·상태 코드·함수 이름만 기록합니다. 테스트가 통과했다는 사실만 적고 어떤 환경과 경계를 확인했는지 생략하지 않습니다.

## 6. 안전한 학습 실습과 다음 질문

아래 질문마다 먼저 링크된 장을 읽고 실행 없이 종이에 답합니다. 실행 검사가 필요하면 해당 장의 안전한 실습만 사용합니다.

1. [02](02-vue-basics/README.md)·[07](07-code-patterns/persisted-state.md): `ref`, `useState`, localStorage 중 새로고침 뒤 남는 것은 무엇이며 왜입니까?
2. [14](14-runtime-http/README.md): 직접 Flask 요청은 성공하고 Nuxt 경유 요청만 실패하면 어디부터 확인합니까?
3. [10](10-backend-providers/README.md): office mode인데 한 기능만 mock인 것은 어떤 조건에서 정상입니까?
4. [15](15-process-auth-operations/README.md): 관리자 사번을 자기 입력한 사람이 왜 관리자 API를 사용할 수 없습니까?
5. [12](12-statistics-wafer/README.md): 차트의 화면 y축을 반전하는 것과 물리 좌표 원점을 바꾸는 것은 어떻게 다릅니까?
6. [16](16-storage-deployment/README.md): bundle에서 `chat.db`, `index.py`, `wsgi.ini`를 제외하는 이유는 무엇입니까?

### 내가 쓸 질문들

여기부터 Q3 등의 번호로 추가합니다. 질문을 추가한 뒤 HTML 재생성 방법은 [학습 홈](README.md)의 안내를 따릅니다.
