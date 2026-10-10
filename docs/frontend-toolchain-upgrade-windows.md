# Windows 사무실 프론트엔드 도구 업그레이드

기준일은 2026-10-10입니다. 도구 업데이트 커밋은 `03ff0e9e`입니다.
사무실 개발 PC와 프론트엔드 빌드 PC에 적용합니다.
실제 Windows·사내 데이터 환경에서는 아직 실행하지 않았습니다.

## 1. 목표 버전과 적용 순서

| 도구 | 목표 버전 | 비고 |
| --- | --- | --- |
| Node.js | 24.21.0 LTS | 검증에 사용한 Node 24 최신 패치입니다 |
| ESLint | 10.12.0 | Nuxt ESLint와 함께 적용합니다 |
| @nuxt/eslint | 1.17.0 | 하위 Unicorn 플러그인이 ESLint 10.4 이상을 요구합니다 |
| vue-tsc | 3.3.12 | Vue 템플릿 타입 검사 도구입니다 |
| TypeScript | 6.0.3 | TypeScript 7로 올리지 않습니다 |

개발 시 설치 순서는 Node → ESLint와 Nuxt ESLint → vue-tsc → TypeScript였습니다.
사무실에서는 이미 검증한 `package.json`과 `package-lock.json`을 가져오므로,
**Node 설치 → Git 업데이트 → `npm.cmd ci` → 검증** 순서로 적용합니다.
`npm ci`가 네 도구와 하위 의존성을 lockfile 버전으로 한 번에 설치합니다.
각 패키지의 `@latest` 설치 명령을 사무실에서 다시 실행하지 않습니다.

Node 24 계열의 하위 의존성 최소 조건은 24.15.0입니다.
이 문서는 macOS에서 검증한 24.21.0으로 맞추는 절차입니다.
TypeScript 7은 현재 typescript-eslint 지원 범위 `>=4.8.4 <6.1.0` 밖이며,
Vue 도구에 필요한 기존 TypeScript 컴파일러 API도 호환되지 않습니다.
ECharts 6.1.0, Nuxt UI 4.11.3, Tailwind 4.3.3, ExcelJS 4.4.0과
Nuxt 4.5.2는 이번 작업에서 유지했습니다.

## 2. 시작 전 확인

아래 명령은 Windows PowerShell에서 실행합니다.
`Set-Location`에는 실제 저장소 경로를 입력합니다.

```powershell
Set-Location 'C:\실제경로\skewnono_v3_nuxt'
git status -sb
git rev-parse HEAD
node --version
npm.cmd --version
where.exe node
where.exe npm
npm.cmd ls -g --depth=0
```

- 현재 Git 커밋과 Node 버전, 필요한 전역 CLI 버전을 기록합니다.
- 로컬 변경이 있다면 작업 내용을 먼저 보존합니다. 아래 업데이트를 그대로 진행하지 않습니다.
- 실행 중인 이 저장소의 Nuxt 개발 서버를 해당 터미널에서 `Ctrl+C`로 종료합니다.
- npm 설치·빌드와 다른 에이전트의 의존성 변경을 동시에 실행하지 않습니다.
- 회사의 기존 `.npmrc`, 프록시, 인증서, 레지스트리 설정은 유지합니다.

## 3. Node 24.21.0 설치

### 공식 설치 프로그램을 사용하는 PC

