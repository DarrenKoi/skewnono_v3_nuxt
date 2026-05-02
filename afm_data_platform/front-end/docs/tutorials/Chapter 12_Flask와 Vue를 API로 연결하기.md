# Chapter 11: Flask와 Vue를 API로 연결하기

## 들어가며

웹 애플리케이션은 프론트엔드와 백엔드가 서로 통신하며 작동합니다. 이 장에서는 Flask 백엔드와 Vue.js 프론트엔드를 API를 통해 연결하는 방법을 배우고, 특히 **환경별 설정 관리의 중요성**을 이해하게 됩니다.

## 1. 전체 아키텍처 이해

### 1.1 시스템 구조

```text
┌─────────────────┐    HTTP Request     ┌──────────────────┐
│                 │ ──────────────────► │                  │
│   Vue.js        │                     │   Flask API      │
│   Frontend      │ ◄────────────────── │   Backend        │
│   (Port 3000)   │    JSON Response    │   (Port 5000)    │
└─────────────────┘                     └──────────────────┘
```

- **프론트엔드 (Vue.js)**: 사용자 인터페이스, 데이터 시각화
- **백엔드 (Flask)**: 데이터 처리, 비즈니스 로직, 파일 관리
- **API**: RESTful API를 통한 JSON 데이터 교환
- **CORS**: Cross-Origin Resource Sharing 설정으로 서로 다른 포트 간 통신 허용

### 1.2 WSGI 이해하기 (Flask 운영 환경)

WSGI(Web Server Gateway Interface)는 Python 웹 애플리케이션의 표준 인터페이스입니다. 이를 전기 규격에 비유하면:

- **WSGI**: 전기 규격 (220V, 60Hz) - 표준 인터페이스
- **웹 서버 (Gunicorn, uWSGI)**: 발전소와 콘센트 - HTTP 요청을 받아 처리
- **Flask**: TV나 냉장고 같은 가전제품 - 실제 애플리케이션 로직

이 표준 덕분에 Flask 애플리케이션을 다양한 웹 서버에서 실행할 수 있습니다. 회사 내에서는 주로 uWSGI를 사용하며, `uwsgi.ini` 파일을 통해 세부 설정을 관리합니다.

## 2. Flask API 서버 구축

### 2.1 기본 Flask 서버 설정

```python
# app.py
from flask import Flask, jsonify, request
from flask_cors import CORS
import os
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

app = Flask(__name__)

# 환경별 CORS 설정 - 이것이 왜 중요한지 설명합니다
is_development = os.getenv('FLASK_ENV') == 'development'

if is_development:
    # 개발 환경: localhost 허용
    origins = os.getenv('DEV_CORS_ORIGINS', 'http://localhost:3000').split(',')
    print("* 개발 모드 실행 중. 허용된 Origins:", origins)
else:
    # 운영 환경: 실제 도메인만 허용
    origins = os.getenv('PROD_CORS_ORIGINS', 'https://afm.skhynix.com').split(',')
    print("* 운영 모드 실행 중. 허용된 Origins:", origins)

CORS(app, resources={r"/api/*": {"origins": origins}}, supports_credentials=True)

# 기본 헬스체크 엔드포인트
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'success',
        'message': 'Flask API 서버가 정상 작동 중입니다',
        'environment': os.getenv('FLASK_ENV', 'production')
    })

if __name__ == '__main__':
    app.run(debug=is_development, port=5000)
```

### 2.2 환경 변수 설정 (.env 파일의 중요성)

**.env 파일을 사용하는 이유:**

1. **보안**: API 키, 비밀번호 등을 코드에서 분리
2. **유연성**: 코드 수정 없이 환경별 설정 변경
3. **협업**: 각 개발자가 자신만의 설정 사용 가능
4. **배포**: 서버별로 다른 설정 적용 가능

