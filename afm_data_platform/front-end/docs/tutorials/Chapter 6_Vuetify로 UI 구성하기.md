# Vuetify로 UI 구성하기

## Vuetify 소개 및 설치

### Vuetify란 무엇인가?

Vuetify는 Vue.js에 사용되는 인기 있는 UI 컴포넌트 라이브러리 중 하나입니다. Google의 Material Design 철학을 따르며, 이미 디자인된 아름다운 컴포넌트들을 제공하여 개발자가 디자인에 대한 고민 없이 전문적인 외관의 웹 애플리케이션을 만들 수 있도록 도와줍니다.

### Vuetify의 주요 특징

#### Material Design 기반

- Google의 Material Design 3.0 지침을 완벽하게 구현
- 일관된 디자인 언어로 직관적인 사용자 경험 제공

#### 풍부한 컴포넌트

- 80개 이상의 다양한 UI 컴포넌트 제공
- 버튼, 카드, 테이블, 차트, 네비게이션 등 대시보드에 필요한 모든 요소 포함

#### 반응형 디자인

- 데스크톱, 태블릿, 모바일에서 자동으로 최적화
- 12컬럼 그리드 시스템으로 유연한 레이아웃 구성

#### 테마 시스템

- 라이트/다크 모드 지원
- 컬러, 타이포그래피, 간격 등 쉬운 커스터마이징

#### 접근성 (Accessibility)

- WCAG 2.1 지침 준수
- 키보드 네비게이션, 스크린 리더 지원

### Vuetify 설치하기

