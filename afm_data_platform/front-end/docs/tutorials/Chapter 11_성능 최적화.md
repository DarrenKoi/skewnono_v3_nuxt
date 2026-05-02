# 성능 최적화

Vue 애플리케이션이 성장하면서 성능 문제가 발생할 수 있습니다. 특히 AFM 데이터 뷰어처럼 대용량 데이터와 복잡한 차트를 다루는 애플리케이션에서는 성능 최적화가 필요할 수 있습니다. 이 장에서는 Vue 3 애플리케이션의 성능을 향상시키는 기법들을 살펴보겠습니다. 웹 어플리케이션 개발이 익숙해지고 점차 기능이 추가되고 고도화되는 시점에 익히면 좋습니다.

---

## 컴포넌트 지연 로딩

### 지연 로딩이란?

지연 로딩(Lazy Loading)은 사용자가 실제로 필요한 시점에 컴포넌트를 로드하는 기법입니다. 초기 페이지 로딩 시 모든 컴포넌트를 한 번에 불러오는 대신, 필요할 때만 불러와서 초기 로딩 시간을 단축시킵니다.

반도체 장비 대시보드처럼 여러 페이지와 복잡한 컴포넌트를 가진 애플리케이션에서는 지연 로딩이 특히 중요합니다. 사용자가 처음 접속했을 때 모든 차트 라이브러리와 데이터 분석 도구를 로드하면 초기 로딩이 매우 느려질 수 있습니다.

### Vue Router에서 지연 로딩 구현

#### 기본 라우터 설정 (지연 로딩 미적용)

```js
// router/index.js
import { createRouter, createWebHistory } from "vue-router";
import Dashboard from "@/views/Dashboard.vue";
import DataAnalysis from "@/views/DataAnalysis.vue";
import EquipmentManagement from "@/views/EquipmentManagement.vue";
import Settings from "@/views/Settings.vue";

const routes = [
  { path: "/", name: "Dashboard", component: Dashboard },
  { path: "/analysis", name: "DataAnalysis", component: DataAnalysis },
  {
    path: "/equipment",
    name: "EquipmentManagement",
    component: EquipmentManagement,
  },
  { path: "/settings", name: "Settings", component: Settings },
];
```

#### 지연 로딩 적용

```js
// router/index.js
import { createRouter, createWebHistory } from "vue-router";

const routes = [
  {
    path: "/",
    name: "Dashboard",
    component: () => import("@/views/Dashboard.vue"),
  },
  {
    path: "/analysis",
    name: "DataAnalysis",
    component: () => import("@/views/DataAnalysis.vue"),
  },
  {
    path: "/equipment",
    name: "EquipmentManagement",
    component: () => import("@/views/EquipmentManagement.vue"),
  },
  {
    path: "/settings",
    name: "Settings",
    component: () => import("@/views/Settings.vue"),
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
```

### 컴포넌트 레벨에서 지연 로딩

```js
<!-- DashboardView.vue -->
<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <h1>대시보드</h1>
      </v-col>
    </v-row>
    <!-- 탭 기반 지연 로딩 -->
    <v-tabs v-model="activeTab">
      <v-tab value="overview">개요</v-tab>
      <v-tab value="charts">차트 분석</v-tab>
      <v-tab value="reports">리포트</v-tab>
    </v-tabs>
    <v-tabs-items v-model="activeTab">
      <v-tab-item value="overview">
        <OverviewPanel />
      </v-tab-item>
      <v-tab-item value="charts">
        <Suspense>
          <template #default>
            <ChartsPanel />
          </template>
          <template #fallback>
            <v-progress-circular indeterminate />
          </template>
        </Suspense>
      </v-tab-item>
      <v-tab-item value="reports">
        <Suspense>
          <template #default>
            <ReportsPanel />
          </template>
          <template #fallback>
            <v-skeleton-loader type="article" />
          </template>
        </Suspense>
      </v-tab-item>
    </v-tabs-items>
  </v-container>
</template>

<script setup>
import { ref, defineAsyncComponent } from "vue";
import OverviewPanel from "@/components/dashboard/OverviewPanel.vue";

// 무거운 컴포넌트들은 지연 로딩
const ChartsPanel = defineAsyncComponent(() =>
  import("@/components/dashboard/ChartsPanel.vue")
);

const ReportsPanel = defineAsyncComponent({
  loader: () => import("@/components/dashboard/ReportsPanel.vue"),
  loadingComponent: () => h("div", "Loading..."),
  errorComponent: () => h("div", "Error loading component"),
  delay: 200,
  timeout: 10000,
});

const activeTab = ref("overview");
</script>
```