```bash
# .env 파일 (Git에 포함시키지 않음!)

# Flask 환경 설정
FLASK_ENV=development

# 개발 환경 CORS 설정
DEV_CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# 운영 환경 CORS 설정
PROD_CORS_ORIGINS=https://afm.skhynix.com

# 비밀 키 (세션, CSRF 보호용)
SECRET_KEY=your-secret-key-here

# 데이터베이스 설정 (예시)
DATABASE_URL=sqlite:///dev.db
```

### 2.3 AFM 데이터 API 구현

```python
# app.py에 추가
from datetime import datetime

# AFM 측정 데이터 API
@app.route('/api/afm-files', methods=['GET'])
def get_afm_files():
    """AFM 측정 파일 목록을 반환합니다"""
    try:
        # 실제로는 데이터베이스나 파일에서 읽어옴
        dummy_afm_data = [
            {
                'id': 1,
                'filename': '240618_FSOXCMP_DISHING_9PT_T7HQR42TA_21_1',
                'recipe_name': 'FSOXCMP_DISHING_9PT',
                'lot_id': 'T7HQR42TA',
                'date': '2024-06-18',
                'roughness': 1.2,
                'tool': 'MAP608'
            },
            {
                'id': 2,
                'filename': '240617_OXIDE_ETCH_3PT_T8HQR43TB_15_1',
                'recipe_name': 'OXIDE_ETCH_3PT',
                'lot_id': 'T8HQR43TB',
                'date': '2024-06-17',
                'roughness': 2.1,
                'tool': 'MAP608'
            }
        ]

        # 검색 기능
        search = request.args.get('search', '')
        if search:
            dummy_afm_data = [
                item for item in dummy_afm_data
                if search.lower() in item['filename'].lower() or
                   search.lower() in item['recipe_name'].lower()
            ]

        return jsonify({
            'success': True,
            'data': dummy_afm_data,
            'total_count': len(dummy_afm_data),
            'timestamp': datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'데이터 조회 중 오류: {str(e)}'
        }), 500

# 특정 AFM 파일의 상세 데이터
@app.route('/api/afm-files/<int:file_id>', methods=['GET'])
def get_afm_file_detail(file_id):
    """특정 AFM 파일의 상세 정보를 반환합니다"""
    try:
        # 실제로는 데이터베이스에서 조회
        if file_id == 1:
            detailed_data = {
                'id': 1,
                'filename': '240618_FSOXCMP_DISHING_9PT_T7HQR42TA_21_1',
                'recipe_name': 'FSOXCMP_DISHING_9PT',
                'lot_id': 'T7HQR42TA',
                'date': '2024-06-18',
                'summary': {
                    'mean_roughness': 1.2,
                    'std_roughness': 0.15,
                    'min_roughness': 0.9,
                    'max_roughness': 1.5
                },
                'measurement_points': ['1_UL', '2_UC', '3_UR', '4_ML', '5_MC'],
                'profile_available': True
            }

            return jsonify({
                'success': True,
                'data': detailed_data
            })
        else:
            return jsonify({
                'success': False,
                'error': f'ID {file_id}인 파일을 찾을 수 없습니다'
            }), 404

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'파일 상세 정보 조회 중 오류: {str(e)}'
        }), 500
```

## 3. Vue.js에서 API 통신하기

### 3.1 Vue 환경 변수 설정

Vue에서도 환경별 설정을 관리하는 것이 중요합니다. **주의: Vite를 사용하는 Vue 프로젝트에서는 반드시 `VITE_` 접두사를 붙여야 환경 변수를 사용할 수 있습니다.**

```bash
# .env.development (개발 환경)
VITE_API_BASE_URL=http://localhost:5000/api
VITE_APP_TITLE=AFM Data Platform (Development)

# .env.production (운영 환경)
VITE_API_BASE_URL=https://afm.skhynix.com/api
VITE_APP_TITLE=AFM Data Platform
```

환경 변수 사용 시 주의사항:

- 반드시 `VITE_` 접두사 사용
- `import.meta.env.VITE_변수명` 형태로 접근
- `.env` 파일 수정 후 개발 서버 재시작 필요

