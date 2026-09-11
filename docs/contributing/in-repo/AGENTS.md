# AGENTS.md 템플릿 (저장소 안에서 기여)

이 파일을 `backend/contrib/<slug>/AGENTS.md` 와 `apps/<slug>/AGENTS.md` 에 복사하고
`<...>` 를 채웁니다. 아래 가로줄 밑이 동료의 사내 LLM 이 읽는 본문입니다.

---

# `<slug>` 작업 공간

- 소유자: `<이름>`
- 목적: `<한 줄>`
- 읽는 사내 소스: `<OpenSearch 인덱스 / Redis 키>`
- 부르는 SKEWNONO API: `<없음 또는 목록>`

## 이 저장소에서 당신의 자리

당신은 SKEWNONO 저장소 안의 **한 폴더**를 맡습니다. 이 폴더 밖의 코드는 소유자의
것이고, 당신이 만든 것이 깨져도 SKEWNONO 가 뜨도록 설계되어 있습니다. 그 설계를
지키는 것이 당신의 첫 번째 규칙입니다.

작업 전에 읽을 것은 이 파일, `docs/contributing/README.md`,
`docs/contributing/in-repo/README.md`, 저장소 루트 `AGENTS.md` 입니다. 화면을
`frontend/app/` 안에 만들 때만 `DESIGN.md` 를 더 읽습니다. 그 밖의 파일은 본보기로
지목된 것만 엽니다.

## 반드시 지킬 것

1. **편집 범위.** `backend/contrib/<slug>/` 와 `apps/<slug>/` 안만 편집합니다. 그 밖에
   손대도 되는 것은 `frontend/app/pages/<slug>.vue` 한 장과
   `frontend/app/utils/headerNav.ts` 의 항목 한 줄뿐입니다. 다른 파일을 고쳐야 할 것
   같으면 고치지 말고 `MIGRATION.md` 에 이유를 적어 소유자에게 맡깁니다.
2. **import 범위.** 공유 코드 중 import 해도 되는 것은 `backend._core` 뿐입니다. 다른
   기능 패키지(`backend.sem_list` 등), `backend._runtime`, `backend._auth`,
   `backend._logging` 은 import 하지 않습니다.
3. **슬러그.** 백엔드 폴더와 API 접두어는 `<slug>` (snake_case), 페이지 경로는
   `/<slug-kebab>` 입니다. 바꾸지 않습니다.
4. **패키지 모양.** `__init__.py` 에 `from .routes import bp`, `routes.py` 에
   `bp = Blueprint("<slug>", __name__)`, 모든 경로는 `/<slug>/...` 로 시작,
   `tests/__init__.py` 가 있어야 합니다.
5. **import 시점에 사내 자원을 만지지 않습니다.** 연결은 첫 호출에서 엽니다.
6. **에러.** 사내 소스를 못 읽으면 `raise RuntimeError("...")` (정확히 이 클래스),
   잘못된 요청은 `flask.abort(400)`. 다른 기능의 예외 클래스를 가져오지 않습니다.
7. **동시성.** 스레드, 타이머, 스케줄러를 만들지 않습니다. 주기 작업이 필요하면
   `MIGRATION.md` 에 적고 소유자에게 맡깁니다.
8. **의존성.** `backend/requirements.txt` 와 `frontend/package.json` 을 편집하지
   않습니다. 새 패키지가 필요하면 `MIGRATION.md` 에 적습니다.
9. **providers/ 를 만들지 않습니다.** mock/office 이중화는 이 폴더에 해당하지 않습니다.
10. **요청 수.** 사용자당 `/api/*` 예산이 50 req / 5 s 이고 SKEWNONO 전체와 공유합니다.
    한 화면에서 반복 호출을 만들지 않습니다.
11. **프런트엔드는 `apps/<slug>/` 의 Vite 앱입니다.** `base: '/ws/<slug>/'`,
    `outDir: '../../frontend/public/ws/<slug>'`, 해시 라우터. 빌드 산출물은 gitignore
    되어 있으니 commit 하지 않습니다. `frontend/app/` 안에 컴포넌트를 만들지 않습니다
    (승격 전).
12. **git.** 자기 폴더의 파일만 명시해서 stage 합니다. `git add -A`, `git add .`,
    `git commit -a` 는 쓰지 않습니다. 넘기기 전에 commit 하고 `git status` 가 깨끗한지
    확인합니다.
13. **문서.** `MIGRATION.md` 와 이 파일은 한국어 `~입니다` 체로 씁니다. 표는
    markdownlint `MD060` compact 스타일입니다.

## 끝내기 전에 돌릴 것

```bash
.venv/bin/python -m pytest backend/contrib/<slug> -q   # 저장소 루트
.venv/bin/python -m ruff check .
npm run lint:md                                        # 저장소 루트
npm run typecheck && npm run lint && npm test          # frontend/. 진입 페이지나 headerNav.ts 를 만졌다면
```

해당하는 것이 모두 통과하고 `git status` 가 깨끗할 때만 "끝났다" 고 말합니다.
