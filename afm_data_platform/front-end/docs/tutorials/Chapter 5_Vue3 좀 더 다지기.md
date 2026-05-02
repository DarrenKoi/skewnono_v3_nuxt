# Vue 3 좀 더 다지기

이 장에서는 Vue 3의 더 고급 개념들을 배워보겠습니다. 이전 장에서 배운 기초 개념들을 바탕으로, 실제 개발에서 자주 사용되는 중요한 기능들을 살펴보겠습니다. 자세한 내용은 [Vue.js 공식 가이드 (한국어)](https://ko.vuejs.org/guide/introduction.html)를 참고하세요.

## Computed vs Watchers

Vue 3에서는 반응형 데이터를 다루는 두 가지 주요 방법이 있습니다. Computed와 Watchers는 비슷해 보이지만 사용 목적과 동작 방식이 다릅니다.

### Computed Properties (계산된 속성)

Computed는 다른 반응형 데이터를 기반으로 계산된 값을 반환합니다. 종속된 데이터가 변경될 때만 재계산되며, 결과를 캐싱합니다.

### 캐싱의 장점

Computed 속성의 캐싱은 다음과 같은 장점을 제공합니다:

**성능 최적화**

- 동일한 계산을 여러 번 수행하지 않고 결과를 재사용
- 템플릿에서 여러 번 참조해도 한 번만 계산됨
- 대용량 데이터 처리 시 특히 효과적

**효율적인 리소스 관리**

- 복잡한 연산(필터링, 정렬, 통계 계산 등)의 결과를 메모리에 저장
- 종속된 데이터가 변경될 때만 재계산하여 불필요한 연산 방지
- CPU 사용량 감소로 전체적인 애플리케이션 성능 향상

### Watchers (감시자)

Watchers는 특정 데이터의 변화를 감시하고, 변화가 발생했을 때 부수 효과(side effects)를 실행합니다. API 호출, 로깅, DOM 조작 등에 사용됩니다.

```javascript
import { ref, watch } from "vue";

const scanSpeed = ref(50);
const errorLog = ref([]);

// Watch - 스캔 속도 변화 감시 및 로깅
watch(scanSpeed, (newSpeed, oldSpeed) => {
  console.log(`스캔 속도 변경: ${oldSpeed} → ${newSpeed}`);

  // 부수 효과: API 호출
  updateEquipmentSettings({ speed: newSpeed });

  // 부수 효과: 에러 로깅
  if (newSpeed > 100) {
    errorLog.value.push({
      timestamp: new Date(),
      message: `위험: 스캔 속도가 ${newSpeed}로 설정됨`,
    });
  }
});
```

### Watch의 반환값과 감시 제어

Watch는 기본적으로 콜백 함수에서 반환값이 없지만, watch 함수 자체는 감시를 중단할 수 있는 함수를 반환합니다.

```javascript
// watch는 stop 함수를 반환
const stopWatching = watch(scanSpeed, (newValue) => {
  console.log("속도 변경:", newValue);
  // 콜백 함수는 반환값 없음 - 부수 효과만 실행
});

// 필요 시 감시 중단
stopWatching(); // 더 이상 scanSpeed 변화를 감시하지 않음
```

**조건부 감시 예제**

```javascript
import { ref, watch, onBeforeUnmount } from "vue";

const temperature = ref(25);
const isMonitoring = ref(true);

// 조건부 감시 구현
let stopTempWatch = null;

watch(isMonitoring, (shouldMonitor) => {
  if (shouldMonitor) {
    // 모니터링 시작
    stopTempWatch = watch(temperature, (newTemp) => {
      if (newTemp > 30) {
        console.warn("온도가 너무 높습니다!");
        sendAlert("high-temperature", newTemp);
      }
    });
  } else {
    // 모니터링 중단
    if (stopTempWatch) {
      stopTempWatch();
      stopTempWatch = null;
    }
  }
});

// 컴포넌트 정리 시 감시 중단
onBeforeUnmount(() => {
  if (stopTempWatch) {
    stopTempWatch();
  }
});
```

### Watch의 고급 옵션

```javascript
// 1. immediate: 즉시 실행
watch(
  dataSource,
  (newValue) => {
    loadData(newValue);
  },
  { immediate: true } // 컴포넌트 생성 시 즉시 한 번 실행
);

// 2. deep: 깊은 감시 (객체 내부 변화 감지)
const afmSettings = ref({
  speed: 50,
  resolution: 512,
  mode: "contact",
});

watch(
  afmSettings,
  (newSettings) => {
    console.log("설정 변경됨:", newSettings);
    saveSettings(newSettings);
  },
  { deep: true } // 객체 내부 속성 변화도 감시
);

// 3. flush: 실행 타이밍 제어
watch(
  source,
  (newValue) => {
    updateDOM();
  },
  {
    flush: "post", // 'pre' (기본값), 'post' (DOM 업데이트 후), 'sync' (동기적)
  }
);
```

### WatchEffect - 자동 종속성 추적

`watchEffect`는 내부에서 사용하는 반응형 값들을 자동으로 추적합니다.

```javascript
import { ref, watchEffect } from "vue";

const temperature = ref(25);
const humidity = ref(60);
const pressure = ref(1013);

// 자동으로 사용된 반응형 값들을 감시
const stop = watchEffect(() => {
  // 내부에서 사용하는 값들을 자동으로 추적
  console.log(
    `환경 조건: 온도 ${temperature.value}°C, 습도 ${humidity.value}%, 압력 ${pressure.value}hPa`
  );

  // 조건에 따른 경고
  if (temperature.value > 30 || humidity.value > 80) {
    console.warn("측정 환경이 적절하지 않습니다");
  }
});

// vs watch - 명시적으로 감시 대상 지정
watch([temperature, humidity, pressure], ([newTemp, newHumid, newPress]) => {
  console.log(
    `환경 조건: 온도 ${newTemp}°C, 습도 ${newHumid}%, 압력 ${newPress}hPa`
  );
});
```

### Computed vs Watch 비교

| 특징          | Computed           | Watch                    |
| ------------- | ------------------ | ------------------------ |
| **주요 용도** | 파생된 상태 계산   | 부수 효과 실행           |
| **반환값**    | 계산된 값 반환     | 반환값 없음              |
| **캐싱**      | 결과를 캐싱함      | 캐싱하지 않음            |
| **실행 시점** | 종속성이 변경될 때 | 감시 대상이 변경될 때    |
| **사용 예시** | 필터링, 정렬, 계산 | API 호출, 로깅, DOM 조작 |

```javascript
// 실제 사용 예제: AFM 데이터 대시보드
import { ref, computed, watch } from "vue";

const rawData = ref([]);
const filterThreshold = ref(10);

// ✅ Computed 사용이 적절한 경우
const filteredData = computed(() => {
  return rawData.value.filter((d) => d.value > filterThreshold.value);
});

const dataStatistics = computed(() => {
  return {
    total: rawData.value.length,
    filtered: filteredData.value.length,
    percentage: (
      (filteredData.value.length / rawData.value.length) *
      100
    ).toFixed(2),
  };
});

// ✅ Watch 사용이 적절한 경우
watch(filterThreshold, async (newThreshold) => {
  // 서버에 새로운 임계값 저장
  await saveThresholdToServer(newThreshold);

  // 사용자에게 알림
  showNotification(`필터 임계값이 ${newThreshold}로 변경되었습니다`);
});

// ❌ 잘못된 사용 예시 - Watch로 계산된 값 만들기
let wrongFilteredData = [];
watch(rawData, (newData) => {
  // 이런 경우는 computed를 사용해야 함
  wrongFilteredData = newData.filter((d) => d.value > 10);
});
```

## Props와 Emits (컴포넌트 통신)

Vue의 컴포넌트는 독립적이고 재사용 가능한 단위입니다. Props와 Emits는 이러한 컴포넌트들 간에 데이터를 주고받는 공식적인 방법입니다.

### Props 심화 이해

Props는 부모 컴포넌트에서 자식 컴포넌트로 데이터를 전달하는 단방향 통신 방법입니다.

```javascript
// MeasurementDisplay.vue - 자식 컴포넌트
const props = defineProps({
  // 기본 타입 정의
  title: String,

  // 상세 설정
  measurement: {
    type: Object,
    required: true,
    // 객체/배열의 기본값은 함수로 반환
    default: () => ({
      value: 0,
      unit: "nm",
    }),
  },

  // 커스텀 검증
  threshold: {
    type: Number,
    validator: (value) => {
      return value >= 0 && value <= 100;
    },
  },

  // 여러 타입 허용
  id: [String, Number],

  // 복잡한 타입 정의
  config: {
    type: Object,
    default: () => ({}),
    // 객체 속성 검증
    validator: (config) => {
      return (
        config.hasOwnProperty("mode") &&
        ["auto", "manual"].includes(config.mode)
      );
    },
  },
});

// Props는 읽기 전용!
// ❌ 잘못된 사용
props.measurement.value = 100; // 이렇게 직접 수정하면 안 됨

// ✅ 올바른 사용 - 로컬 복사본 만들기
const localMeasurement = ref({ ...props.measurement });
localMeasurement.value.value = 100; // 로컬 복사본은 수정 가능
```

### Props 전달 패턴

```javascript
// 부모 컴포넌트 템플릿
<template>
  <div>
    <!-- 정적 Props -->
    <MeasurementDisplay
      title="표면 거칠기"
      unit="nm"
    />

    <!-- 동적 Props (v-bind 사용) -->
    <MeasurementDisplay
      :title="dynamicTitle"
      :measurement="currentMeasurement"
      :threshold="warningThreshold"
    />

    <!-- 객체 전체를 Props로 전달 -->
    <MeasurementDisplay v-bind="measurementProps" />
  </div>
</template>

// 부모 컴포넌트 스크립트
<script setup>
const dynamicTitle = ref('실시간 측정')
const currentMeasurement = ref({ value: 23.5, unit: 'nm' })
const warningThreshold = ref(50)

const measurementProps = {
  title: 'Z축 높이',
  measurement: { value: 45.2, unit: 'nm' },
  threshold: 60
}
</script>
```

### Emits 심화 이해

Emits는 자식 컴포넌트에서 부모 컴포넌트로 이벤트를 전달하는 방법입니다.

```javascript
// ControlPanel.vue - 자식 컴포넌트
// 이벤트 정의 및 검증
const emit = defineEmits({
  // 간단한 이벤트
  start: null,

  // 페이로드 검증
  update: (payload) => {
    // 검증 로직 - true 반환하면 유효
    return payload && typeof payload.value === "number" && payload.value >= 0;
  },

  // 여러 파라미터를 가진 이벤트
  change: (id, value, timestamp) => {
    return (
      typeof id === "string" &&
      typeof value === "number" &&
      timestamp instanceof Date
    );
  },
});

// 이벤트 발생시키기
function handleStart() {
  // 단순 이벤트
  emit("start");

  // 페이로드와 함께
  emit("update", {
    value: 42.5,
    unit: "nm",
    timestamp: new Date(),
  });

  // 여러 파라미터와 함께
  emit("change", "sensor-01", 23.4, new Date());
}
```

### 양방향 바인딩 패턴 (v-model)

Props와 Emits를 조합하여 양방향 바인딩을 구현할 수 있습니다.

```javascript
// CustomInput.vue - 자식 컴포넌트 템플릿
<template>
  <input
    :value="modelValue"
    @input="$emit('update:modelValue', $event.target.value)"
  />
</template>

// CustomInput.vue - 자식 컴포넌트 스크립트
<script setup>
defineProps(['modelValue'])
defineEmits(['update:modelValue'])
</script>

// 부모 컴포넌트에서 사용
<template>
  <CustomInput v-model="searchQuery" />
  <!-- 위는 아래와 동일 -->
  <CustomInput
    :modelValue="searchQuery"
    @update:modelValue="searchQuery = $event"
  />
</template>
```

### 실제 활용 예제: AFM 설정 패널

```javascript
// AFMSettingsPanel.vue - 자식 컴포넌트 템플릿
<template>
  <div class="settings-panel">
    <h3>{{ title }}</h3>

    <div class="setting-item">
      <label>스캔 속도</label>
      <input
        :value="settings.scanSpeed"
        @input="updateSetting('scanSpeed', $event.target.value)"
        type="number"
      />
    </div>

    <div class="setting-item">
      <label>해상도</label>
      <select
        :value="settings.resolution"
        @change="updateSetting('resolution', $event.target.value)"
      >
        <option value="256">256x256</option>
        <option value="512">512x512</option>
        <option value="1024">1024x1024</option>
      </select>
    </div>

    <button @click="applySettings">적용</button>
    <button @click="resetSettings">초기화</button>
  </div>
</template>

// AFMSettingsPanel.vue - 자식 컴포넌트 스크립트
<script setup>
import { ref, watch } from 'vue'

// Props 정의
const props = defineProps({
  title: {
    type: String,
    default: 'AFM 설정'
  },
  initialSettings: {
    type: Object,
    required: true
  }
})

// Emits 정의
const emit = defineEmits(['update', 'apply', 'reset'])

// 로컬 상태
const settings = ref({ ...props.initialSettings })

// Props 변경 감시
watch(() => props.initialSettings, (newSettings) => {
  settings.value = { ...newSettings }
}, { deep: true })

// 메서드
function updateSetting(key, value) {
  settings.value[key] = Number(value)

  // 부모에게 변경 사항 알림
  emit('update', {
    key,
    value: settings.value[key],
    allSettings: { ...settings.value }
  })
}

function applySettings() {
  emit('apply', { ...settings.value })
}

function resetSettings() {
  settings.value = { ...props.initialSettings }
  emit('reset')
}
</script>

// 부모 컴포넌트에서 사용 - 템플릿
<template>
  <AFMSettingsPanel
    :initial-settings="defaultSettings"
    @update="handleSettingUpdate"
    @apply="applySettingsToEquipment"
    @reset="handleReset"
  />
</template>

// 부모 컴포넌트에서 사용 - 스크립트
<script setup>
const defaultSettings = ref({
  scanSpeed: 50,
  resolution: 512,
  force: 1.5
})

function handleSettingUpdate(data) {
  console.log(`설정 변경: ${data.key} = ${data.value}`)
}

async function applySettingsToEquipment(settings) {
  try {
    await sendSettingsToAFM(settings)
    showNotification('설정이 적용되었습니다', 'success')
  } catch (error) {
    showNotification('설정 적용 실패', 'error')
  }
}

function handleReset() {
  console.log('설정이 초기화되었습니다')
}
</script>
```

## 생명주기 (Lifecycle) 이해와 활용

### 생명주기가 중요한 이유

Vue 컴포넌트의 생명주기를 이해하면 적절한 시점에 필요한 작업을 수행할 수 있습니다. 특히 다음과 같은 상황에서 중요합니다:

1. **리소스 관리**: 타이머, WebSocket 연결, 이벤트 리스너 등의 정리
2. **외부 라이브러리 통합**: DOM이 준비된 후 차트 라이브러리 초기화
3. **데이터 로딩**: 컴포넌트가 표시될 때 API 호출
4. **메모리 누수 방지**: 사용하지 않는 리소스 정리

### 주요 생명주기 훅과 사용 시점

```javascript
import {
  onBeforeMount,
  onMounted,
  onBeforeUpdate,
  onUpdated,
  onBeforeUnmount,
  onUnmounted,
  ref,
} from "vue";

// AFM 실시간 모니터링 컴포넌트
export default {
  setup() {
    const chartInstance = ref(null);
    const websocket = ref(null);
    const updateTimer = ref(null);

    // 1. onBeforeMount - DOM 생성 전
    onBeforeMount(() => {
      console.log("컴포넌트 마운트 준비");
      // DOM에 접근할 수 없음
      // 초기 데이터 준비, 설정 로드 등
    });

    // 2. onMounted - DOM 생성 후 (가장 많이 사용)
    onMounted(() => {
      // ✅ DOM 요소 접근 가능
      initializeChart();

      // ✅ 외부 라이브러리 초기화
      chartInstance.value = new ECharts(document.getElementById("chart"));

      // ✅ API 호출
      loadInitialData();

      // ✅ 이벤트 리스너 등록
      window.addEventListener("resize", handleResize);

      // ✅ 실시간 연결 시작
      connectWebSocket();
    });

    // 3. onBeforeUpdate - 재렌더링 전
    onBeforeUpdate(() => {
      // DOM 업데이트 전 현재 상태 저장
      saveScrollPosition();
    });

    // 4. onUpdated - 재렌더링 후
    onUpdated(() => {
      // DOM 업데이트 후 작업
      restoreScrollPosition();

      // 차트 업데이트
      if (chartInstance.value) {
        chartInstance.value.update();
      }
    });

    // 5. onBeforeUnmount - 컴포넌트 제거 전 (중요!)
    onBeforeUnmount(() => {
      // ✅ 타이머 정리
      if (updateTimer.value) {
        clearInterval(updateTimer.value);
      }

      // ✅ 이벤트 리스너 제거
      window.removeEventListener("resize", handleResize);

      // ✅ WebSocket 연결 종료
      if (websocket.value) {
        websocket.value.close();
      }

      // ✅ 진행 중인 API 요청 취소
      cancelPendingRequests();
    });

    // 6. onUnmounted - 컴포넌트 제거 후
    onUnmounted(() => {
      // 최종 정리 작업
      console.log("컴포넌트가 완전히 제거되었습니다");
    });

    // 메서드들
    function initializeChart() {
      // 차트 초기화 로직
    }

    function connectWebSocket() {
      websocket.value = new WebSocket("ws://afm-server/realtime");

      websocket.value.onmessage = (event) => {
        // 실시간 데이터 처리
      };
    }

    function handleResize() {
      if (chartInstance.value) {
        chartInstance.value.resize();
      }
    }
  },
};
```

### 페이지 이동 시 생명주기

Vue Router를 사용한 페이지 이동 시 컴포넌트의 생명주기는 다음과 같이 동작합니다:

```javascript
// 페이지 A에서 페이지 B로 이동하는 경우
// 1. 페이지 A 컴포넌트: onBeforeUnmount 호출
// 2. 페이지 A 컴포넌트: onUnmounted 호출
// 3. 페이지 B 컴포넌트: onBeforeMount 호출
// 4. 페이지 B 컴포넌트: onMounted 호출

// RouteGuard와 함께 사용하는 예제
import { onBeforeRouteLeave } from "vue-router";

export default {
  setup() {
    const hasUnsavedChanges = ref(false);

    // 라우트 이탈 전 확인
    onBeforeRouteLeave((to, from, next) => {
      if (hasUnsavedChanges.value) {
        const answer = window.confirm(
          "저장하지 않은 변경사항이 있습니다. 정말 나가시겠습니까?"
        );
        if (answer) {
          next();
        } else {
          next(false);
        }
      } else {
        next();
      }
    });

    // 컴포넌트 언마운트 시 정리
    onBeforeUnmount(() => {
      // 자동 저장
      if (hasUnsavedChanges.value) {
        saveDataToLocalStorage();
      }

      // 리소스 정리
      cleanupResources();
    });
  },
};
```

### 실제 프로젝트에서의 생명주기 활용 예시

```javascript
// AFMDataViewer.vue - 실제 활용 예제 템플릿
<template>
  <div class="afm-data-viewer">
    <div ref="chartContainer" class="chart-container"></div>
    <div v-if="loading" class="loading-overlay">
      데이터 로딩 중...
    </div>
  </div>
</template>

// AFMDataViewer.vue - 실제 활용 예제 스크립트
<script setup>
import { ref, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import * as echarts from 'echarts'

// 상태
const chartContainer = ref(null)
const chartInstance = ref(null)
const loading = ref(true)
const dataUpdateInterval = ref(null)
const resizeObserver = ref(null)

// 마운트 시 초기화
onMounted(async () => {
  try {
    // 1. 차트 인스턴스 생성
    chartInstance.value = echarts.init(chartContainer.value)

    // 2. 초기 데이터 로드
    const data = await fetchAFMData()
    updateChart(data)

    // 3. 실시간 업데이트 시작
    startRealtimeUpdate()

    // 4. ResizeObserver로 반응형 차트 구현
    resizeObserver.value = new ResizeObserver(() => {
      chartInstance.value?.resize()
    })
    resizeObserver.value.observe(chartContainer.value)

    loading.value = false
  } catch (error) {
    console.error('차트 초기화 실패:', error)
    showErrorNotification('데이터 로드 실패')
  }
})

// 언마운트 전 정리 (메모리 누수 방지)
onBeforeUnmount(() => {
  // 1. 차트 인스턴스 제거
  if (chartInstance.value) {
    chartInstance.value.dispose()
    chartInstance.value = null
  }

  // 2. 실시간 업데이트 중지
  if (dataUpdateInterval.value) {
    clearInterval(dataUpdateInterval.value)
    dataUpdateInterval.value = null
  }

  // 3. ResizeObserver 정리
  if (resizeObserver.value) {
    resizeObserver.value.disconnect()
    resizeObserver.value = null
  }

  // 4. 진행 중인 API 요청 취소
  abortController?.abort()
})

// keep-alive 사용 시
onActivated(() => {
  // 컴포넌트가 다시 활성화될 때
  if (chartInstance.value) {
    chartInstance.value.resize()
  }
  startRealtimeUpdate()
})

onDeactivated(() => {
  // 컴포넌트가 비활성화될 때
  stopRealtimeUpdate()
})

// 헬퍼 함수들
function startRealtimeUpdate() {
  dataUpdateInterval.value = setInterval(async () => {
    const newData = await fetchLatestAFMData()
    updateChart(newData)
  }, 5000)
}

function stopRealtimeUpdate() {
  if (dataUpdateInterval.value) {
    clearInterval(dataUpdateInterval.value)
    dataUpdateInterval.value = null
  }
}

async function fetchAFMData() {
  // API 호출 로직
}

function updateChart(data) {
  if (chartInstance.value) {
    chartInstance.value.setOption({
      // 차트 옵션
    })
  }
}
</script>
```

## 정리

이 장에서 배운 내용을 정리하면:

1. **Computed vs Watch**

   - Computed: 파생된 상태 계산, 캐싱, 반환값 있음
   - Watch: 부수 효과 실행, 캐싱 없음, 반환값 없음

2. **Props와 Emits**

   - Props: 부모→자식 단방향 데이터 전달, 읽기 전용
   - Emits: 자식→부모 이벤트 전달, 검증 가능
   - v-model: Props와 Emits를 조합한 양방향 바인딩

3. **생명주기**
   - 리소스 관리와 메모리 누수 방지에 필수
   - onMounted: DOM 접근, 외부 라이브러리 초기화
   - onBeforeUnmount: 타이머, 리스너, 연결 정리
   - 페이지 이동 시 컴포넌트 생명주기 이해

이러한 개념들을 잘 이해하고 활용하면 더 효율적이고 안정적인 Vue 애플리케이션을 개발할 수 있습니다. 특히 AFM 데이터 뷰어와 같은 실시간 데이터를 다루는 애플리케이션에서는 생명주기 관리가 매우 중요합니다.

다음 장에서는 Vuetify를 사용한 UI 구성에 대해 배워보겠습니다.