### 조건부 컴포넌트 로딩

```js
<!-- EquipmentDetail.vue -->
<template>
  <v-container>
    <v-row>
      <v-col cols="12">
        <v-btn @click="showAdvancedAnalysis = !showAdvancedAnalysis">
          고급 분석 도구 {{ showAdvancedAnalysis ? "숨기기" : "보기" }}
        </v-btn>
      </v-col>
    </v-row>
    <!-- 사용자가 요청할 때만 로드 -->
    <v-row v-if="showAdvancedAnalysis">
      <v-col cols="12">
        <AdvancedAnalysisTools
          v-if="isComponentLoaded"
          :equipment-id="equipmentId"
        />
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, watch, defineAsyncComponent } from "vue";

const props = defineProps({ equipmentId: String });
const showAdvancedAnalysis = ref(false);
const isComponentLoaded = ref(false);

// 컴포넌트 동적 로드
const AdvancedAnalysisTools = defineAsyncComponent(() =>
  import("@/components/analysis/AdvancedAnalysisTools.vue")
);

// 사용자가 고급 분석을 열 때만 컴포넌트 로드
watch(showAdvancedAnalysis, (newVal) => {
  if (newVal && !isComponentLoaded.value) {
    isComponentLoaded.value = true;
  }
});
</script>
```

---

## 이미지 최적화

### 이미지 최적화의 중요성

AFM 데이터 뷰어에서는 장비 사진, 측정 결과 이미지, 사용자 프로필 등 다양한 이미지를 사용합니다. 최적화되지 않은 이미지는 페이지 로딩 속도를 크게 저하시킬 수 있습니다.

### 이미지 지연 로딩 구현

```js
<!-- ImageLazyLoad.vue -->
<template>
  <div ref="imageContainer" class="image-container">
    <v-img
      v-if="isIntersecting"
      :src="src"
      :alt="alt"
      :aspect-ratio="aspectRatio"
      @load="onImageLoad"
      @error="onImageError"
    >
      <template v-slot:placeholder>
        <v-row class="fill-height ma-0" align="center" justify="center">
          <v-progress-circular indeterminate color="grey lighten-5" />
        </v-row>
      </template>
    </v-img>
    <!-- 이미지 로드 전 플레이스홀더 -->
    <v-skeleton-loader v-else :type="skeletonType" :height="height" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";

const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: "" },
  aspectRatio: { type: [String, Number], default: 1.7778 },
  height: { type: [String, Number], default: 200 },
  skeletonType: { type: String, default: "image" },
});
const emit = defineEmits(["load", "error"]);
const imageContainer = ref(null);
const isIntersecting = ref(false);
let observer = null;
// Intersection Observer 설정
onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          isIntersecting.value = true;
          observer.unobserve(entry.target);
        }
      });
    },
    { rootMargin: "50px" }
  );
  if (imageContainer.value) {
    observer.observe(imageContainer.value);
  }
});
onUnmounted(() => {
  if (observer && imageContainer.value) {
    observer.unobserve(imageContainer.value);
  }
});
const onImageLoad = () => {
  emit("load");
};
const onImageError = () => {
  emit("error");
};
</script>

<style scoped>
.image-container {
  width: 100%;
  overflow: hidden;
}
</style>
```

### 이미지 포맷 최적화

