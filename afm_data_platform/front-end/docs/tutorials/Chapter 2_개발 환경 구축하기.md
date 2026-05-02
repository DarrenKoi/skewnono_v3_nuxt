# Node.js 설치 및 Vue 개발 환경 구축

## Node.js란 무엇인가?

Node.js는 Chrome V8 JavaScript 엔진으로 빌드된 JavaScript 런타임입니다. 쉽게 말해, **JavaScript를 브라우저 밖에서도 실행할 수 있게 해주는 프로그램**입니다. Vue 개발을 위해서는 Node.js가 필수적으로 필요합니다.

### 집 건축으로 이해하는 Node.js

- **브라우저**: 완성된 집 (사용자가 사는 공간)
- **Node.js**: 건축 현장 (개발자가 작업하는 공간)
- **JavaScript**: 건축 도구 (양쪽에서 모두 사용 가능)

### Node.js가 Vue 개발에 필요한 이유

| 기능                           | 설명                                   | 비유               |
| ------------------------------ | -------------------------------------- | ------------------ |
| **npm (Node Package Manager)** | Vue와 관련된 패키지들을 설치하고 관리  | 마트에서 재료 구매 |
| **개발 서버 실행**             | 로컬에서 Vue 애플리케이션을 테스트     | 요리 시식          |
| **빌드 도구 실행**             | 개발한 코드를 배포 가능한 형태로 변환  | 포장해서 배달      |
| **개발 도구 지원**             | 코드 검사, 자동 완성 등 개발 편의 기능 | 요리 도구와 레시피 |

간단히 말하면: Node.js 없이는 Vue 개발이 불가능합니다!

## Node.js 설치하기

### Windows에서 설치하기

#### 1. Node.js 공식 웹사이트 접속