### 3.2 Axios를 사용한 API 서비스

```javascript
// src/services/api.js
import axios from "axios";

// 환경 변수에서 API URL 가져오기
const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:5000/api";

console.log("API Base URL:", API_BASE_URL);

// Axios 인스턴스 생성
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
  headers: {
    "Content-Type": "application/json",
  },
});

// 요청 인터셉터 (디버깅용)
apiClient.interceptors.request.use(
  (config) => {
    console.log(`📡 API 요청: ${config.method.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error("❌ 요청 오류:", error);
    return Promise.reject(error);
  }
);

// 응답 인터셉터 (에러 처리)
apiClient.interceptors.response.use(
  (response) => {
    console.log(`✅ API 응답: ${response.config.url}`, response.data);
    return response;
  },
  (error) => {
    console.error("❌ 응답 오류:", error);

    // 네트워크 오류 처리
    if (!error.response) {
      error.message = "서버에 연결할 수 없습니다. 네트워크를 확인해주세요.";
    } else {
      // HTTP 상태 코드별 처리
      switch (error.response.status) {
        case 404:
          error.message = "요청한 데이터를 찾을 수 없습니다.";
          break;
        case 500:
          error.message = "서버 내부 오류가 발생했습니다.";
          break;
        default:
          error.message =
            error.response.data?.error || "알 수 없는 오류가 발생했습니다.";
      }
    }

    return Promise.reject(error);
  }
);

// API 서비스 함수들
export const apiService = {
  // 헬스체크
  async healthCheck() {
    try {
      const response = await apiClient.get("/health");
      return {
        success: true,
        data: response.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
      };
    }
  },

  // AFM 파일 목록 조회
  async getAfmFiles(search = "") {
    try {
      const response = await apiClient.get("/afm-files", {
        params: { search },
      });
      return {
        success: true,
        data: response.data.data,
        totalCount: response.data.total_count,
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
        data: [],
      };
    }
  },

  // AFM 파일 상세 정보 조회
  async getAfmFileDetail(fileId) {
    try {
      const response = await apiClient.get(`/afm-files/${fileId}`);
      return {
        success: true,
        data: response.data.data,
      };
    } catch (error) {
      return {
        success: false,
        error: error.message,
      };
    }
  },
};

export default apiClient;
```

### 3.3 Pinia Store에서 API 사용

```javascript
// src/stores/dataStore.js
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import { apiService } from "@/services/api.js";