설치 방법은 [Vuetify 공식 설치 가이드](https://vuetifyjs.com/en/getting-started/installation/)에서 확인할 수 있습니다.

#### 방법 1: 새 프로젝트를 Vuetify로 시작하기

```bash
npm create vuetify@latest
cd my-project
npm install
npm run dev
```

#### 방법 2: 기존 Vue 프로젝트에 Vuetify 추가하기

```bash
npm install vuetify
npm install -D vite-plugin-vuetify
npm install @mdi/font
npm install -D sass
```

#### main.js 파일 수정

```javascript
import { createApp } from "vue";
import { createVuetify } from "vuetify";
import * as components from "vuetify/components";
import * as directives from "vuetify/directives";
import "vuetify/styles";
import "@mdi/font/css/materialdesignicons.css";
import App from "./App.vue";

const vuetify = createVuetify({
  components,
  directives,
  theme: {
    defaultTheme: "light",
  },
});

const app = createApp(App);
app.use(vuetify);
app.mount("#app");
```

#### Vite 설정 파일 수정

```javascript
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import vuetify from "vite-plugin-vuetify";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [vue(), vuetify({ autoImport: true })],
  define: { "process.env": {} },
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
});
```

#### 설치 시 오류 해결

만약 위 설정 후 오류가 발생한다면, 다음 플러그인들을 추가로 설치해주세요:

```bash
npm install -D vite-plugin-vuetify
npm install -D @vitejs/plugin-vue
npm install -D @vue/tsconfig
```

#### 자주 발생하는 오류와 해결법

1. "Cannot resolve vuetify" 오류

   ```bash
   npm install vuetify
   ```

2. "vite-plugin-vuetify not found" 오류

   ```bash
   npm install -D vite-plugin-vuetify
   ```

3. Material Design Icons 관련 오류

   ```bash
   npm install @mdi/font
   ```

4. 개발 서버 재시작

   ```bash
   npm run dev
   ```

## Material Design 이해하기

### Material Design이란?

Material Design은 Google이 2014년에 발표한 디자인 시스템으로, 물리적 세계의 재료(Material)와 빛의 특성을 디지털 인터페이스에 적용한 디자인 철학입니다. 현실에서 종이와 잉크가 가지는 물리적 특성을 디지털 환경에서 시뮬레이션하여 사용자에게 직관적이고 자연스러운 경험을 제공합니다.

### Material Design의 핵심 원칙

#### 물리적 법칙 적용

- 그림자와 깊이를 통한 계층 구조 표현
- 애니메이션을 통한 자연스러운 움직임
- 실제 물리 법칙을 따르는 상호작용

#### 일관성 있는 디자인 언어

- 모든 플랫폼에서 동일한 디자인 규칙 적용
- 예측 가능한 사용자 경험 제공

#### 의미 있는 애니메이션

- 사용자의 주의를 올바른 곳으로 유도
- 앱의 상태 변화를 명확하게 전달

### Material Design 3.0의 새로운 특징

Material Design 3.0은 개인화와 접근성에 중점을 둡니다:

- 동적 색상: 사용자 배경화면에서 추출한 색상 팔레트
- 개선된 접근성: 더 높은 대비와 큰 터치 영역
- 유연한 컴포넌트: 다양한 브랜드 스타일에 맞춤화 가능

### 주요 디자인 요소

#### 색상 시스템

```css
.primary-color {
  color: #1976d2;
}
.secondary-color {
  color: #424242;
}
.accent-color {
  color: #82b1ff;
}
.error-color {
  color: #ff5252;
}
.warning-color {
  color: #ffc107;
}
.info-color {
  color: #2196f3;
}
.success-color {
  color: #4caf50;
}
```

#### 타이포그래피

```css
.text-h1 {
  font-size: 6rem;
}
.text-h2 {
  font-size: 3.75rem;
}
.text-h3 {
  font-size: 3rem;
}
.text-h4 {
  font-size: 2.125rem;
}
.text-h5 {
  font-size: 1.5rem;
}
.text-h6 {
  font-size: 1.25rem;
}
.text-subtitle-1 {
  font-size: 1rem;
}
.text-subtitle-2 {
  font-size: 0.875rem;
}
.text-body-1 {
  font-size: 1rem;
}
.text-body-2 {
  font-size: 0.875rem;
}
```

#### 간격 시스템

```css
.ma-1 {
  margin: 4px;
}
.ma-2 {
  margin: 8px;
}
.ma-3 {
  margin: 12px;
}
.ma-4 {
  margin: 16px;
}
.ma-5 {
  margin: 20px;
}
.pa-1 {
  padding: 4px;
}
.pa-2 {
  padding: 8px;
}
.pa-3 {
  padding: 12px;
}
.pa-4 {
  padding: 16px;
}
.pa-5 {
  padding: 20px;
}
```

## 레이아웃 시스템

### Vuetify 그리드 시스템

Vuetify는 CSS Flexbox를 기반으로 한 12컬럼 그리드 시스템을 제공합니다. 이 시스템을 통해 다양한 화면 크기에 대응하는 반응형 레이아웃을 쉽게 구성할 수 있습니다.

### 기본 그리드 구조

```javascript
<template>
  <v-container>
    <v-row>
      <v-col cols="12" md="6" lg="4">
        <!-- 내용 -->
      </v-col>
    </v-row>
  </v-container>
</template>
```

### 컨테이너 (Container)

- `v-container`: 콘텐츠를 중앙에 정렬하고 최대 너비를 제한
- `fluid` 속성: 전체 너비 사용

### 행 (Row)

- `v-row`: 컬럼들을 수평으로 배치하는 컨테이너
- `no-gutters` 속성: 컬럼 간 간격 제거

### 열 (Column)

- `v-col`: 그리드의 기본 단위
- `cols`: 모든 화면 크기에서의 컬럼 수 (1-12)
- `sm`, `md`, `lg`, `xl`: 반응형 브레이크포인트별 컬럼 수

### 반응형 브레이크포인트

| 브레이크포인트 | 디바이스      | 크기 범위       |
| -------------- | ------------- | --------------- |
| xs             | 모바일        | < 600px         |
| sm             | 태블릿        | 600px ~ 960px   |
| md             | 소형 데스크톱 | 960px ~ 1264px  |
| lg             | 대형 데스크톱 | 1264px ~ 1904px |
| xl             | 초대형 화면   | > 1904px        |

### 실제 대시보드 레이아웃 예제

```javascript
<template>
  <v-app>
    <v-app-bar app color="primary" dark>
      <v-app-bar-nav-icon @click="drawer = !drawer"></v-app-bar-nav-icon>
      <v-toolbar-title>AFM Data Viewer</v-toolbar-title>
      <v-spacer></v-spacer>
      <v-btn icon>
        <v-icon>mdi-account</v-icon>
      </v-btn>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer" app>
      <v-list>
        <v-list-item
          v-for="item in menuItems"
          :key="item.title"
          :to="item.route"
          link
        >
          <v-list-item-action>
            <v-icon>{{ item.icon }}</v-icon>
          </v-list-item-action>
          <v-list-item-content>
            <v-list-item-title>{{ item.title }}</v-list-item-title>
          </v-list-item-content>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>

    <v-main>
      <v-container fluid>
        <v-row class="mb-4">
          <v-col cols="12">
            <h1 class="text-h4 font-weight-bold">대시보드</h1>
            <p class="text-subtitle-1 text--secondary">
              AFM 장비 현황 및 데이터 분석
            </p>
          </v-col>
        </v-row>

        <v-row class="mb-4">
          <v-col
            cols="12"
            sm="6"
            md="3"
            v-for="stat in stats"
            :key="stat.title"
          >
            <v-card>
              <v-card-text>
                <div class="d-flex align-center">
                  <v-icon :color="stat.color" large class="mr-3">
                    {{ stat.icon }}
                  </v-icon>
                  <div>
                    <h3 class="text-h5 font-weight-bold">{{ stat.value }}</h3>
                    <p class="text-caption text--secondary mb-0">
                      {{ stat.title }}
                    </p>
                  </div>
                </div>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>

        <v-row>
          <v-col cols="12" md="8">
            <v-card>
              <v-card-title>데이터 트렌드</v-card-title>
              <v-card-text>
                <div
                  style="height: 300px; background-color: #f5f5f5;
                           display: flex; align-items: center; justify-content: center;"
                >
                  차트 영역
                </div>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card>
              <v-card-title>최근 활동</v-card-title>
              <v-card-text>
                <v-list dense>
                  <v-list-item
                    v-for="activity in activities"
                    :key="activity.id"
                  >
                    <v-list-item-avatar>
                      <v-icon :color="activity.color">{{
                        activity.icon
                      }}</v-icon>
                    </v-list-item-avatar>
                    <v-list-item-content>
                      <v-list-item-title>{{
                        activity.title
                      }}</v-list-item-title>
                      <v-list-item-subtitle>{{
                        activity.time
                      }}</v-list-item-subtitle>
                    </v-list-item-content>
                  </v-list-item>
                </v-list>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-container>
    </v-main>

    <v-footer app color="grey lighten-3">
      <v-spacer></v-spacer>
      <span>&copy; 2025 SK hynix. All rights reserved.</span>
    </v-footer>
  </v-app>
</template>

<script setup>
import { ref } from "vue";

const drawer = ref(false);

const menuItems = ref([
  { title: "대시보드", icon: "mdi-view-dashboard", route: "/" },
  { title: "데이터 분석", icon: "mdi-chart-line", route: "/analysis" },
  { title: "장비 관리", icon: "mdi-cog", route: "/equipment" },
  { title: "설정", icon: "mdi-settings", route: "/settings" },
]);

const stats = ref([
  { title: "활성 장비", value: "12", icon: "mdi-factory", color: "success" },
  { title: "오늘 측정", value: "48", icon: "mdi-chart-box", color: "info" },
  { title: "알림", value: "3", icon: "mdi-bell", color: "warning" },
  {
    title: "데이터 용량",
    value: "2.4GB",
    icon: "mdi-database",
    color: "primary",
  },
]);

const activities = ref([
  {
    id: 1,
    title: "AFM-01 측정 완료",
    time: "10분 전",
    icon: "mdi-check-circle",
    color: "success",
  },
  {
    id: 2,
    title: "데이터 백업 시작",
    time: "30분 전",
    icon: "mdi-backup-restore",
    color: "info",
  },
  {
    id: 3,
    title: "시스템 업데이트",
    time: "1시간 전",
    icon: "mdi-update",
    color: "primary",
  },
]);
</script>
```

### 레이아웃 최적화 팁

#### 컨테이너 선택

- 일반적인 콘텐츠: `v-container` 사용
- 전체 너비 필요시: `v-container fluid` 사용

#### 간격 조정

- `class="mb-4"`: 아래쪽 여백 추가
- `class="pa-4"`: 모든 방향 패딩 추가
- `class="mx-auto"`: 수평 가운데 정렬

#### 반응형 고려사항

- 모바일: 대부분 `cols="12"` 사용
- 태블릿: `sm="6"` 또는 `sm="12"`
- 데스크톱: `md="4"`, `md="6"`, `md="8"` 등 활용

## 기본 컴포넌트 사용

### 핵심 컴포넌트 소개

AFM 데이터 뷰어에서 가장 자주 사용하게 될 Vuetify 컴포넌트들을 실무 중심으로 설명합니다.

### 버튼 컴포넌트

#### 기본 버튼 사용법

```javascript
<template>
  <v-btn>기본 버튼</v-btn>
  <v-btn color="primary">주요 버튼</v-btn>
  <v-btn color="success" variant="outlined">
    {" "}
    성공 아웃라인{" "}
  </v-btn>
  <v-btn color="error" variant="text">
    {" "}
    에러 텍스트{" "}
  </v-btn>
  <v-btn size="large" prepend-icon="mdi-download">
    {" "}
    다운로드{" "}
  </v-btn>
</template>
```

#### 실제 사용 예시

```javascript
<template>
  <v-btn
    color="primary"
    prepend-icon="mdi-download"
    @click="downloadData"
    :loading="isDownloading"
  >
    데이터 다운로드
  </v-btn>
</template>

<script setup>
import { ref } from "vue";

const isDownloading = ref(false);

const downloadData = async () => {
  isDownloading.value = true;
  await new Promise((resolve) => setTimeout(resolve, 2000));
  isDownloading.value = false;
};
</script>
```

### 카드 컴포넌트

#### 기본 카드 구조

```javascript
<template>
  <v-card>
    <v-card-title>카드 제목</v-card-title>
    <v-card-subtitle>부제목</v-card-subtitle>
    <v-card-text>카드 내용</v-card-text>
    <v-card-actions>
      <v-btn>액션1</v-btn>
      <v-btn>액션2</v-btn>
    </v-card-actions>
  </v-card>
</template>
```

#### AFM 측정 정보 카드

```javascript
<template>
  <v-card class="ma-2" elevation="2">
    <v-card-title class="d-flex align-center">
      <v-icon color="primary" class="mr-2">mdi-microscope</v-icon>
      {{ equipment.name }}
      <v-spacer></v-spacer>
      <v-chip :color="getStatusColor(equipment.status)" small>
        {{ equipment.status }}
      </v-chip>
    </v-card-title>

    <v-card-text>
      <v-row>
        <v-col cols="6">
          <div class="text-caption">마지막 측정</div>
          <div class="text-body-1">{{ equipment.lastMeasurement }}</div>
        </v-col>
        <v-col cols="6">
          <div class="text-caption">총 측정 수</div>
          <div class="text-body-1">{{ equipment.totalMeasurements }}</div>
        </v-col>
      </v-row>
    </v-card-text>

    <v-card-actions>
      <v-btn color="primary" variant="text">상세보기</v-btn>
      <v-btn color="success" variant="text">측정시작</v-btn>
    </v-card-actions>
  </v-card>
</template>

<script setup>
const getStatusColor = (status) => {
  const colors = {
    active: "success",
    maintenance: "warning",
    offline: "error",
  };
  return colors[status] || "grey";
};
</script>
```

### 입력 폼 컴포넌트

#### 텍스트 입력

```javascript
<template>
  <v-text-field
    v-model="sampleId"
    label="샘플 ID"
    placeholder="예: AFM-2025-001"
    prepend-icon="mdi-tag"
    :rules="sampleIdRules"
    required
  ></v-text-field>
</template>

<script setup>
import { ref } from "vue";

const sampleId = ref("");
const sampleIdRules = [
  (v) => !!v || "샘플 ID는 필수입니다",
  (v) => v.length >= 3 || "최소 3자 이상 입력해주세요",
];
</script>
```

#### 선택 드롭다운

```javascript
<template>
  <v-select
    v-model="selectedEquipment"
    :items="equipmentList"
    item-title="name"
    item-value="id"
    label="장비 선택"
    prepend-icon="mdi-factory"
    clearable
  ></v-select>
</template>

<script setup>
import { ref } from "vue";

const selectedEquipment = ref(null);
const equipmentList = ref([
  { id: 1, name: "AFM-01", status: "active" },
  { id: 2, name: "AFM-02", status: "maintenance" },
  { id: 3, name: "AFM-03", status: "active" },
]);
</script>
```

#### 날짜 선택

```javascript
<template>
  <v-text-field
    v-model="measurementDate"
    label="측정 날짜"
    type="date"
    prepend-icon="mdi-calendar"
  ></v-text-field>
</template>

<script setup>
import { ref } from "vue";

const measurementDate = ref(new Date().toISOString().slice(0, 10));
</script>
```

### 데이터 테이블

#### 기본 데이터 테이블

```javascript
<template>
  <v-data-table
    :headers="headers"
    :items="measurements"
    :search="search"
    class="elevation-1"
  >
    <template v-slot:top>
      <v-toolbar flat>
        <v-toolbar-title>측정 데이터</v-toolbar-title>
        <v-spacer></v-spacer>
        <v-text-field
          v-model="search"
          append-icon="mdi-magnify"
          label="검색"
          single-line
          hide-details
        ></v-text-field>
      </v-toolbar>
    </template>

    <template v-slot:item.status="{ item }">
      <v-chip :color="getStatusColor(item.status)" small>
        {{ item.status }}
      </v-chip>
    </template>

    <template v-slot:item.actions="{ item }">
      <v-icon small class="mr-2" @click="viewItem(item)"> mdi-eye </v-icon>
      <v-icon small @click="downloadItem(item)"> mdi-download </v-icon>
    </template>
  </v-data-table>
</template>

<script setup>
import { ref } from "vue";

const search = ref("");
const headers = ref([
  { title: "샘플 ID", value: "sampleId", sortable: true },
  { title: "측정 날짜", value: "date", sortable: true },
  { title: "측정값 (nm)", value: "value", sortable: true },
  { title: "상태", value: "status", sortable: false },
  { title: "액션", value: "actions", sortable: false },
]);

const measurements = ref([
  {
    sampleId: "AFM-001",
    date: "2025-01-15",
    value: 2.5,
    status: "completed",
  },
  {
    sampleId: "AFM-002",
    date: "2025-01-16",
    value: 3.1,
    status: "processing",
  },
]);

const viewItem = (item) => {
  console.log("상세보기:", item);
};

const downloadItem = (item) => {
  console.log("다운로드:", item);
};
</script>
```

### 내비게이션 컴포넌트

#### 앱바와 사이드 네비게이션

```javascript
<template>
  <v-app>
    <v-app-bar app color="primary" dark>
      <v-app-bar-nav-icon @click="drawer = !drawer"></v-app-bar-nav-icon>
      <v-toolbar-title>AFM Data Viewer</v-toolbar-title>
      <v-spacer></v-spacer>

      <v-btn icon>
        <v-badge
          :content="notificationCount"
          :value="notificationCount > 0"
          color="error"
        >
          <v-icon>mdi-bell</v-icon>
        </v-badge>
      </v-btn>

      <v-menu>
        <template v-slot:activator="{ props }">
          <v-btn icon v-bind="props">
            <v-icon>mdi-account</v-icon>
          </v-btn>
        </template>
        <v-list>
          <v-list-item @click="logout">
            <v-list-item-title>로그아웃</v-list-item-title>
          </v-list-item>
        </v-list>
      </v-menu>
    </v-app-bar>

    <v-navigation-drawer v-model="drawer" app>
      <v-list>
        <v-list-item
          v-for="item in menuItems"
          :key="item.title"
          :to="item.route"
          link
        >
          <template v-slot:prepend>
            <v-icon>{{ item.icon }}</v-icon>
          </template>
          <v-list-item-title>{{ item.title }}</v-list-item-title>
        </v-list-item>
      </v-list>
    </v-navigation-drawer>
  </v-app>
</template>

<script setup>
import { ref } from "vue";

const drawer = ref(false);
const notificationCount = ref(3);

const menuItems = ref([
  { title: "대시보드", icon: "mdi-view-dashboard", route: "/" },
  { title: "측정 데이터", icon: "mdi-chart-line", route: "/measurements" },
  { title: "장비 관리", icon: "mdi-cog", route: "/equipment" },
  { title: "설정", icon: "mdi-settings", route: "/settings" },
]);

const logout = () => {
  console.log("로그아웃");
};
</script>
```

## 테마 커스터마이징

### 기본 테마 설정

Vuetify의 테마 시스템을 활용하여 SK hynix 브랜드에 맞는 색상과 스타일을 적용할 수 있습니다.

### 색상 테마 커스터마이징

#### main.js에서 테마 설정

```javascript
import { createVuetify } from "vuetify";

const vuetify = createVuetify({
  theme: {
    defaultTheme: "light",
    themes: {
      light: {
        colors: {
          primary: "#1976D2",
          secondary: "#424242",
          accent: "#82B1FF",
          error: "#FF5252",
          info: "#2196F3",
          success: "#4CAF50",
          warning: "#FFC107",
          surface: "#FFFFFF",
          background: "#F5F5F5",
        },
      },
      dark: {
        colors: {
          primary: "#2196F3",
          secondary: "#616161",
          accent: "#FF4081",
          error: "#F44336",
          info: "#2196F3",
          success: "#4CAF50",
          warning: "#FF9800",
          surface: "#303030",
          background: "#121212",
        },
      },
    },
  },
});
```

### SCSS 변수 활용

#### styles/variables.scss 파일 생성

```scss
$sk-blue: #1976d2;
$sk-gray: #424242;
$sk-light-gray: #f5f5f5;

$primary-gradient: linear-gradient(135deg, #1976d2 0%, #42a5f5 100%);
$card-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

$base-spacing: 8px;

$font-family: "Roboto", "Noto Sans KR", sans-serif;
```

#### 컴포넌트에서 SCSS 변수 사용

```javascript
<template>
  <v-card class="custom-card">
    <v-card-title class="custom-title"> AFM 측정 현황 </v-card-title>
  </v-card>
</template>

<style lang="scss" scoped>
@import "@/styles/variables.scss";

.custom-card {
  background: linear-gradient(135deg, $sk-blue 0%, lighten($sk-blue, 20%) 100%);
  box-shadow: $card-shadow;
  border-radius: 12px;

  .custom-title {
    color: white;
    font-family: $font-family;
    font-weight: 500;
  }
}
</style>
```

### 다크 모드 구현

#### 다크 모드 토글 기능

```javascript
<template>
  <v-app :theme="currentTheme">
    <v-app-bar>
      <v-btn icon @click="toggleTheme">
        <v-icon>{{ themeIcon }}</v-icon>
      </v-btn>
    </v-app-bar>
  </v-app>
</template>

<script setup>
import { useTheme } from "vuetify";
import { ref, computed, onMounted } from "vue";

const theme = useTheme();
const currentTheme = ref("light");

const themeIcon = computed(() => {
  return currentTheme.value === "light"
    ? "mdi-weather-night"
    : "mdi-weather-sunny";
});

const toggleTheme = () => {
  currentTheme.value = currentTheme.value === "light" ? "dark" : "light";
  theme.global.name.value = currentTheme.value;
  localStorage.setItem("theme", currentTheme.value);
};

onMounted(() => {
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme) {
    currentTheme.value = savedTheme;
    theme.global.name.value = savedTheme;
  }
});
</script>
```

### 반응형 디자인 최적화

#### 브레이크포인트별 스타일 조정

```scss
.dashboard-grid {
  .v-col {
    padding: 8px;

    @media (min-width: 600px) {
      padding: 12px;
    }

    @media (min-width: 960px) {
      padding: 16px;
    }
  }
}

.equipment-card {
  margin: 8px 0;

  @media (max-width: 599px) {
    .v-card-title {
      font-size: 1.1rem;
      padding: 12px;
    }

    .v-card-text {
      padding: 8px 12px;
    }
  }
}
```

## Vuetify 효과적으로 활용하기

### 실용적인 접근 방법

Vuetify를 비롯한 UI 프레임워크는 전부 이해하면서 할 필요는 없습니다. 개발을 진행하면서 필요한 컴포넌트들을 그때 그때 찾아서 넣으면 됩니다.

### 학습 vs 실무 접근법

| 구분     | 학습 중심          | 실무 중심 (권장)      |
| -------- | ------------------ | --------------------- |
| 방식     | 모든 컴포넌트 숙지 | 필요한 것만 검색 사용 |
| 시간     | 몇 주~몇 달        | 즉시 시작 가능        |
| 효과     | 이론적 완벽함      | 빠른 결과물           |
| 스트레스 | 높음               | 낮음                  |

### 컴포넌트 찾기 전략

#### 공식 문서 활용

- [Vuetify 컴포넌트 문서](https://vuetifyjs.com/en/components/all/)
- 검색 기능으로 원하는 컴포넌트 빠르게 찾기
- 예시 코드 복사해서 바로 사용

#### "내가 뭘 만들고 싶은가?" 기준으로 검색

```text
이런 식으로 생각하고 검색하세요:
"버튼이 필요해" → "vuetify button" 검색
"테이블이 필요해" → "vuetify data table" 검색
"폼을 만들어야 해" → "vuetify form input" 검색
"차트를 보여줘야 해" → "vuetify charts" 또는 다른 차트 라이브러리 검색
"LLM도 적극 활용합니다"
```

#### 단계별 개발 프로세스

```javascript
<!-- Step 1: 기본 레이아웃부터 시작 -->
<template>
  <v-container>
    <v-row>
      <v-col>
        <!-- 여기에 내용 추가할 예정 -->
      </v-col>
    </v-row>
  </v-container>
</template>

<!-- Step 2: 필요한 컴포넌트 하나씩 추가 -->
<!-- 버튼이 필요하면 → v-btn 검색해서 추가 -->
<!-- 카드가 필요하면 → v-card 검색해서 추가 -->
<!-- 입력폼이 필요하면 → v-text-field 검색해서 추가 -->
```

### 자주 사용하는 핵심 컴포넌트

AFM 데이터 플랫폼에서 90% 이상 사용하게 될 컴포넌트들:

#### 레이아웃 관련

- `v-container`, `v-row`, `v-col` (그리드 시스템)
- `v-app-bar` (상단 네비게이션)
- `v-card` (카드 컨테이너)

#### 입력 관련

- `v-btn` (버튼)
- `v-text-field` (텍스트 입력)
- `v-select` (드롭다운)
- `v-checkbox` (체크박스)

#### 데이터 표시

- `v-data-table` (테이블)
- `v-list` (리스트)
- `v-chip` (태그/라벨)

### 스타일링 꿀팁

#### 클래스 기반 스타일링

```javascript
<template>
  <!-- Vuetify는 유틸리티 클래스를 제공합니다 -->
  <v-card class="ma-4 pa-3 elevation-2">
    <!-- ma-4: margin 16px, pa-3: padding 12px, elevation-2: 그림자 -->
  </v-card>

  <!-- 색상도 클래스로 쉽게 적용 -->
  <v-btn color="primary">주요 버튼</v-btn>
  <v-btn color="success">성공 버튼</v-btn>
  <v-btn color="error">에러 버튼</v-btn>
</template>
```

#### 반응형 디자인 쉽게 하기

```javascript
<template>
  <!-- 화면 크기별로 다른 컬럼 수 지정 -->
  <v-col cols="12" sm="6" md="4" lg="3">
    <!-- 모바일: 12컬럼, 태블릿: 6컬럼, 데스크톱: 4컬럼, 대형: 3컬럼 -->
  </v-col>
</template>
```

### 개발 워크플로우

#### 실제 개발할 때 이렇게 하세요

1. 목업/디자인 보기 → "어떤 컴포넌트가 필요한가?"
2. Vuetify 문서에서 검색 → 비슷한 컴포넌트 찾기
3. 예제 코드 복사 → 내 프로젝트에 붙여넣기
4. 필요에 맞게 수정 → 데이터, 색상, 크기 등 조정
5. 동작 확인 → 브라우저에서 테스트
6. 다음 컴포넌트로 → 반복

#### 실제 예시: 데이터 테이블 만들기

```javascript
<!-- 1. "데이터 테이블 필요해" 생각 -->
<!-- 2. "vuetify data table" 검색 -->
<!-- 3. 공식 문서 예제 복사 -->
<!-- 4. 내 데이터에 맞게 수정 -->

<template>
  <v-data-table :headers="headers" :items="measurements" class="elevation-1">
  </v-data-table>
</template>

<script setup>
import { ref } from "vue";

const headers = ref([
  { title: "샘플 ID", value: "sampleId" },
  { title: "측정값", value: "value" },
  { title: "날짜", value: "date" },
]);

const measurements = ref([
  { sampleId: "A001", value: 2.5, date: "2025-01-15" },
  { sampleId: "A002", value: 3.1, date: "2025-01-16" },
]);
</script>
```

### 추천 학습 리소스

#### 즉시 활용 가능한 자료들

1. [Vuetify 컴포넌트 갤러리](https://vuetifyjs.com/en/components/all/) - 모든 컴포넌트 한눈에 보기
2. [Material Design Icons](https://materialdesignicons.com/) - 아이콘 검색 및 사용법
3. [Vuetify Playground](https://play.vuetifyjs.com/) - 온라인에서 바로 테스트
4. ChatGPT/Claude 활용 - "Vuetify로 OO 만드는 방법" 질문

#### 핵심 메시지

"완벽하게 알고 시작하지 마세요. 만들면서 배우세요!"

실제로 AFM 데이터 플랫폼을 개발하면서 Vuetify 컴포넌트를 하나씩 익혀나가는 것이 가장 효율적이고 재미있는 방법입니다. 필요할 때마다 검색하고, 복사하고, 수정하면서 점진적으로 실력을 향상시켜 나갑시다!