```js
<!-- OptimizedImage.vue -->
<template>
  <picture>
    <!-- WebP 지원 브라우저용 -->
    <source :srcset="webpSrcset" type="image/webp" />
    <!-- JPEG 폴백 -->
    <source :srcset="jpegSrcset" type="image/jpeg" />
    <!-- 기본 이미지 -->
    <img
      :src="defaultSrc"
      :alt="alt"
      :loading="loading"
      class="responsive-image"
    />
  </picture>
</template>

<script setup>
import { computed } from "vue";
const props = defineProps({
  src: { type: String, required: true },
  alt: { type: String, default: "" },
  sizes: { type: Array, default: () => [320, 640, 1024, 1920] },
  loading: { type: String, default: "lazy" },
});
const baseName = computed(() =>
  props.src.substring(0, props.src.lastIndexOf("."))
);
const webpSrcset = computed(() =>
  props.sizes
    .map((size) => `${baseName.value}-${size}w.webp ${size}w`)
    .join(", ")
);
const jpegSrcset = computed(() =>
  props.sizes
    .map((size) => `${baseName.value}-${size}w.jpg ${size}w`)
    .join(", ")
);
const defaultSrc = computed(() => `${baseName.value}-${props.sizes[1]}w.jpg`);
</script>

<style scoped>
.responsive-image {
  width: 100%;
  height: auto;
  display: block;
}
</style>
```

### 이미지 프리로딩 전략

```js
// utils/imagePreloader.js
export class ImagePreloader {
  constructor() {
    this.cache = new Map();
  }
  // 단일 이미지 프리로드
  preload(src) {
    if (this.cache.has(src)) return this.cache.get(src);
    const promise = new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = src;
    });
    this.cache.set(src, promise);
    return promise;
  }
  // 여러 이미지 프리로드
  preloadMultiple(sources) {
    return Promise.all(sources.map((src) => this.preload(src)));
  }
  // 우선순위 기반 프리로드
  preloadWithPriority(images) {
    const high = images.filter((img) => img.priority === "high");
    const medium = images.filter((img) => img.priority === "medium");
    const low = images.filter((img) => img.priority === "low");
    // 높은 우선순위부터 순차적으로 로드
    return this.preloadMultiple(high.map((img) => img.src))
      .then(() => this.preloadMultiple(medium.map((img) => img.src)))
      .then(() => this.preloadMultiple(low.map((img) => img.src)));
  }
}
// 사용 예시
const preloader = new ImagePreloader();
// 라우트 진입 전 중요 이미지 프리로드
router.beforeEach(async (to, from, next) => {
  if (to.name === "Dashboard") {
    await preloader.preloadMultiple([
      "/images/dashboard-hero.jpg",
      "/images/equipment-overview.png",
    ]);
  }
  next();
});
```

---

## 번들 크기 줄이기

### 번들 분석

번들 크기를 줄이기 전에 먼저 현재 상태를 분석해야 합니다.

```js
// vite.config.js
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig({
  plugins: [
    vue(),
    // 번들 크기 시각화
    visualizer({
      open: true,
      filename: "dist/stats.html",
      gzipSize: true,
      brotliSize: true,
    }),
  ],
  build: {
    // 번들 크기 경고 임계값
    chunkSizeWarningLimit: 500,
    rollupOptions: {
      output: {
        // 수동 청크 분할
        manualChunks: {
          "vue-vendor": ["vue", "vue-router", "pinia"],
          "ui-vendor": ["vuetify"],
          "chart-vendor": ["echarts"],
          utils: ["lodash-es", "date-fns"],
        },
      },
    },
  },
});
```

### 트리 쉐이킹 최적화

```js
// 잘못된 예 - 전체 라이브러리 import
import _ from "lodash";
import * as echarts from "echarts";
import { VBtn, VCard, VContainer } from "vuetify/components";

// 올바른 예 - 필요한 것만 import
import debounce from "lodash-es/debounce";
import groupBy from "lodash-es/groupBy";
// ECharts 모듈별 import
import { use } from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { LineChart, BarChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
} from "echarts/components";

use([
  CanvasRenderer,
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
]);
```

