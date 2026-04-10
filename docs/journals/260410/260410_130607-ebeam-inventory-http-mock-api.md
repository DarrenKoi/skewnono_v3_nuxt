## 1. 진행 사항
- `claude mcp add --transport http nuxt-ui-remote https://ui.nuxt.com/mcp` 명령으로 현재 프로젝트에 `nuxt-ui-remote` MCP 서버를 Claude 설정에 추가했다.
- `codex mcp add nuxt-ui-remote --url https://ui.nuxt.com/mcp` 명령으로 같은 MCP 서버를 Codex 설정에도 추가했다.
- `app/mock-data/ebeam-tool-inventory/` 아래 중복 Markdown 문서를 정리하고 `ebeam-tool-inventory.md` 단일 문서로 통합했다.
- E-beam inventory 조회 흐름을 mock 객체 직접 import 방식에서 HTTP API 호출 방식으로 전환했다.
- Nuxt 서버에 mock endpoint `server/routes/mock-api/ebeam/tools.get.ts`를 추가해 이후 Flask 서버 연동과 유사한 fetch 경로를 만들었다.
- `runtimeConfig.public.apiBase`와 `NUXT_API_TARGET` 기반 분기 설정을 정리해, 개발 중에는 로컬 mock API를 쓰고 이후 Flask 서버로 쉽게 전환할 수 있도록 구성했다.
- 변경 파일 기준으로 `bunx eslint nuxt.config.ts app/composables/useEbeamToolApi.ts app/composables/useToolData.ts app/components/ebeam/ToolInventoryView.vue app/components/nav/ToolTypeTabs.vue server/routes/mock-api/ebeam/tools.get.ts app/mock-data/ebeam-tool-inventory/ebeam-tool-inventory.ts` 검증을 통과했다.

## 2. 수정 내용
- `front-dev-home/nuxt.config.ts`
  `apiBase` 기본값을 `NUXT_API_TARGET` 유무에 따라 `/mock-api` 또는 `/api`로 분기하도록 수정했다. `devProxy`도 `NUXT_API_TARGET`이 있을 때만 활성화되도록 정리했다.
- `front-dev-home/server/routes/mock-api/ebeam/tools.get.ts`
  로컬 mock inventory를 HTTP로 반환하는 Nuxt server route를 새로 추가했다.
- `front-dev-home/app/composables/useEbeamToolApi.ts`
  `fetchToolInventory()`가 `$fetch`로 `${runtimeConfig.public.apiBase}/ebeam/tools`를 호출하도록 바꾸고, `filterRows()`로 응답 후처리를 분리했다.
- `front-dev-home/app/components/ebeam/ToolInventoryView.vue`
  화면에서 mock 객체를 직접 다루지 않고 HTTP inventory 응답을 받아 row/fab summary를 계산하도록 바꿨다.
- `front-dev-home/app/components/nav/ToolTypeTabs.vue`
  탭 배지 count도 같은 inventory HTTP 응답을 사용하도록 수정했다.
- `front-dev-home/app/composables/useToolData.ts`
  tool count의 mock import 의존성을 제거하고 정적 메타데이터만 남겼다.
- `front-dev-home/app/mock-data/ebeam-tool-inventory/ebeam-tool-inventory.md`
  장비별 중복 문서를 하나의 공통 inventory 스키마 문서로 통합했다.
- `front-dev-home/app/mock-data/ebeam-tool-inventory/ebeam-tool-inventory.ts`
  HTTP mock route가 사용하는 inventory source 파일로 유지했다.
- 삭제된 파일
  `front-dev-home/app/mock-data/ebeam-tool-inventory/hv-sem-equipment.md`
- 삭제된 파일
  `front-dev-home/app/mock-data/ebeam-tool-inventory/provision-equipment.md`
- 삭제된 파일
  `front-dev-home/app/mock-data/ebeam-tool-inventory/veritysem-equipment.md`
- 검증 메모
  `bun run lint`와 `bun run typecheck`는 저장소의 기존 이슈로 실패했다. `bun run build`는 client/server build와 `/` prerender까지 진행됐고, 마지막에는 샌드박스 네트워크 제한으로 `fonts.gstatic.com` 다운로드가 실패했다.

## 3. 다음 단계
- Flask 서버에 `/ebeam/tools` 엔드포인트를 구현하고 현재 mock 응답과 동일한 response shape을 맞춘다.
- Flask 연동 시 `NUXT_PUBLIC_API_BASE=/api`와 `NUXT_API_TARGET=http://127.0.0.1:5000`를 설정해 프론트 fetch 경로를 그대로 유지한다.
- 저장소의 기존 `bun run lint`/`bun run typecheck` 실패 항목을 정리해 전체 검증이 녹색으로 돌아오도록 만든다.
- 가능하면 외부 폰트 다운로드 의존성을 줄이거나 네트워크가 없는 환경에서도 빌드되도록 설정을 보완한다.

## 4. 메모리 업데이트
- 루트 `MEMORY.md`를 새로 추가했다.
- mock inventory는 클라이언트에서 직접 import하지 않고 HTTP로 가져오며, Nuxt mock route와 Flask 전환은 `runtimeConfig.public.apiBase` 및 `NUXT_API_TARGET`로 제어한다는 규칙을 기록했다.
