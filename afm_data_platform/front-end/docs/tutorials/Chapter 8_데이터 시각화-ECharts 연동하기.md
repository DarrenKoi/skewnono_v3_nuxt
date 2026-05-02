# **데이터 시각화 - ECharts 연동하기**

## **ECharts 소개**

### **ECharts란 무엇인가?**

ECharts(Enterprise Charts)는 Apache 소프트웨어 재단에서 관리하는 오픈소스 데이터 시각화 라이브러리입니다. 원래 중국의 Baidu에서 개발했으며, 현재는 Apache 프로젝트로 전 세계적으로 활발히 사용되고 있습니다. 반도체 장비에서 생성되는 복잡한 데이터를 직관적으로 시각화하는 데 매우 적합한 도구입니다.

**💡 추가 학습 자료**
ECharts 공식 홈페이지(https://echarts.apache.org/examples/)에서 다양한 차트와 예제들을 볼 수 있으니 직접 코드를 확인하면서 구현하길 추천합니다.

### **ECharts의 주요 특징**

**강력한 성능** ECharts는 Canvas와 SVG 렌더링을 모두 지원하여 대용량 데이터도 부드럽게 표현할 수 있습니다. 특히 AFM 측정 데이터처럼 수만 개의 데이터 포인트를 가진 경우에도 성능 저하 없이 시각화가 가능합니다. 스트리밍 데이터나 실시간 업데이트가 필요한 대시보드에서도 안정적인 성능을 보여줍니다.

**다양한 차트 타입** 기본적인 선 그래프, 막대 그래프부터 히트맵, 3D 차트, 지도 기반 시각화까지 30가지 이상의 차트 타입을 제공합니다. 반도체 공정 데이터 분석에 자주 사용되는 박스플롯, 산점도 행렬, 평행 좌표계 등 고급 차트도 지원합니다.

**인터랙티브 기능** 사용자가 차트와 상호작용할 수 있는 다양한 기능을 제공합니다. 데이터 줌, 드래그, 툴팁, 범례 필터링 등으로 사용자가 원하는 데이터를 자유롭게 탐색할 수 있습니다. 이는 엔지니어가 특정 구간의 데이터를 세밀하게 분석할 때 매우 유용합니다.

### **다른 차트 라이브러리와의 비교**

| 특징             | ECharts           | Chart.js       | D3.js              | Highcharts  |
| ---------------- | ----------------- | -------------- | ------------------ | ----------- |
| **학습 곡선**    | 중간              | 쉬움           | 어려움             | 중간        |
| **차트 종류**    | 매우 많음 (30+)   | 기본적 (8개)   | 무제한 (직접 구현) | 많음 (20+)  |
| **성능**         | 매우 우수         | 보통           | 우수               | 우수        |
| **커스터마이징** | 높음              | 중간           | 매우 높음          | 높음        |
| **라이선스**     | Apache 2.0 (무료) | MIT (무료)     | BSD (무료)         | 상업용 유료 |
| **파일 크기**    | 큼 (\~1MB)        | 작음 (\~200KB) | 중간 (\~500KB)     | 큼 (\~1MB)  |

### **ECharts를 선택한 이유**

기반기술센터의 AFM Data Viewer 프로젝트에서 ECharts를 선택한 주요 이유는 다음과 같습니다:

1. **무료 라이선스**: Apache 2.0 라이선스로 상업적 사용에 제약이 없습니다.
2. **풍부한 차트 타입**: 반도체 데이터 분석에 필요한 다양한 시각화를 한 라이브러리로 해결할 수 있습니다.
3. **뛰어난 성능**: 대용량 측정 데이터를 처리해도 브라우저가 느려지지 않습니다.
4. **Vue.js와의 호환성**: Vue 컴포넌트로 쉽게 통합할 수 있습니다.

## **설치 및 기본 설정**

### **ECharts 설치하기**

프로젝트 디렉토리에서 다음 명령어를 실행합니다:

```bash
# ECharts 설치
npm install echarts
```

### **기본 설정**

**전체 ECharts 가져오기 (간단한 방법)**

```javascript
// main.js 또는 컴포넌트에서
import * as echarts from "echarts";

// 전역으로 사용하고 싶은 경우
app.config.globalProperties.$echarts = echarts;
```

**필요한 모듈만 가져오기 (권장 \- 번들 크기 최적화)**

```javascript
// 필요한 차트와 컴포넌트만 import
import { init } from "echarts/core";
import { LineChart, BarChart } from "echarts/charts";
import {
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";

// ECharts에 사용할 기능들 등록
echarts.use([
  LineChart,
  BarChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer,
]);
```

### **Vue 컴포넌트에서 ECharts 통합하기**

## **핵심 통합 개념들**

### **1. 차트 인스턴스 생명주기 관리**

ECharts 인스턴스는 적절한 생명주기 (life cycle) 관리가 필수입니다:

```javascript
<template>
  <div ref="chartContainer" style="width: 100%; height: 400px;"></div>
</template>

<script setup>
import * as echarts from 'echarts'
import { ref, onMounted, onBeforeUnmount } from 'vue'

const chartContainer = ref(null)
const chart = ref(null)

const initChart = () => {
  // 기존 차트가 있다면 먼저 해제
  if (chart.value) {
    chart.value.dispose()
  }

  // 새 인스턴스 생성
  chart.value = echarts.init(chartContainer.value)

  // 차트 옵션은 ECharts 공식 홈페이지 예제 참조
  // https://echarts.apache.org/examples/
}

onMounted(() => {
  initChart()
})

onBeforeUnmount(() => {
  // 메모리 누수 방지를 위한 정리
  if (chart.value) {
    chart.value.dispose()
    chart.value = null
  }
})
</script>
```

**🔥 중요한 메모리 관리 포인트:**

- `onBeforeUnmount`에서 반드시 `dispose()` 호출
- 차트 참조를 `null`로 초기화
- 여러 차트가 있는 페이지에서는 더욱 중요

### **2. 반응형 크기 조정**

사용자가 브라우저 크기를 변경하거나 Vuetify 레이아웃이 변할 때 차트 크기 자동 조정:

```javascript
mounted() {
  this.initChart()

  // 윈도우 리사이즈 이벤트 등록
  window.addEventListener('resize', this.handleResize)
},
beforeUnmount() {
  window.removeEventListener('resize', this.handleResize)
  if (this.chart) {
    this.chart.dispose()
  }
},
methods: {
  handleResize() {
    if (this.chart) {
      this.chart.resize()
    }
  }
}
```

## **차트 컴포넌트 만들기**

### **재사용 가능한 차트 컴포넌트 설계**

실제 프로젝트에서는 차트를 재사용 가능한 컴포넌트로 만드는 것이 중요합니다. 다음은 AFM 데이터 뷰어에서 사용할 수 있는 범용 차트 컴포넌트 예제입니다.

**BaseChart.vue - 기본 차트 컴포넌트**

```javascript
<template>
  <div class="chart-container">
    <div ref="chartRef" :style="{ width: width, height: height }"></div>
  </div>
</template>

<script setup>
import * as echarts from 'echarts'
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  // 차트 옵션
  option: {
    type: Object,
    required: true
  },
  // 차트 크기
  width: {
    type: String,
    default: '100%'
  },
  height: {
    type: String,
    default: '400px'
  },
  // 테마
  theme: {
    type: String,
    default: 'light'
  }
})

const chart = ref(null)
const chartRef = ref(null)
const resizeObserver = ref(null)

const initChart = () => {
  // 기존 차트가 있으면 제거
  if (chart.value) {
    chart.value.dispose()
  }

  // 새 차트 인스턴스 생성
  chart.value = echarts.init(chartRef.value, props.theme)
  updateChart(props.option)
}

const updateChart = (option) => {
  if (chart.value && option) {
    chart.value.setOption(option, true)
  }
}

const addResizeListener = () => {
  window.addEventListener('resize', handleResize)
  // Vuetify 레이아웃 변경 감지
  resizeObserver.value = new ResizeObserver(handleResize)
  resizeObserver.value.observe(chartRef.value)
}

const removeResizeListener = () => {
  window.removeEventListener('resize', handleResize)
  if (resizeObserver.value) {
    resizeObserver.value.disconnect()
  }
}

const handleResize = () => {
  if (chart.value) {
    chart.value.resize()
  }
}

// Watch for option changes
watch(() => props.option, (newOption) => {
  updateChart(newOption)
}, { deep: true })

// Watch for theme changes
watch(() => props.theme, () => {
  initChart()
})

onMounted(() => {
  initChart()
  addResizeListener()
})

onBeforeUnmount(() => {
  removeResizeListener()
  if (chart.value) {
    chart.value.dispose()
    chart.value = null
  }
})
</script>

<style scoped>
.chart-container {
  position: relative;
  width: 100%;
}
</style>
```

### **특화된 차트 컴포넌트 만들기**

BaseChart를 확장하여 특정 용도의 차트를 만들 수 있습니다:

**AFMLineChart.vue - AFM 측정 데이터용 라인 차트 예시**

```javascript
<template>
  <v-card>
    <v-card-title>
      {{ title }}
      <v-spacer></v-spacer>
      <v-btn icon @click="exportChart">
        <v-icon>mdi-download</v-icon>
      </v-btn>
    </v-card-title>
    <v-card-text>
      <base-chart
        :option="chartOption"
        :height="height"
        ref="baseChart"
      />
    </v-card-text>
  </v-card>
</template>

<script setup>

import BaseChart from './BaseChart.vue'
import { computed, ref } from 'vue'

const props = defineProps({
  title: {
    type: String,
    default: 'AFM 측정 데이터'
  },
  data: {
    type: Array,
    required: true
  },
  xAxisLabel: {
    type: String,
    default: '측정 위치 (nm)'
  },
  yAxisLabel: {
    type: String,
    default: '높이 (nm)'
  },
  height: {
    type: String,
    default: '400px'
  }
})

const baseChart = ref(null)

const chartOption = computed(() => {
  return {
    title: {
      show: false // 카드 타이틀 사용
    },
    tooltip: {
      trigger: 'axis',
      formatter: (params) => {
        const point = params[0]
        return `${props.xAxisLabel}: ${point.axisValue}<br/>
                ${props.yAxisLabel}: ${point.value} nm`
      }
    },
    grid: {
      left: '10%',
      right: '5%',
      bottom: '15%',
      top: '10%'
    },
    xAxis: {
      type: 'category',
      name: props.xAxisLabel,
      nameLocation: 'middle',
      nameGap: 30,
      data: props.data.map(item => item.x)
    },
    yAxis: {
      type: 'value',
      name: props.yAxisLabel,
      nameLocation: 'middle',
      nameGap: 50
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'none',
      lineStyle: {
        color: '#1976D2',
        width: 2
      },
      areaStyle: {
        color: {
          type: 'linear',
          x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [
            { offset: 0, color: 'rgba(25, 118, 210, 0.3)' },
            { offset: 1, color: 'rgba(25, 118, 210, 0.05)' }
          ]
        }
      },
      data: props.data.map(item => item.y)
    }],
    dataZoom: [{
      type: 'inside',
      start: 0,
      end: 100
    }, {
      type: 'slider',
      start: 0,
      end: 100
    }]
  }
})

const exportChart = () => {
  if (baseChart.value && baseChart.value.chart) {
    const url = baseChart.value.chart.getDataURL({
      type: 'png',
      pixelRatio: 2,
      backgroundColor: '#fff'
    })

    const link = document.createElement('a')
    link.download = `${props.title}_${new Date().toISOString()}.png`
    link.href = url
    link.click()
  }
}
</script>
```

## Vue와 ECharts 통합 시 고려사항

### 차트 타입 선택 전략

ECharts는 다양한 차트 타입을 제공하며, 각 차트의 구체적인 구현 코드는 [ECharts 공식 홈페이지](https://echarts.apache.org/examples/)에서 확인할 수 있습니다.

**반도체 데이터 분석에 적합한 차트 타입들:**

- **히트맵 (Heatmap)**: AFM 표면 형상 데이터, 웨이퍼 맵 표시
- **산점도 (Scatter Plot)**: 측정값 분포, 상관관계 분석
- **박스플롯 (Box Plot)**: 데이터 분포와 이상치 파악
- **선 그래프**: 시간별 트렌드 분석
- **복합 차트**: 여러 데이터를 동시 비교

### **차트 선택 시 Vue 통합 관점에서 고려할 점**

**1. 데이터 업데이트 빈도**

```javascript
// 실시간 업데이트가 필요한 차트
const realtimeCharts = ["line", "bar"]; // 빠른 업데이트 가능

// 정적 분석용 차트
const staticCharts = ["heatmap", "boxplot"]; // 대용량 데이터 처리 우수
```

**2. 렌더링 성능**

```javascript
// 대용량 데이터용 설정
const performanceOption = {
  animation: false, // 애니메이션 비활성화로 성능 향상
  progressive: 1000, // 점진적 렌더링 임계값
  progressiveThreshold: 3000,
};
```

**3. 상호작용 복잡도**

```javascript
// 복잡한 상호작용이 필요한 경우
const interactiveCharts = {
  tooltip: true,
  dataZoom: true,
  brush: true, // 데이터 선택 기능
  legend: { type: "scroll" },
};
```

## **반응형 차트 구현 전략**

### **화면 크기 대응 방법**

Vuetify와 ECharts를 함께 사용할 때 반응형 차트를 구현할 수 있습니다.

**Vue Composition API를 활용한 반응형 감지**

```javascript
<script>

import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import { useDisplay } from 'vuetify'

const { mobile, tablet, desktop } = useDisplay()
const chartContainer = ref(null)
const chart = ref(null)

// Vuetify의 브레이크포인트를 활용한 반응형 옵션
const responsiveOption = computed(() => {
  const baseOption = {
    // 기본 차트 설정
  }

  // 모바일 최적화
  if (mobile.value) {
    return {
      ...baseOption,
      grid: { left: '15%', right: '5%', bottom: '25%' },
      legend: { orient: 'horizontal', bottom: 0 },
      tooltip: { trigger: 'axis' } // 모바일에서 더 쉬운 상호작용
    }
  }

  // 태블릿 최적화
  if (tablet.value) {
    return {
      ...baseOption,
      grid: { left: '12%', right: '8%', bottom: '15%' }
    }
  }

  // 데스크톱 기본 설정
  return baseOption
})

// 화면 크기 변경 시 차트 리사이즈
const handleResize = () => {
  if (chart.value) {
    chart.value.resize()
  }
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
})
</script>
```

### **성능 최적화와 메모리 관리**

Vue 애플리케이션에서 ECharts를 사용할 때 가장 중요한 부분입니다.

**대용량 데이터 처리 전략**

```javascript
<script setup>
import { ref, computed, onBeforeUnmount } from 'vue'

// 데이터 최적화를 위한 컴포저블 함수
const useChartDataOptimization = () => {
  const maxDataPoints = ref(1000)

  const optimizeData = (data) => {
    if (data.length <= maxDataPoints.value) return data

    // 다운샘플링: LTTB 알고리즘 적용
    const step = Math.ceil(data.length / maxDataPoints.value)
    return data.filter((_, index) => index % step === 0)
  }

  const getPerformanceOption = (baseOption, dataSize) => {
    if (dataSize > 5000) {
      return {
        ...baseOption,
        animation: false, // 대용량 데이터에서 애니메이션 비활성화
        series: baseOption.series.map(series => ({
          ...series,
          large: true,
          largeThreshold: 2000,
          progressive: 5000,
          progressiveThreshold: 10000
        }))
      }
    }
    return baseOption
  }

  return { optimizeData, getPerformanceOption }
}
</script>
```

**메모리 누수 방지**

```javascript
<script>

import { ref, onBeforeUnmount } from 'vue'

// 차트 인스턴스 관리 컴포저블
const useChartManager = () => {
  const charts = ref(new Map())

  const createChart = (id, container, option) => {
    // 기존 차트 정리
    if (charts.value.has(id)) {
      charts.value.get(id).dispose()
    }

    const chart = echarts.init(container)
    chart.setOption(option)
    charts.value.set(id, chart)

    return chart
  }

  const removeChart = (id) => {
    if (charts.value.has(id)) {
      charts.value.get(id).dispose()
      charts.value.delete(id)
    }
  }

  const cleanupAllCharts = () => {
    charts.value.forEach(chart => chart.dispose())
    charts.value.clear()
  }

  // 컴포넌트 언마운트 시 자동 정리
  onBeforeUnmount(() => {
    cleanupAllCharts()
  })

  return { charts, createChart, removeChart, cleanupAllCharts }
}
</script>
```

**데이터 업데이트 최적화**

```javascript
// 데이터 변경 감지 및 효율적 업데이트
const useChartDataUpdate = (chart) => {
  const updateChart = (newData, updateType = "replace") => {
    if (!chart.value) return;

    if (updateType === "append") {
      // 실시간 데이터 추가 (차트 전체 재렌더링 방지)
      chart.value.appendData({
        seriesIndex: 0,
        data: newData,
      });
    } else {
      // 전체 데이터 교체 (notMerge: false로 성능 향상)
      chart.value.setOption(
        {
          series: [{ data: newData }],
        },
        { notMerge: false, lazyUpdate: true }
      );
    }
  };

  return { updateChart };
};
```

**📊 원하는 형태로 Chart를 구현하는데는 많은 설정이 필요합니다. 초기에 학습을 위해서 직접 타이핑을 해가며 echarts 사용에 익숙해지는 게 중요합니다. 익숙해진 이후에는 ECharts 공식 홈페이지의 예제를 참고하여 구체적으로 어떻게 차트를 구성할 지 플랜을 작성하고, LLM의 도움을 받는게 효율적입니다.**