### 동적 import를 통한 코드 분할

```vue
<!-- ChartContainer.vue -->
<template>
  <div class="chart-container">
    <v-select
      v-model="selectedChartType"
      :items="chartTypes"
      label="차트 타입 선택"
    />
    <component v-if="chartComponent" :is="chartComponent" :data="chartData" />
  </div>
</template>

<script setup>
import { ref, computed, defineAsyncComponent } from "vue";
const props = defineProps({ chartData: { type: Array, required: true } });
const selectedChartType = ref("line");
const chartTypes = ["line", "bar", "scatter", "heatmap"];
// 선택된 차트 타입에 따라 동적으로 컴포넌트 로드
const chartComponent = computed(() => {
  switch (selectedChartType.value) {
    case "line":
      return defineAsyncComponent(() =>
        import("@/components/charts/LineChart.vue")
      );
    case "bar":
      return defineAsyncComponent(() =>
        import("@/components/charts/BarChart.vue")
      );
    case "scatter":
      return defineAsyncComponent(() =>
        import("@/components/charts/ScatterChart.vue")
      );
    case "heatmap":
      return defineAsyncComponent(() =>
        import("@/components/charts/HeatmapChart.vue")
      );
    default:
      return null;
  }
});
</script>
```

### Production 빌드 최적화

```js
// vite.config.js
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import viteCompression from "vite-plugin-compression";

export default defineConfig({
  plugins: [
    vue(),
    // Gzip 압축
    viteCompression({
      verbose: true,
      disable: false,
      threshold: 10240,
      algorithm: "gzip",
      ext: ".gz",
    }),
    // Brotli 압축
    viteCompression({
      verbose: true,
      disable: false,
      threshold: 10240,
      algorithm: "brotliCompress",
      ext: ".br",
    }),
  ],
  build: {
    // CSS 코드 분할
    cssCodeSplit: true,
    // 소스맵 생성 비활성화 (프로덕션)
    sourcemap: false,
    // Terser 옵션
    terserOptions: {
      compress: {
        drop_console: true,
        drop_debugger: true,
      },
    },
    // 작은 에셋 인라인 임계값
    assetsInlineLimit: 4096,
  },
});
```

---

## 메모리 누수 방지

### 일반적인 메모리 누수 원인

Vue 애플리케이션에서 메모리 누수는 주로 다음과 같은 상황에서 발생합니다:

- 이벤트 리스너를 제거하지 않은 경우
- 타이머나 인터벌을 정리하지 않은 경우
- 전역 변수나 클로저에 대한 참조가 남아있는 경우
- 제3자 라이브러리의 인스턴스를 정리하지 않은 경우

### 이벤트 리스너 관리

```js
<!-- EventHandlingComponent.vue -->
<template>
  <div ref="chartContainer" class="chart-wrapper">
    <canvas ref="canvas"></canvas>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
const chartContainer = ref(null);
const canvas = ref(null);
// 이벤트 핸들러를 별도 변수로 저장
const handleResize = () => {
  if (canvas.value) {
    canvas.value.width = chartContainer.value.clientWidth;
    canvas.value.height = chartContainer.value.clientHeight;
    redrawChart();
  }
};
const handleScroll = (event) => {
  // 스크롤 처리 로직
  console.log("Scroll position:", event.target.scrollTop);
};
const handleKeydown = (event) => {
  if (event.key === "Escape") {
    // ESC 키 처리
  }
};
onMounted(() => {
  // 이벤트 리스너 등록
  window.addEventListener("resize", handleResize);
  chartContainer.value?.addEventListener("scroll", handleScroll);
  document.addEventListener("keydown", handleKeydown);
  // 초기 캔버스 크기 설정
  handleResize();
});
onUnmounted(() => {
  // 모든 이벤트 리스너 제거
  window.removeEventListener("resize", handleResize);
  chartContainer.value?.removeEventListener("scroll", handleScroll);
  document.removeEventListener("keydown", handleKeydown);
});
const redrawChart = () => {
  // 차트 다시 그리기 로직
};
</script>
```

