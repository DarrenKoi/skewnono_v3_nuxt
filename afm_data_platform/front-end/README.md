# AFM 데이터 뷰어 (AFM Data Viewer)

ITC에서 개발한 AFM(Atomic Force Microscopy) 측정 데이터 검색 및 시각화 플랫폼입니다.

## 📂 프로젝트 구조

### `src/pages/`
페이지 컴포넌트들이 위치하며, 라우터에 수동으로 등록됩니다.

- **MainPage.vue**: 메인 검색 페이지 (`/` 경로)
  - AFM 로고 표시
  - 통합 검색바 (Fab ID, Lot ID, Tool ID, Recipe name 검색 가능)
  - 검색 기능 구현

### `src/layouts/`
레이아웃 관련 컴포넌트들이 위치합니다.

- **AppHeader.vue**: 상단 앱바
  - "AFM Data Viewer" 타이틀
  - 우측 네비게이션 링크들 (Home, About, Help, Contact)
  - 현재 링크들은 비활성화 상태 (href: null)

- **AppFooter.vue**: 하단 푸터
  - "© 2025 ITC AFM Data Platform" 표시

### `src/components/`
재사용 가능한 UI 컴포넌트들을 위한 폴더입니다.

- 현재는 비어있음
- 향후 차트, 버튼, 카드 등의 재사용 컴포넌트들이 추가될 예정

### `src/stores/`
Pinia 상태 관리 스토어들이 위치합니다.

- **app.js**: 기본 앱 스토어
- **index.js**: 스토어 설정 파일

### `src/plugins/`
Vue 플러그인 등록 파일들이 위치합니다.

- **index.js**: 플러그인 등록
- **vuetify.js**: Vuetify 설정

### `src/router/`
라우터 설정 파일이 위치합니다.

- **index.js**: 수동 라우터 설정
  - MainPage.vue → `/` 경로 매핑
  - 기존 자동 생성 라우팅에서 수동 설정으로 변경

### `src/assets/`
정적 자산 파일들이 위치합니다.

- **afm_logo2.png**: AFM 로고 이미지
- **favicon.png**: 파비콘
- **logo.png, logo.svg**: 기본 Vue 로고들

### `src/styles/`
SCSS 스타일 설정 파일들이 위치합니다.

- **settings.scss**: Vuetify 스타일 설정

## 🛠️ 기술 스택

- **Vue 3** (Composition API)
- **Vuetify 3** (Material Design)
- **Vue Router** (수동 설정)
- **Pinia** (상태 관리)
- **Vite** (빌드 도구)

## 🚀 개발 명령어

```bash
# 의존성 설치
npm install

# 개발 서버 시작 (http://localhost:3000)
npm run dev

# 프로덕션 빌드
npm run build

# 빌드 미리보기
npm run preview

# 린팅 (자동 수정)
npm run lint
```

## 📋 TODO 목록

1. **더미 AFM 측정 데이터 구조 생성** (Fab ID, Lot ID, Tool ID, Recipe name, 측정 결과 포함)
2. **검색 결과 페이지 생성** (데이터 시각화 컴포넌트 포함)
3. **검색 기록 추적 및 최근 검색 내역 표시**
4. **검색 페이지와 결과 페이지 간 라우팅 구현**
5. **반응형 디자인 추가**

## 📄 라이선스

© 2025 ITC AFM Data Platform