[Node 공식 다운로드](https://nodejs.org/en/download)에서 Windows와 PC 아키텍처에
맞는 24.21.0 LTS 배포 파일을 선택합니다.
일반적인 x64 Windows의 공식 설치 파일은
[node-v24.21.0-x64.msi](https://nodejs.org/dist/v24.21.0/node-v24.21.0-x64.msi)입니다.
회사에서 허용한 설치·관리자 권한 절차로 설치합니다.
기존 버전 관리 도구를 사용하는 PC에는 MSI를 추가로 설치하지 않습니다.

설치 후 PowerShell과 IDE 터미널을 다시 엽니다.
IDE가 옛 PATH를 유지한다면 IDE도 다시 실행합니다.

```powershell
node --version
npm.cmd --version
where.exe node
node -p "process.execPath"
```

`node --version`은 `v24.21.0`이어야 합니다.
공식 배포에 포함된 npm은 11.19.0입니다.
프로젝트의 `packageManager` 표기는 현재 `npm@11.9.0`이며,
이번 macOS 검증은 Node에 포함된 npm 11.19.0에서 수행했습니다.
별도로 npm을 최신 버전으로 올리는 작업은 필요하지 않습니다.

### 기존 Node 버전 관리 도구를 사용하는 PC

해당 도구의 설치·전환 방법으로 24.21.0을 선택한 뒤 위 명령으로 확인합니다.
Windows의 NVM for Windows는 macOS/Linux의 nvm과 다른 도구입니다.
macOS용 `source nvm.sh`, `nvm alias default` 명령은 PowerShell에서 사용하지 않습니다.
설치된 NVM 버전에 맞는 [공식 안내](https://github.com/nvm-windows/nvm)를 확인합니다.

Node 전환 후 필요한 전역 CLI가 사라졌다면 2장에서 기록한 이름과 버전으로
다시 설치합니다. 프로젝트의 ESLint·TypeScript는 전역 설치하지 않습니다.

## 4. 코드와 의존성 적용

저장소 루트에서 실행합니다. `git pull`이 충돌하거나 실패하면 먼저 원인을 해결합니다.
오류 상태에서 뒤의 명령을 계속 실행하지 않습니다.

```powershell
git pull --ff-only
git merge-base --is-ancestor 03ff0e9e HEAD
```

두 번째 명령의 종료 코드가 0이면 이번 업데이트가 포함되어 있습니다.
PowerShell에서 직후 `$LASTEXITCODE`로 확인할 수 있습니다.

```powershell
Set-Location frontend
npm.cmd ci
npm.cmd ls eslint @nuxt/eslint vue-tsc typescript --depth=0
```

목표 네 버전이 1장의 표와 같아야 합니다.
이후 다른 의존성 업데이트가 반영된 커밋이라면 현재 lockfile과 그 변경의 검증 기록을
먼저 확인합니다. 과거 목표 버전을 맞추려고 lockfile을 임의로 되돌리지 않습니다.

`npm ci`는 기존 `node_modules`를 제거하고 다시 설치하며,
`package.json`이나 lockfile을 수정하지 않습니다.
설치 후 `nuxt prepare`가 실행되어 `.nuxt` 타입을 생성합니다.
`--omit=dev`나 `--ignore-scripts`를 추가하면 이번 검사 도구 또는 생성 단계가
빠질 수 있으므로 이 절차에서는 사용하지 않습니다.

macOS의 `node_modules`를 Windows로 복사하지 않습니다.
네이티브 모듈과 OS별 선택 의존성을 Windows에서 새로 설치해야 합니다.

## 5. 검증과 개발 서버 재시작

`frontend`에서 아래 명령을 하나씩 실행합니다.
각 명령 직후 `$LASTEXITCODE`가 0인지 확인하고 실패하면 다음 단계로 넘어가지 않습니다.

```powershell
npm.cmd run typecheck
npm.cmd run lint
npm.cmd test
npm.cmd run build
```

macOS 검증 결과는 타입 검사 통과, lint 오류 0건, 테스트 2,176건 통과,
SPA 빌드 성공입니다. 기존 `ImageViewer.vue`의 `eqp_ip`·`class_name`
camelCase 경고 2건은 남아 있습니다.
테스트 수는 이후 코드 변경에 따라 달라질 수 있습니다.
CI는 프론트엔드 typecheck와 test만 실행하므로 lint와 build를 현장에서 따로 실행합니다.

새 PowerShell에서 확인한 Node 경로로 개발 서버를 다시 시작합니다.
기존 프로세스는 Node를 설치해도 자동으로 새 버전으로 전환되지 않습니다.

```powershell
npm.cmd run dev
```

기존 사무실 API 프록시 설정을 유지합니다.
`NUXT_API_TARGET`은 실제 Flask 시작 로그의 주소·포트와 맞아야 합니다.
사무실 기본 구성의 5000과 집 구성의 5050을 혼동하지 않습니다.
이 도구 업데이트 때문에 `providers/office.py`, `data.py` 또는 Python 패키지를
바꾸거나 office 어댑터를 다시 복사할 필요는 없습니다.
다만 같은 pull에 다른 커밋이 함께 들어왔다면 Flask 시작 로그의 `STALE office.py`를
확인하고 해당 어댑터의 변경 안내를 따릅니다.

브라우저에서는 다음을 확인합니다.

- `/mag-pixel`에서 입력값 변경 시 결과와 미리보기가 갱신되는지 확인합니다.
- `/ebeam/cd-sem/<실제 FAB 경로>/tttm`에서 레시피·장비 선택과 사내 데이터 요청을 확인합니다.
- 평소 사용하는 차트에서 툴팁·확대/축소·PNG 저장, 모달·선택 메뉴를 확인합니다.
- 브라우저 콘솔 오류와 API 응답 실패를 확인합니다.

macOS에서는 위 두 페이지의 렌더링과 Mag/Pixel 입력 변경만 mock 데이터로 확인했습니다.
사내 데이터 요청·전체 차트 조작·Windows 화면 검증은 이 현장 단계에서 수행합니다.
클라우드에 반영할 경우 빌드 성공 후 [배포 가이드](deployment.md)를 따릅니다.
클라우드 Flask 호스트에는 이 프론트엔드 도구 업데이트만을 위해 Node를 설치하지 않습니다.

## 6. 자주 만나는 문제

| 증상 | 확인·조치 |
| --- | --- |
| `npm.ps1` 실행 정책 오류 | 이 문서처럼 `npm.cmd`를 사용합니다. 실행 정책을 전역으로 완화하지 않습니다 |
| `EBADENGINE` | `node --version`, `where.exe node`, `process.execPath`를 확인하고 옛 Node PATH를 해결합니다 |
| `EPERM`, `EBUSY` | 이 저장소의 dev 서버·설치 프로세스를 종료하고 파일 점유 원인을 확인한 뒤 재시도합니다 |
| 프록시·인증서·다운로드 실패 | 회사 레지스트리·프록시·인증서를 확인합니다. `strict-ssl=false`로 우회하지 않습니다 |
| package.json과 lock 불일치 | 두 파일을 같은 Git 커밋에서 받았는지 확인합니다. lock을 지우거나 `--legacy-peer-deps`로 우회하지 않습니다 |
| 새 lint 오류 | 업데이트가 주석 이동 두 건까지 포함됐는지 확인하고 실제 오류를 수정합니다. 규칙을 끄지 않습니다 |
| `install-scripts`·`allowScripts` 경고 | macOS npm 11.19.0에서는 경고가 있어도 설치·검사가 통과했습니다. 종료 코드와 실제 검사를 확인하고 필요한 스크립트만 검토합니다 |

macOS 설치에서 npm audit 결과 19건이 업데이트 전후 동일했습니다.
이는 취약점이 없다는 의미가 아닙니다. 기존 취약점의 상세 분석·수정은 별도 작업입니다.
`npm audit fix --force`는 이번에 검증한 조합을 바꿀 수 있으므로 적용 절차에 포함하지 않습니다.

## 7. 실패 시 복구

오류 메시지와 실제 Node·패키지 버전을 먼저 기록합니다.
설치가 중간에 실패했다면 Node 경로·네트워크·파일 점유 원인을 해결한 뒤
같은 커밋에서 `npm.cmd ci`를 다시 실행합니다.

코드 회귀로 이전 버전 확인이 필요하다면 현재 작업 파일을 덮어쓰지 않고
별도 checkout/worktree에서 2장에 기록한 이전 커밋을 검증합니다.
별도 checkout에는 gitignore된 `office.py`와 `.env`가 따라오지 않으므로
프론트엔드 타입 검사·lint·테스트·빌드 비교에 사용합니다. 사내 데이터 회귀는
회사 설정을 확인한 별도 환경에서 검증합니다.
이전 커밋의 `package.json`과 lockfile을 함께 사용하고 `npm.cmd ci`를 실행합니다.
Node 자체를 되돌려야 한다면 기존 설치 방식으로 기록한 버전으로 복구합니다.
복구 후에도 터미널·개발 서버를 다시 시작하고 타입 검사·lint·테스트·빌드를 수행합니다.

## 참고 자료

- [Node 24.21.0 공식 배포 목록](https://nodejs.org/dist/v24.21.0/)
- [npm ci 공식 문서](https://docs.npmjs.com/cli/v11/commands/npm-ci/)
- [typescript-eslint 지원 버전](https://typescript-eslint.io/users/dependency-versions/)
- [TypeScript 7과 Vue 도구의 API 제약](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)