### 타이머 및 인터벌 정리

```js
<!-- DataPollingComponent.vue -->
<template>
  <div>
    <h3>실시간 장비 상태</h3>
    <div v-for="equipment in equipmentStatus" :key="equipment.id">
      {{ equipment.name }}: {{ equipment.status }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue";
import { useEquipmentStore } from "@/stores/equipment";
const equipmentStore = useEquipmentStore();
const equipmentStatus = ref([]);
// 타이머 ID 저장
let pollingInterval = null;
let debounceTimeout = null;
// 데이터 폴링 함수
const fetchEquipmentStatus = async () => {
  try {
    const response = await fetch("/api/equipment/status");
    equipmentStatus.value = await response.json();
  } catch (error) {
    console.error("Failed to fetch equipment status:", error);
  }
};
// 디바운스된 업데이트 함수
const debouncedUpdate = (data) => {
  // 이전 타임아웃 취소
  if (debounceTimeout) {
    clearTimeout(debounceTimeout);
  }
  debounceTimeout = setTimeout(() => {
    equipmentStore.updateStatus(data);
  }, 300);
};
onMounted(() => {
  // 초기 데이터 로드
  fetchEquipmentStatus();
  // 5초마다 폴링
  pollingInterval = setInterval(fetchEquipmentStatus, 5000);
});
onUnmounted(() => {
  // 모든 타이머 정리
  if (pollingInterval) {
    clearInterval(pollingInterval);
    pollingInterval = null;
  }
  if (debounceTimeout) {
    clearTimeout(debounceTimeout);
    debounceTimeout = null;
  }
});
</script>
```

### 제3자 라이브러리 정리

```js
<!-- EChartsComponent.vue -->
<template>
  <div ref="chartDiv" style="width: 100%; height: 400px;"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch } from "vue";
import * as echarts from "echarts";
const props = defineProps({ option: { type: Object, required: true } });
const chartDiv = ref(null);
let chartInstance = null;
let resizeObserver = null;
// 차트 초기화
const initChart = () => {
  if (chartDiv.value) {
    // 기존 인스턴스가 있으면 먼저 정리
    if (chartInstance) {
      chartInstance.dispose();
    }
    chartInstance = echarts.init(chartDiv.value);
    chartInstance.setOption(props.option);
  }
};
// ResizeObserver를 사용한 반응형 차트
const observeResize = () => {
  resizeObserver = new ResizeObserver((entries) => {
    for (const entry of entries) {
      if (chartInstance) {
        chartInstance.resize();
      }
    }
  });
  if (chartDiv.value) {
    resizeObserver.observe(chartDiv.value);
  }
};
// props 변경 감지
watch(
  () => props.option,
  (newOption) => {
    if (chartInstance) {
      chartInstance.setOption(newOption, true);
    }
  },
  { deep: true }
);
onMounted(() => {
  initChart();
  observeResize();
});
onUnmounted(() => {
  // ECharts 인스턴스 정리
  if (chartInstance) {
    chartInstance.dispose();
    chartInstance = null;
  }
  // ResizeObserver 정리
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
});
</script>
```

### 컴포넌트 수명 주기 관리 베스트 프랙티스

