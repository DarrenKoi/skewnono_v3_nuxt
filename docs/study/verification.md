# 2026-10-03 학습 문서 검증 기록

이 기록은 학습 문서·HTML의 확인 범위를 설명합니다. runtime 코드를 변경하거나 사내 서비스에 접속해 검증한 기록이 아닙니다.

## 기초 개념과 검증 용어

코드 대조는 설명이 실제 호출 경로·설정과 같은지 확인하는 일입니다. 초심자 점검은 용어와 선행 지식·작은 예제·실습의 기대 결과를 확인하는 일입니다. 정적 검사는 파일·링크·원본 hash처럼 실행 없이 확인하는 항목이며 browser 검사는 실제 화면과 이동을 확인하는 일입니다. 서로 대체하지 않습니다.

## 1차: 현재 구현과 대조

검사 대상은 기존 01~13 전체와 01·07 보조 문서, home·questions, 새 14~16입니다. `CLAUDE.md`를 먼저 읽고 frontend 설정·package/lock/설치, API composable·cache·persisted state, design tokens, backend factory·provider·auth·logging·scheduler·SPA, 차트·좌표·통계 함수 및 테스트, CI·pack·deployment를 대조했습니다.

중요한 정정은 실제 설치 버전과 선언 범위 분리, 과거 frontend mock 경로 제거, 현재 API 타입 소유자, Nuxt 캐시와 성공 Promise 캐시의 수명, sync watcher의 영속화 범위, Blueprint package export, 사내 office readiness, 실제 uWSGI HTTP 설정과 SPA mount의 cloud 경로 조건입니다. 사내 template와 실제 실행 adapter는 구분합니다.

## 2차: 초심자 관점

각 장에서 기초 개념·용어·구현·이유와 한계·실수·안전한 확인으로 학습 흐름을 연결했습니다. Python/TypeScript 값의 차이, 반응성과 영속성, API 교환 계약, process/thread, 신원과 권한을 작은 예시로 분리했습니다. 기존 문법 예제·Q1·Q2를 유지하고 실제 파일의 위치를 고쳤습니다.

실습은 저장소 루트 또는 frontend 디렉터리를 표시하고 읽기 전용 탐색·작은 순수 함수 확인·이미 준비된 home mock의 진단을 우선합니다. 사내 pack·배포·삭제·token 작업은 home 실습과 구분합니다. 신뢰되지 않은 pickle 열기, localStorage 전체 삭제, 운영 DB 쓰기와 같은 연습을 피합니다.

## 3차: 링크·명령·Markdown·브라우저

정적 검사와 실제 브라우저 결과는 최종 실행 후 아래에 기록합니다. HTML은 같은 Markdown parse 결과로 생성하며 각 파일의 `source-sha256`와 본문을 검증합니다. 전체 내부 문서·anchor·이미지·code 링크를 검사하며, 외부 공식 문서 링크는 생성된 페이지의 실행 의존성이 아닙니다.

### 재현 명령

저장소 루트에서 다음 명령을 사용합니다. 첫 명령은 HTML 문서만 생성하며 두 번째는 읽기 전용 검사입니다.

```bash
node docs/study/build-html.mjs
node docs/study/check-site.mjs
npm run lint:md
```

### 실제 결과

- **내용 대응:** Markdown 23개와 대응 HTML 23개, 추가 입구 `index.html`을 생성했습니다. 원본 SHA-256(Secure Hash Algorithm 256-bit)과 렌더 본문 hash를 비교하고, 코드 블록 142개를 원문과 비교했습니다. 변경된 HTML 본문을 일부러 넣은 음성 검사에서 검증기가 실패하는 것도 확인한 뒤 원복했습니다.
- **링크:** 로컬 링크·anchor 1005개를 검사했고 누락 0건입니다. 원본 Markdown 링크, HTML 학습 문서 링크, 저장소 코드 링크, 온라인 공식 문서 링크를 구분합니다.
- **Markdown:** 저장소 전체 `npm run lint:md`는 당시 203개 파일을 검사해 오류 0건입니다. 따라서 별도로 남은 기존 Markdown 오류도 없습니다. `git diff --check`도 통과했습니다.
- **실제 브라우저:** Playwright의 Chromium으로 `file://` 파일을 직접 열고 네트워크 offline 상태에서 HTML 24개를 1280·390·320px 너비로 모두 순회했습니다(72회). 각 문서의 목차 anchor와 이전·다음 이동을 실제 클릭했습니다. 문서 가로 넘침·깨진 이미지·page error·HTTP 원격 요청은 0건입니다.
- **모바일·긴 자료:** 긴 table과 code는 자신의 영역에서 overflow하도록 확인했습니다. 390px에서 긴 코드와 SVG의 scrollLeft가 실제 변하는 것을 확인했습니다. 여섯 SVG를 각각 열어 text bounding box가 viewBox 밖으로 잘리지 않는지 검사했습니다. 홈의 desktop 화면과 통계 그림의 mobile 화면은 screenshot으로 눈으로 확인했습니다. 그림의 실제 비례 축척 여부를 본문에 구분했습니다.
- **접근성:** `lang=ko`, viewport, 단일 h1, 표·그림 스크롤 focus, native details 목차를 확인했습니다. Tab의 첫 focus가 ‘본문으로 건너뛰기’에 보이는 outline으로 도착하고 Enter 후 main으로 이동했습니다. 본문·링크·상단·주석·코드·그림 강조 색 쌍의 대비는 모두 4.5:1 이상(최저 7.01:1)이었습니다. 스크린리더 사용자 시험까지 수행했다는 의미는 아닙니다.
- **실습:** 문서에 연결된 순수 함수 Node 테스트 125개와 backend site/provider·sem_list 테스트 55개가 통과했습니다. TypeScript strict 작은 실습, JSON/불리언 예시, Vue 배열 교체·sync watcher 메모리 예시, 실제 cache helper의 성공 Promise 유지/reset/실패 재시도, 통계·좌표 수치 예시를 실행했습니다. 수정 runtime에 대한 full suite가 아니라 학습 예시의 확인입니다.

**기존 실행 환경 오류:** 기본 PATH의 Homebrew Node 25.6.1은 `libllhttp.9.3.dylib` 누락으로 기동하지 않았습니다. 별도로 설치된 NVM의 Node 24.13.0과 npm 11.19.1을 선택해 검사했습니다. 패키지·시스템 라이브러리는 수정하지 않았습니다. agent-browser는 sandbox 내 daemon을 시작하지 못해 Playwright 브라우저로 확인했습니다.

## 남은 사내 확인

- 실제 Python·Node 빌드 환경과 package 버전, 사내 영구 `index.py`·`wsgi.ini`의 내용입니다.
- office adapter 사본 freshness, DB schema·null·분포, Redis·OpenSearch·MinIO·FTP 응답과 권한입니다.
- cookie 전달·token 폐기·admin allowlist·실제 proxy 신뢰 경계·TLS 종료 위치입니다.
- worker 1 scheduler 선출, Redis 잠금 갱신, reboot 중 작업 처리, 로그 alias 적재와 dropped 지표입니다.
- SQLite 파일 권한·WAL·동시 사용·backup, RAG checkout/index 준비 여부입니다.

## 선택 이유와 흔한 실수

완료라고 표시하는 것은 위 문서·HTML의 확인 범위에 한정합니다. 사내 gate를 local mock test로 대체하면 배포 후에만 발견되는 오류가 생깁니다. 문서를 다시 고칠 때 Markdown만 수정하고 HTML을 재생성해야 두 형식이 어긋나지 않습니다.