export const useDataStore = defineStore("data", () => {
  // 상태
  const measurements = ref([]);
  const isLoading = ref(false);
  const error = ref(null);
  const lastUpdated = ref(null);

  // 계산된 속성
  const measurementCount = computed(() => measurements.value.length);

  const averageRoughness = computed(() => {
    if (measurements.value.length === 0) return 0;
    const sum = measurements.value.reduce((acc, m) => acc + m.roughness, 0);
    return (sum / measurements.value.length).toFixed(2);
  });

  // AFM 파일 목록 로드
  async function loadMeasurements(search = "") {
    isLoading.value = true;
    error.value = null;

    try {
      console.log("📊 AFM 측정 파일 목록을 로드합니다...");

      const result = await apiService.getAfmFiles(search);

      if (result.success) {
        measurements.value = result.data;
        lastUpdated.value = new Date();
        console.log(`✅ ${result.data.length}개의 측정 파일을 로드했습니다`);
      } else {
        throw new Error(result.error);
      }
    } catch (err) {
      error.value = err.message;
      console.error("❌ 측정 파일 로드 실패:", err);

      // 사용자에게 친화적인 에러 메시지
      if (err.message.includes("네트워크")) {
        error.value = "Flask 서버가 실행 중인지 확인해주세요 (포트 5000)";
      }
    } finally {
      isLoading.value = false;
    }
  }

  // 특정 측정 파일의 상세 데이터 로드
  async function loadMeasurementDetail(fileId) {
    try {
      console.log(`📊 측정 파일 상세 정보 로드: ${fileId}`);

      const result = await apiService.getAfmFileDetail(fileId);

      if (result.success) {
        console.log(`✅ 파일 ${fileId} 상세 정보 로드 완료`);
        return result.data;
      } else {
        throw new Error(result.error);
      }
    } catch (err) {
      console.error(`❌ 파일 ${fileId} 상세 정보 로드 실패:`, err);
      throw err;
    }
  }

  // 데이터 초기화
  function clearData() {
    measurements.value = [];
    error.value = null;
    lastUpdated.value = null;
  }

  return {
    // 상태
    measurements,
    isLoading,
    error,
    lastUpdated,

    // 계산된 속성
    measurementCount,
    averageRoughness,

    // 액션
    loadMeasurements,
    loadMeasurementDetail,
    clearData,
  };
});
```

## 4. 실전 예제: AFM 데이터 대시보드

### 4.1 메인 페이지 컴포넌트

```javascript
// src/pages/AfmDashboard.vue
<template>
  <div class="afm-dashboard">
    <h1>AFM 측정 데이터 대시보드</h1>

    <!-- 환경 정보 표시 -->
    <div class="environment-info" v-if="isDevelopment">
      <v-alert type="info" variant="tonal">
        개발 모드로 실행 중 (API: {{ apiUrl }})
      </v-alert>
    </div>

    <!-- 검색 바 -->
    <div class="search-section">
      <v-text-field
        v-model="searchQuery"
        @input="onSearch"
        placeholder="파일명이나 레시피로 검색..."
        prepend-inner-icon="mdi-magnify"
        clearable
        @click:clear="onSearch"
      />
    </div>

    <!-- 통계 카드 -->
    <v-row class="mb-4">
      <v-col cols="12" sm="6" md="3">
        <v-card>
          <v-card-text>
            <div class="text-h5">{{ dataStore.measurementCount }}</div>
            <div class="text-caption">총 측정 수</div>
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card>
          <v-card-text>
            <div class="text-h5">{{ dataStore.averageRoughness }} nm</div>
            <div class="text-caption">평균 거칠기</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- 로딩 상태 -->
    <div v-if="dataStore.isLoading" class="text-center pa-4">
      <v-progress-circular indeterminate color="primary" />
      <p class="mt-2">데이터를 불러오는 중...</p>
    </div>

    <!-- 에러 상태 -->
    <v-alert
      v-else-if="dataStore.error"
      type="error"
      variant="outlined"
      class="mb-4"
    >
      <div class="d-flex align-center justify-space-between">
        <div>
          <div class="text-h6">오류 발생</div>
          <div>{{ dataStore.error }}</div>
        </div>
        <v-btn @click="refreshData" color="error" variant="text">
          다시 시도
        </v-btn>
      </div>
    </v-alert>

    <!-- 데이터 목록 -->
    <div v-else class="data-grid">
      <v-row>
        <v-col
          v-for="item in dataStore.measurements"
          :key="item.id"
          cols="12"
          sm="6"
          md="4"
        >
          <MeasurementCard
            :measurement="item"
            @click="viewDetail(item.id)"
          />
        </v-col>
      </v-row>

      <!-- 데이터가 없을 때 -->
      <div v-if="dataStore.measurements.length === 0" class="text-center pa-8">
        <v-icon size="64" color="grey">mdi-database-off</v-icon>
        <p class="text-h6 mt-4">측정 데이터가 없습니다</p>
        <p class="text-caption">검색 조건을 변경해보세요</p>
      </div>
    </div>

    <!-- 마지막 업데이트 시간 -->
    <div v-if="dataStore.lastUpdated" class="text-caption text-center mt-4">
      마지막 업데이트: {{ formatDate(dataStore.lastUpdated) }}
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useDataStore } from '@/stores/dataStore.js'
import MeasurementCard from '@/components/MeasurementCard.vue'
import { debounce } from 'lodash-es'

const router = useRouter()
const dataStore = useDataStore()
const searchQuery = ref('')