```js
<!-- BestPracticeComponent.vue -->
<template>
  <div>
    <!-- 컴포넌트 내용 -->
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onBeforeUnmount } from "vue";
// 정리가 필요한 리소스들을 추적
const resources = {
  timers: new Set(),
  listeners: new Map(),
  subscriptions: new Set(),
};
// 타이머 래퍼 함수
const setManagedInterval = (callback, delay) => {
  const id = setInterval(callback, delay);
  resources.timers.add(id);
  return id;
};
const setManagedTimeout = (callback, delay) => {
  const id = setTimeout(() => {
    callback();
    resources.timers.delete(id);
  }, delay);
  resources.timers.add(id);
  return id;
};
// 이벤트 리스너 래퍼 함수
const addManagedListener = (target, event, handler) => {
  target.addEventListener(event, handler);
  if (!resources.listeners.has(target)) {
    resources.listeners.set(target, new Map());
  }
  resources.listeners.get(target).set(event, handler);
};
// WebSocket 연결 관리
const ws = ref(null);
const connectWebSocket = () => {
  ws.value = new WebSocket("ws://localhost:8080/realtime");
  ws.value.onmessage = (event) => {
    // 메시지 처리
  };
  ws.value.onerror = (error) => {
    console.error("WebSocket error:", error);
  };
};
// 모든 리소스 정리
const cleanup = () => {
  // 타이머 정리
  resources.timers.forEach((id) => {
    clearInterval(id);
    clearTimeout(id);
  });
  resources.timers.clear();
  // 이벤트 리스너 정리
  resources.listeners.forEach((events, target) => {
    events.forEach((handler, event) => {
      target.removeEventListener(event, handler);
    });
  });
  resources.listeners.clear();
  // WebSocket 정리
  if (ws.value) {
    ws.value.close();
    ws.value = null;
  }
  // 기타 구독 정리
  resources.subscriptions.forEach((unsubscribe) => {
    if (typeof unsubscribe === "function") {
      unsubscribe();
    }
  });
  resources.subscriptions.clear();
};
onMounted(() => {
  // 리소스 초기화
  connectWebSocket();
  // 관리되는 타이머 설정
  setManagedInterval(() => {
    console.log("Periodic task");
  }, 5000);
  // 관리되는 이벤트 리스너
  addManagedListener(window, "resize", () => {
    console.log("Window resized");
  });
});
// 컴포넌트 정리
onBeforeUnmount(() => {
  cleanup();
});
</script>
```

---

## 성능 모니터링 도구

### Vue DevTools 활용

Vue DevTools는 컴포넌트 트리, 상태 관리, 성능 프로파일링 등을 제공합니다. Chrome 웹 스토어에서 설치할 수 있으며, 개발 중 성능 문제를 진단하는 데 매우 유용합니다.

### Performance API 활용

```js
// utils/performanceMonitor.js
export const performanceMonitor = {
  marks: new Map(),
  // 성능 측정 시작
  start(label) {
    performance.mark(`${label}-start`);
    this.marks.set(label, performance.now());
  },
  // 성능 측정 종료
  end(label) {
    if (!this.marks.has(label)) {
      console.warn(`No start mark found for ${label}`);
      return;
    }
    performance.mark(`${label}-end`);
    performance.measure(label, `${label}-start`, `${label}-end`);
    const duration = performance.now() - this.marks.get(label);
    console.log(`${label} took ${duration.toFixed(2)}ms`);
    this.marks.delete(label);
    return duration;
  },
  // 모든 측정 결과 출력
  getResults() {
    const entries = performance.getEntriesByType("measure");
    return entries.map((entry) => ({
      name: entry.name,
      duration: entry.duration.toFixed(2),
    }));
  },
};
```

---

이러한 성능 최적화 기법들을 적용하면 AFM 데이터 뷰어가 더 빠르고 효율적으로 동작하게 됩니다. 특히 대용량 데이터를 다루는 반도체 장비 애플리케이션에서는 이러한 최적화가 사용자 경험을 크게 향상시킬 수 있습니다.

더 자세한 정보는 다음 문서들을 참고하시기 바랍니다:

- [Vue.js 성능 최적화 가이드](https://kr.vuejs.org/v2/guide/optimizations.html)
- [Vite 성능 최적화](https://vitejs.dev/guide/build.html)
- [Chrome DevTools 성능 프로파일링](https://developer.chrome.com/docs/devtools/evaluate-performance/)