- [https://nodejs.org/](https://nodejs.org/) 접속
- **LTS(Long Term Support)** 버전 다운로드 (안정성 보장)
- **2025년 6월 현재 권장**: Node.js 20.x LTS

#### 2. 설치 프로그램 실행

- 다운로드한 `.msi` 파일 실행
- 설치 마법사 안내에 따라 진행
- **중요**: "Add to PATH" 옵션 체크 확인

#### 3. 설치 옵션 선택

- 기본 설정으로 진행 권장
- 설치 경로: `C:\Program Files\nodejs` (기본값 사용)
- "Automatically install the necessary tools" → 체크 해제 가능

**MacOS, Linux 사용자도 Node.js 공식 사이트에서 설치 방법을 찾을 수 있습니다.**

## Node.js 설치 확인

설치가 완료되면 터미널을 열어 다음 명령어로 설치를 확인합니다.

### 터미널 열기

운영체제별 터미널 실행 방법:

- **Windows**: `Win + R` → `cmd` 또는 `powershell` 입력
- **macOS**: `Cmd + Space` → `터미널` 검색
- **Linux**: `Ctrl + Alt + T`

### 설치 확인 명령어

터미널에서 다음 명령어들을 순서대로 실행하세요:

```bash
# Node.js 버전 확인
node -v
# 출력 예시: v20.14.0

# npm 버전 확인
npm -v
# 출력 예시: 10.7.0
```

### 설치 확인 결과

- **성공**: 두 명령어 모두 버전 번호가 출력되면 설치 완료
- **참고**: 표시된 버전 번호와 다를 수 있지만 정상입니다
- **실패**: 명령어를 찾을 수 없다는 오류가 나오면 설치를 다시 확인해주세요

## SK hynix 내부 네트워크 설정

### npm 프록시 서버 설정

SK hynix 내부 네트워크에서 npm 패키지를 설치하려면 다음 설정이 필요합니다:

```bash
# npm 레지스트리를 회사 내부 프록시 서버로 변경
npm config set registry http://nexus.skhynix.com:8181/repository/npm-proxy/

# npm 타임아웃 설정 (네트워크 안정성 향상)
npm config set fetch-retry-maxtimeout 600000 -g
```

### 설정 효과

위 설정을 완료하면:

- 회사 내부 프록시 서버를 통해 npm 패키지 다운로드 가능
- 네트워크 타임아웃 시간이 늘어나 안정적인 패키지 설치
- `npm install [패키지명]` 명령어 사용 가능

### 설정 확인

설정이 올바르게 적용되었는지 확인하려면:

```bash
# 현재 npm 레지스트리 확인
npm config get registry
# 출력 예시: http://nexus.skhynix.com:8181/repository/npm-proxy/

# 타임아웃 설정 확인
npm config get fetch-retry-maxtimeout
# 출력 예시: 600000
```

### 주의사항

- 이 설정은 SK hynix 내부 네트워크에서만 필요합니다
- 외부 네트워크에서 작업할 때는 원래 설정으로 되돌려야 할 수 있습니다
- 설정 변경 후 터미널을 다시 시작하는 것을 권장합니다

## 첫 번째 Vue 프로젝트 생성하기

### Vite를 사용한 Vue 프로젝트 생성

#### Vite란?

- **차세대 프론트엔드 빌드 도구**
- **초고속 개발 서버** (1-3초 내 시작)
- **최적화된 빌드** 제공
- **Vue 3 공식 추천 도구**

#### 단계별 프로젝트 생성

```bash
# 1. 프로젝트 생성
npm create vue@latest

# 2. 옵션 선택 (대화형 메뉴가 나타남)
# Framework: Vue
# Variant: JavaScript (또는 TypeScript)

# 3. 프로젝트 디렉토리로 이동
cd 프로젝트 디렉토리

# 4. 의존성 패키지 설치
npm install

# 5. 개발 서버 실행
npm run dev
```

#### 실습해보기

1. 위 명령어들을 순서대로 실행
2. 브라우저에서 `http://localhost:5173` 접속
3. Vue 로고가 보이면 성공!

### 기본 npm 명령어 이해하기

| 명령어          | 기능              | 언제 사용?                |
| --------------- | ----------------- | ------------------------- |
| `npm install`   | 패키지 설치       | 프로젝트 처음 다운로드 시 |
| `npm run dev`   | 개발 서버 시작    | 개발 중                   |
| `npm run build` | 프로덕션 빌드     | 배포 전                   |
| `npm run lint`  | 코드 검사 및 정리 | 코드 품질 관리            |

## 프로젝트 구조 이해하기

생성된 Vue 프로젝트의 구조를 **아파트 건물**에 비유해서 이해해보겠습니다:

```text
my-vue-app/
├── 📁 node_modules/      # 상가 (외부에서 가져온 도구들)
├── 📁 public/           # 로비 (모든 사람이 볼 수 있는 공간)
│   ├── 🖼️ favicon.ico   # 건물 표지판
│   └── 📄 index.html    # 메인 입구
├── 📁 src/              # 실제 거주 공간 (우리가 작업하는 곳)
│   ├── 📁 assets/       # 장식품 보관함 (이미지, 스타일)
│   ├── 📁 components/   # 가구 조립 부품 (재사용 가능한 UI)
│   ├── 📄 App.vue       # 메인 거실 (중심 컴포넌트)
│   └── 📄 main.js       # 전기 메인 스위치 (앱 시작점)
├── 📄 .gitignore        # 비밀 서류함 (Git에서 제외할 파일)
├── 📄 package.json      # 건물 설계도 (프로젝트 설정)
├── 📄 README.md         # 사용 설명서
└── 📄 vite.config.js    # 건물 시설 설정 (빌드 도구 설정)
```

### 각 폴더의 역할

#### src/ - 우리가 주로 작업하는 공간

- **`main.js`**: 애플리케이션의 시작점
- **`App.vue`**: 메인 컴포넌트 (모든 페이지의 틀)
- **`components/`**: 재사용 가능한 UI 조각들
- **`assets/`**: 이미지, 아이콘, 스타일 파일

#### public/ - 정적 파일들

- **`index.html`**: 기본 HTML 템플릿
- **`favicon.ico`**: 브라우저 탭 아이콘

## VS Code 개발 환경 설정하기

### 필수 VS Code 확장 프로그램

Vue 개발을 위한 필수 확장 프로그램들을 **도구상자**에 비유해서 설명하겠습니다:

#### 핵심 도구

| 확장 프로그램           | 기능                         | 필수도     |
| ----------------------- | ---------------------------- | ---------- |
| **Vue - Official**      | Vue 3 공식 지원 (이전 Volar) | ⭐⭐⭐⭐⭐ |
| **Vue VSCode Snippets** | Vue 코드 자동 완성           | ⭐⭐⭐⭐   |
| **ESLint**              | JavaScript 코드 품질 검사    | ⭐⭐⭐⭐   |
| **Prettier**            | 코드 자동 포맷팅             | ⭐⭐⭐⭐   |

#### 편의 도구

| 확장 프로그램         | 기능                | 추천도 |
| --------------------- | ------------------- | ------ |
| **Auto Rename Tag**   | HTML 태그 자동 수정 | ⭐⭐⭐ |
| **Path Intellisense** | 파일 경로 자동 완성 | ⭐⭐⭐ |
| **GitLens**           | Git 기록 시각화     | ⭐⭐   |

### 스니펫 활용하기

Vue 파일에서 다음 단축키들을 사용해보세요:

```vue
<!-- 'vbase' 입력 후 Tab -->
<template>
  <div></div>
</template>

<script setup></script>

<style scoped></style>
```

### VS Code에서 Vue 개발 팁

#### 파일 트리 구성

```text
프로젝트/
├── 📁 .vscode/          # VS Code 설정
│   └── settings.json    # 프로젝트별 설정
├── 📁 src/
│   └── 📄 *.vue        # Vue 컴포넌트
```

#### 유용한 단축키

- `Ctrl/Cmd + P`: 빠른 파일 열기
- `Ctrl/Cmd + Shift + P`: 명령 팔레트
- `Alt + Shift + F`: 코드 포맷팅
- `F2`: 변수/함수명 일괄 변경

## 개발 서버 실행 및 확인

모든 설정이 완료되면 개발 서버를 실행하여 정상 작동을 확인합니다:

### 개발 서버 시작하기

```bash
# 개발 서버 실행
npm run dev

# 출력 예시:
#   VITE v4.4.5  ready in 589 ms
#   ➜  Local:   http://localhost:5173/
#   ➜  Network: use --host to expose
```

### 브라우저에서 확인하기

1. **URL 접속**: `http://localhost:5173` 클릭 또는 직접 입력
2. **성공 확인**: Vue 로고와 "Hello Vue 3 + Vite" 메시지 표시
3. **Hot Reload 테스트**: 코드 수정 시 자동 반영 확인

네트워크에서 접근하려면:

```bash
# 네트워크 접근 허용
npm run dev -- --host 0.0.0.0

# 출력 예시:
#   ➜  Local:   http://localhost:5173/
#   ➜  Network: http://192.168.1.100:5173/
```

### 일반적인 문제 해결

#### 포트 5173이 이미 사용 중

```bash
# 다른 포트 사용
npm run dev -- --port 3000
```

#### 브라우저가 자동으로 열리지 않음

```bash
# 브라우저 자동 열기
npm run dev -- --open
```

#### 파일 변경이 반영되지 않음

```bash
# 서버 재시작
Ctrl + C (서버 종료)
npm run dev (재시작)
```

### 성공! 다음 단계는?

- ✅ Node.js 설치 완료
- ✅ Vue 프로젝트 생성 완료
- ✅ VS Code 환경 설정 완료
- ✅ 개발 서버 실행 완료

이제 Chapter 3에서 Vue 프로젝트의 구조와 첫 번째 컴포넌트를 만들어보겠습니다!

---

## 읽을 거리: Vite란 무엇인가?

### Vite의 정의와 개념

Vite(비트, 프랑스어로 "빠르다"는 뜻)는 Evan You(Vue.js 창시자)가 개발한 차세대 프론트엔드 빌드 도구입니다. 기존의 Webpack 기반 도구들보다 훨씬 빠른 개발 서버와 빌드 성능을 제공하며, 현대적인 JavaScript 생태계에 최적화되어 있습니다. Vite는 Vue에서 처음 개발되었지만, Vue뿐만 아니라 React, Svelte, Preact, SolidJS 등 다양한 프레임워크와 라이브러리에서 사용 가능한 범용적인 빌드 도구로 자리 잡고 있습니다.

Vite를 이해하기 위해 요리에 비유해보겠습니다. 전통적인 빌드 도구(Webpack)가 모든 재료를 미리 준비해서 완성된 요리를 만드는 것과 같다면, Vite는 주문이 들어올 때마다 필요한 재료만 빠르게 조리해서 제공하는 방식입니다. 이로 인해 개발 중에는 훨씬 빠른 반응속도를 얻을 수 있습니다.

Webpack은 대규모 프로젝트에서 여전히 표준으로 사용되고 있지만, Vite는 속도와 단순성 덕분에 신규 및 중소규모 프로젝트에서 점유율이 빠르게 증가하며 Webpack을 추월하는 추세에 있습니다.

### Vite의 핵심 아키텍처

Vite는 두 가지 주요 단계로 작동합니다:

#### 개발 단계 (Development)

- **ES Modules 활용**: 브라우저의 네이티브 ES 모듈 기능을 직접 사용
- **esbuild 기반 변환**: Go 언어로 작성된 초고속 JavaScript 번들러 사용
- **온디맨드 컴파일**: 요청된 파일만 실시간으로 변환

\*네이티브 ES 모듈: JavaScript의 표준 모듈 시스템으로, import와 export 구문을 사용해 코드를 모듈화하고 재사용 가능하게 만드는 기능

#### 빌드 단계 (Production)

- **Rollup 기반 번들링**: 성숙하고 안정적인 Rollup을 사용하여 최적화된 번들 생성
- **트리 쉐이킹**: 사용하지 않는 코드 자동 제거
- **코드 스플리팅**: 효율적인 청크 분할로 로딩 성능 최적화

\*Rollup: JavaScript 코드를 번들링하여 ES 모듈을 효율적으로 결합하고 최적화된 단일 파일로 출력하는 모듈 번들러

## 왜 Vue는 Vite를 선택했는가?

### Vue 생태계의 발전 과정

Vue.js는 프레임워크의 발전과 함께 빌드 도구도 함께 진화시켜왔습니다:

- **Vue 1.x 시대**: 단순한 script 태그로 사용
- **Vue 2.x 시대**: Vue CLI와 Webpack 조합으로 본격적인 SPA 개발 지원
- **Vue 3.x 시대**: Vite를 기본 빌드 도구로 채택하여 개발 경험 혁신

### Vue가 Vite를 선택한 이유

#### 1. 개발 서버 시작 속도 혁신

```bash
# Webpack 기반 Vue CLI
npm run serve # 20-30초 소요

# Vite 기반 Vue 프로젝트
npm run dev # 1-3초 소요
```

큰 프로젝트에서는 이 차이가 더욱 극명해집니다. Webpack은 모든 모듈을 미리 번들링하는 반면, Vite는 필요한 모듈만 실시간으로 처리하기 때문입니다.

#### 2. 핫 모듈 교체(HMR) 성능

- Webpack: 프로젝트 크기에 따라 HMR 속도가 느려짐
- Vite: 프로젝트 크기와 무관하게 일정한 HMR 속도 유지

#### 3. Vue 3 최적화

- Composition API와의 완벽한 호환성
- Single File Components (.vue) 완벽 지원
- TypeScript 지원

## Vite의 주요 장점

### 성능상의 이점

#### 개발 서버 시작 시간

프로젝트 규모별 비교 (평균)

**작은 프로젝트 (~50 컴포넌트):**

- Webpack: 15초
- Vite: 1초

**중간 프로젝트 (~200 컴포넌트):**

- Webpack: 30초
- Vite: 1.5초

**대형 프로젝트 (~500+ 컴포넌트):**

- Webpack: 60초+
- Vite: 2초

#### 핫 모듈 교체 속도

- Webpack: 파일 수정 후 500ms~2초
- Vite: 파일 수정 후 50ms~200ms

### 개발 경험상의 이점

#### 1. 즉시 시작

개발 서버가 거의 즉시 시작되므로 개발 리듬이 끊어지지 않습니다. 특히 많은 컴포넌트를 가진 대시보드 애플리케이션에서 이 장점이 두드러집니다.

#### 2. 실시간 피드백

코드를 수정하면 브라우저에서 거의 즉시 결과를 확인할 수 있어 시행착오를 통한 학습이 훨씬 효율적입니다.

#### 3. 간단한 설정

Webpack의 복잡한 설정 파일 대신 직관적인 `vite.config.js` 파일로 대부분의 설정을 해결할 수 있습니다.

## Vite의 역할과 작동 원리

### 개발 단계에서의 역할

#### 1. 개발 서버 제공

```text
// Vite 개발 서버 실행 과정
npm run dev
↓
vite 명령어 실행
↓
로컬 서버 시작 (기본: http://localhost:5173)
↓
브라우저에서 index.html 요청
↓
필요한 .vue 파일들을 실시간으로 변환하여 제공
```

#### 2. 모듈 변환

```vue
<!-- HelloWorld.vue 파일 -->
<template>
  <div>{{ message }}</div>
</template>

<script>
export default {
  data() {
    return {
      message: "Hello from Vite!",
    };
  },
};
</script>

<style scoped>
div {
  color: blue;
}
</style>
```

Vite는 이 .vue 파일을 브라우저가 이해할 수 있는 JavaScript 모듈로 실시간 변환합니다.

#### 3. 의존성 사전 번들링

```json
// package.json의 dependencies
{
  "vue": "^3.3.0",
  "vuetify": "^3.4.0",
  "echarts": "^5.4.0"
}
```

Vite는 node_modules의 의존성들을 esbuild로 사전 번들링하여 브라우저에서 효율적으로 로드할 수 있도록 합니다.

### 빌드 단계에서의 역할

#### 1. 프로덕션 최적화

```text
npm run build
↓
Rollup으로 모든 파일 번들링
↓
코드 압축 및 최적화
↓
dist/ 폴더에 배포용 파일 생성
```

#### 2. 코드 스플리팅

```javascript
// 자동 코드 스플리팅 예시
const Dashboard = () => import("./components/Dashboard.vue");
const Analytics = () => import("./components/Analytics.vue");

// 각 컴포넌트는 별도 청크로 분리되어 필요할 때만 로드
```

## Webpack과의 비교

### 아키텍처 차이점

#### Webpack 방식

```text
개발 서버 시작
↓
모든 모듈 스캔
↓
전체 의존성 그래프 생성
↓
모든 파일 번들링
↓
메모리에 결과 저장
↓
서버 시작 완료 (20-60초)
```

#### Vite 방식

```text
개발 서버 시작
↓
index.html만 준비
↓
서버 즉시 시작 (1-3초)
↓
브라우저 요청 시 필요한 모듈만 실시간 변환
```

### 실제 사용 시나리오 비교

시나리오: 200개 컴포넌트를 가진 대시보드 프로젝트

#### Webpack 기반 개발

1. 프로젝트 시작: 30초 대기
2. 컴포넌트 수정: 1-2초 후 반영
3. 새 컴포넌트 추가: 전체 재빌드 필요

#### Vite 기반 개발

1. 프로젝트 시작: 1-2초
2. 컴포넌트 수정: 100ms 내 반영
3. 새 컴포넌트 추가: 즉시 사용 가능

## Vite 설정과 커스터마이징

### 기본 vite.config.js 구조

```javascript
// vite.config.js
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  // 플러그인 설정
  plugins: [
    vue(), // Vue SFC 지원
  ],

  // 경로 별칭 설정
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },

  // 개발 서버 설정
  server: {
    port: 3000, // 포트 변경
    open: true, // 자동 브라우저 열기
    host: true, // 네트워크 접근 허용
  },

  // 빌드 설정
  build: {
    outDir: "dist", // 빌드 출력 디렉토리
    sourcemap: true, // 소스맵 생성
    minify: "terser", // 압축 도구
  },

  // 환경 변수 설정
  define: {
    "process.env": {},
  },
});
```

## Rollup 이해하기

### Rollup이란 무엇인가?

Rollup은 JavaScript 모듈 번들러로, 작은 코드 조각들을 하나 또는 여러 개의 큰 파일로 결합하는 도구입니다. Vite가 개발 단계에서는 esbuild를 사용하다가 프로덕션 빌드 시에는 Rollup으로 전환하는 이유를 이해하기 위해 Rollup의 특성을 깊이 있게 살펴보겠습니다.

음식점에서 요리를 비유로 설명하면, Rollup은 마치 고급 레스토랑의 셰프가 각각의 재료들을 정교하게 조합하여 완벽한 요리를 만드는 과정과 같습니다. 개발 단계에서는 빠른 패스트푸드 방식(esbuild)으로 즉석에서 서빙하지만, 최종 제품은 정교한 방법으로 완성도 높은 결과물을 만들어냅니다.

### Rollup의 핵심 철학과 특징

#### ES 모듈 우선주의

먼저 ES는 ECMAScript의 약자로, JavaScript의 표준 스크립팅 언어 사양을 정의하는 국제 표준을 의미합니다. Rollup은 처음부터 ES 모듈(ES6 modules)을 기본으로 설계되었습니다. 이는 `import`와 `export` 문법을 네이티브하게 지원한다는 의미입니다. 다른 번들러들이 CommonJS나 AMD 같은 이전 모듈 시스템도 지원하느라 복잡해진 반면, Rollup은 ES 모듈에 집중함으로써 더 효율적이고 예측 가능한 번들링을 제공합니다.

```javascript
// ES 모듈 방식 - Rollup이 최적화하는 형태
import { createApp } from "vue";
import { createRouter } from "vue-router";
import Dashboard from "./components/Dashboard.vue";

export { Dashboard };
export default createApp;
```

#### 라이브러리 개발에 최적화

Rollup은 원래 라이브러리와 패키지 개발을 위해 만들어졌습니다. 이는 Vue.js, React, D3.js 같은 유명한 라이브러리들이 모두 Rollup으로 빌드되는 이유이기도 합니다. 라이브러리는 다양한 환경에서 사용되어야 하므로, 깔끔하고 예측 가능한 출력이 중요한데 Rollup이 이런 요구사항을 잘 만족시킵니다.

### Rollup vs Webpack 비교 분석

이 두 도구의 차이점을 이해하면 Vite가 왜 상황에 따라 다른 도구를 선택하는지 알 수 있습니다.

#### 설계 철학의 차이

Webpack은 "모든 것이 모듈이다"라는 철학으로 JavaScript뿐만 아니라 CSS, 이미지, 폰트 등 모든 자원을 모듈로 취급합니다. 이는 매우 강력하지만 복잡성을 증가시킵니다. 반면 Rollup은 "JavaScript 모듈을 효율적으로 번들링하자"에 집중합니다. 이런 차이로 인해 Rollup은 더 작고 깔끔한 번들을 생성하는 경향이 있습니다.

#### 트리 쉐이킹 성능

트리 쉐이킹이란 사용하지 않는 코드를 자동으로 제거하는 기능입니다. 예를 들어 라이브러리에서 몇 개의 함수만 사용한다면, 나머지 불필요한 함수들은 최종 번들에 포함시키지 않습니다.

Rollup은 ES 모듈의 정적 구조를 활용하여 Webpack보다 더 정확하고 효율적인 트리 쉐이킹을 수행합니다. 이는 특히 대시보드 애플리케이션에서 중요한데, ECharts같은 큰 라이브러리에서 실제로 사용하는 차트 타입만 포함시켜 번들 크기를 크게 줄일 수 있습니다.

### Vite에서 Rollup이 하는 구체적인 역할

#### 개발 vs 프로덕션의 이중 전략

Vite는 개발 단계와 프로덕션 빌드에서 다른 도구를 사용하는 영리한 전략을 취합니다. 개발할 때는 속도가 가장 중요하므로 Go 언어로 작성된 초고속 esbuild를 사용합니다. 하지만 프로덕션에서는 안정성과 최적화가 더 중요하므로 성숙하고 검증된 Rollup을 사용합니다.

##### 개발 단계

```text
npm run dev
→ esbuild 사용 (속도 우선)
→ 1-3초 내 서버 시작
→ 실시간 모듈 변환
```

##### 프로덕션 빌드

```text
npm run build
→ Rollup 사용 (최적화 우선)
→ 트리 쉐이킹, 코드 스플리팅
→ 압축 및 최적화된 번들 생성
```

#### 플러그인 생태계 활용

Rollup은 풍부한 플러그인 생태계를 가지고 있으며, Vite는 이를 그대로 활용합니다. 예를 들어 TypeScript 변환, CSS 처리, 이미지 최적화 등 다양한 작업을 Rollup 플러그인을 통해 처리합니다.

```javascript
// vite.config.js에서 Rollup 플러그인 직접 사용 가능
import { defineConfig } from "vite";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig({
  plugins: [
    // Vite 플러그인
    vue(),
    // Rollup 플러그인도 바로 사용 가능
    visualizer({
      filename: "dist/stats.html",
      open: true,
    }),
  ],
});
```

### Rollup의 최적화 전략

#### 코드 스플리팅 구현

Rollup은 애플리케이션을 여러 개의 청크로 나누어 필요한 부분만 로드할 수 있게 합니다. 이는 특히 대시보드 애플리케이션에서 유용합니다.

```javascript
// 동적 import를 통한 코드 스플리팅
const routes = [
  {
    path: "/dashboard",
    component: () => import("./views/Dashboard.vue"), // 별도 청크로 분리
  },
  {
    path: "/analytics",
    component: () => import("./views/Analytics.vue"), // 별도 청크로 분리
  },
];

// Rollup이 자동으로 다음과 같이 청크를 생성:
// dashboard-hash.js
// analytics-hash.js
// vendor-hash.js (공통 라이브러리)
```

#### 번들 분석과 최적화

Rollup은 번들 구성을 세밀하게 제어할 수 있는 옵션들을 제공합니다.

```javascript
// rollup 설정 예시 (vite.config.js 내부)
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        // Vue 관련 라이브러리를 하나의 청크로
        vue: ['vue', 'vue-router', 'pinia'],

        // UI 라이브러리를 별도 청크로
        ui: ['vuetify'],

        // 차트 라이브러리를 별도 청크로
        charts: ['echarts'],

        // 유틸리티 함수들
        utils: ['lodash', 'date-fns']
      }
    }
  }
}
```

#### 실제 성능 개선 사례

```javascript
// 최적화 전: ECharts 전체를 import
import * as echarts from "echarts";
// 번들 크기: ~3MB

// 최적화 후: 필요한 차트만 import
import { init } from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

echarts.use([
  LineChart,
  BarChart,
  GridComponent,
  TooltipComponent,
  CanvasRenderer,
]);
// 번들 크기: ~800KB (약 75% 감소)
```