// 환경 정보
const isDevelopment = import.meta.env.DEV
const apiUrl = import.meta.env.VITE_API_BASE_URL

// 디바운스된 검색 함수 (과도한 API 호출 방지)
const debouncedSearch = debounce((query) => {
  dataStore.loadMeasurements(query)
}, 500)

function onSearch() {
  debouncedSearch(searchQuery.value)
}

function refreshData() {
  dataStore.loadMeasurements(searchQuery.value)
}

function viewDetail(fileId) {
  router.push(`/afm-detail/${fileId}`)
}

function formatDate(date) {
  return new Date(date).toLocaleString('ko-KR')
}

// 페이지 로드 시 데이터 가져오기
onMounted(() => {
  console.log('AFM 대시보드 마운트됨')
  dataStore.loadMeasurements()
})
</script>

<style scoped>
.afm-dashboard {
  padding: 20px;
}

.environment-info {
  margin-bottom: 20px;
}

.search-section {
  max-width: 600px;
  margin: 0 auto 20px;
}

.data-grid {
  min-height: 400px;
}
</style>
```

## 5. 환경별 배포 전략

### 5.1 개발 환경에서 실행

```bash
# Flask 서버 실행 (터미널 1)
cd backend
python app.py

# Vue 개발 서버 실행 (터미널 2)
cd frontend
npm run dev
```

### 5.2 운영 환경 배포

```bash
# Flask 운영 환경 설정
export FLASK_ENV=production
export PROD_CORS_ORIGINS=https://afm.skhynix.com
export SECRET_KEY='강력한-비밀-키-생성'

# Gunicorn으로 실행 (WSGI 서버)
gunicorn --bind 0.0.0.0:5000 app:app

# Vue 빌드
npm run build
# dist 폴더를 웹 서버(nginx 등)에 배포
```

## 6. 보안 고려사항

### 6.1 CORS 설정의 중요성

CORS는 웹 브라우저의 보안 기능으로, 다른 도메인에서의 요청을 제한합니다:

```python
# 잘못된 예 - 모든 도메인 허용 (보안 위험!)
CORS(app, origins="*")

# 올바른 예 - 특정 도메인만 허용
CORS(app, origins=["https://afm.skhynix.com"])
```

### 6.2 환경 변수 관리

```bash
# .gitignore에 추가
.env
.env.local
.env.*.local

# 환경 변수 템플릿 제공 (.env.example)
FLASK_ENV=development
DEV_CORS_ORIGINS=http://localhost:3000
PROD_CORS_ORIGINS=https://your-domain.com
SECRET_KEY=generate-your-own-secret-key
```

## 7. 트러블슈팅

### 7.1 일반적인 문제와 해결방법

**CORS 오류**

```text
Access to XMLHttpRequest at 'http://localhost:5000/api/health' from origin 'http://localhost:3000' has been blocked by CORS policy
```

해결: Flask 서버의 CORS 설정 확인

**네트워크 오류**

```text
Network Error: Failed to fetch
```

해결:

1. Flask 서버가 실행 중인지 확인
2. 포트 번호 확인 (5000)
3. 방화벽 설정 확인

**환경 변수 미설정**

```text
undefined API_BASE_URL
```

해결:

1. `.env` 파일 생성 확인
2. 변수명 규칙 확인 (Vue는 `VITE_` 접두사 필요)
3. 개발 서버 재시작

## 마무리

이 장에서는 Flask와 Vue.js를 API로 연결하는 방법과 환경별 설정 관리의 중요성을 배웠습니다.

### 핵심 포인트

1. **환경 분리**: 개발/운영 환경을 명확히 구분
2. **보안 설정**: CORS를 통한 접근 제어
3. **환경 변수**: `.env` 파일로 유연한 설정 관리
4. **에러 처리**: 사용자 친화적인 오류 메시지
5. **WSGI 이해**: 운영 환경에서의 Flask 실행 방법

이러한 기초를 바탕으로 안전하고 확장 가능한 웹 애플리케이션을 구축할 수 있습니다.
