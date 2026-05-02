<template>
  <v-container class="pa-6">
    <v-row justify="center">
      <v-col cols="12" md="10" lg="8">
        <!-- Header -->
        <div class="text-center mb-8">
          <img alt="AFM Logo" src="@/assets/afm_logo2.png" style="max-width: 300px; width: 100%; height: auto;"
            class="mb-4">
          <h1 class="text-h3 font-weight-bold primary--text mb-4">AFM 데이터 플랫폼</h1>
          <p class="text-h6 text-medium-emphasis">원자간력현미경 데이터 통합 관리 솔루션</p>
        </div>

        <!-- Project Purpose -->
        <v-card elevation="3" class="mb-6">
          <v-card-title class="bg-primary">
            <v-icon start>mdi-target</v-icon>
            프로젝트 목적
          </v-card-title>
          <v-card-text class="pa-6">
            <div class="text-body-1 line-height-relaxed">
              <p class="mb-4">
                AFM 데이터 플랫폼은 SK하이닉스의 원자간력현미경(AFM) 측정 데이터의 관리, 분석, 그리고 시각화를
                효율화하기 위해 설계된 종합적인 웹 기반 솔루션입니다. 이 플랫폼은 반도체 제조 및 연구 환경에서
                효율적인 데이터 처리 및 분석을 위한 기능을 제공합니다.
              </p>

              <h3 class="text-h6 font-weight-bold mb-3">주요 목표:</h3>
              <v-list class="mb-4">
                <v-list-item>
                  <template #prepend>
                    <v-icon color="primary">mdi-magnify</v-icon>
                  </template>
                  <v-list-item-title><strong>실시간 데이터 검색:</strong> 지능형 필터링을 통해 수천 개의 AFM 측정 데이터에서 즉시 검색
                    가능</v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="primary">mdi-chart-line</v-icon>
                  </template>
                  <v-list-item-title><strong>고급 시각화:</strong> 표면 프로파일 및 종합적인 데이터 분석 도구 제공</v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="primary">mdi-database</v-icon>
                  </template>
                  <v-list-item-title><strong>중앙 집중식 저장소:</strong> 표준화된 메타데이터 및 파일 위치 추적을 통한 측정 파일 정리</v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="primary">mdi-account-group</v-icon>
                  </template>
                  <v-list-item-title><strong>협업 연구:</strong> 연구팀 및 부서 간 데이터 공유 및 분석 촉진</v-list-item-title>
                </v-list-item>
                <v-list-item>
                  <template #prepend>
                    <v-icon color="primary">mdi-trending-up</v-icon>
                  </template>
                  <v-list-item-title><strong>트렌드 분석:</strong> 시간에 따른 측정 품질 및 장비 성능 추적</v-list-item-title>
                </v-list-item>
              </v-list>
            </div>
          </v-card-text>
        </v-card>

        <!-- Technical Features -->
        <v-card elevation="3" class="mb-6">
          <v-card-title class="bg-secondary">
            <v-icon start>mdi-cog</v-icon>
            기술적 특징
          </v-card-title>
          <v-card-text class="pa-6">
            <v-row>
              <v-col cols="12" md="6">
                <h4 class="text-h6 font-weight-bold mb-3">프론트엔드 기술</h4>
                <v-chip-group column>
                  <v-chip color="primary" variant="outlined">Vue.js 3</v-chip>
                  <v-chip color="primary" variant="outlined">Vuetify 3</v-chip>
                  <v-chip color="primary" variant="outlined">ECharts</v-chip>
                  <v-chip color="primary" variant="outlined">실시간 검색</v-chip>
                </v-chip-group>
              </v-col>
              <v-col cols="12" md="6">
                <h4 class="text-h6 font-weight-bold mb-3">백엔드 기술</h4>
                <v-chip-group column>
                  <v-chip color="secondary" variant="outlined">Flask API</v-chip>
                  <v-chip color="secondary" variant="outlined">APScheduler</v-chip>
                  <v-chip color="secondary" variant="outlined">Pandas 데이터 처리</v-chip>
                </v-chip-group>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Impact & Benefits -->
        <v-card elevation="3" class="mb-6">
          <v-card-title class="bg-success">
            <v-icon start>mdi-lightbulb</v-icon>
            영향 및 이점
          </v-card-title>
          <v-card-text class="pa-6">
            <v-row>
              <v-col cols="12" md="4">
                <div class="text-center">
                  <v-icon size="64" color="success" class="mb-2">mdi-clock-fast</v-icon>
                  <h4 class="text-h6 font-weight-bold mb-2">시간 효율성</h4>
                  <p class="text-body-2">실시간 검색 기능으로 데이터 검색 시간을 몇 분에서 몇 초로 단축</p>
                </div>
              </v-col>
              <v-col cols="12" md="4">
                <div class="text-center">
                  <v-icon size="64" color="success" class="mb-2">mdi-quality-high</v-icon>
                  <h4 class="text-h6 font-weight-bold mb-2">데이터 품질</h4>
                  <p class="text-body-2">모든 시설에서 일관된 데이터 표준 보장 및 측정 추적성 향상</p>
                </div>
              </v-col>
              <v-col cols="12" md="4">
                <div class="text-center">
                  <v-icon size="64" color="success" class="mb-2">mdi-chart-areaspline</v-icon>
                  <h4 class="text-h6 font-weight-bold mb-2">연구 가속화</h4>
                  <p class="text-body-2">포괄적인 데이터 인사이트로 더 빠른 연구 반복 및 정보에 기반한 의사결정 지원</p>
                </div>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Version Information -->
        <v-card elevation="3" class="mb-6">
          <v-card-title class="bg-info">
            <v-icon start>mdi-information</v-icon>
            버전 정보
          </v-card-title>
          <v-card-text class="pa-6">
            <v-row>
              <v-col cols="12" md="6">
                <v-list dense>
                  <v-list-item>
                    <v-list-item-title><strong>현재 버전:</strong> 1.1.0</v-list-item-title>
                  </v-list-item>
                  <v-list-item>
                    <v-list-item-title><strong>출시일:</strong> 2025년 8월</v-list-item-title>
                  </v-list-item>
                  <v-list-item>
                    <v-list-item-title><strong>개발 상태:</strong> 활발히 진행 중</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-col>
              <v-col cols="12" md="6">
                <v-list dense>
                  <v-list-item>
                    <v-list-item-title><strong>데이터셋 크기:</strong> 20,000+ 측정</v-list-item-title>
                  </v-list-item>
                  <v-list-item>
                    <v-list-item-title><strong>검색 성능:</strong> 300ms 미만 응답 시간</v-list-item-title>
                  </v-list-item>
                  <v-list-item>
                    <v-list-item-title><strong>지원 형식:</strong> Charts, Image, Excel</v-list-item-title>
                  </v-list-item>
                </v-list>
              </v-col>
            </v-row>
          </v-card-text>
        </v-card>

        <!-- Update History -->
        <v-card elevation="3">
          <v-card-title class="bg-warning">
            <v-icon start>mdi-update</v-icon>
            업데이트 이력
          </v-card-title>
          <v-card-text class="pa-6">
            <v-timeline align="start" density="compact">
              <v-timeline-item dot-color="primary" size="small">
                <div class="mb-4">
                  <div class="font-weight-bold">버전 1.1.0 - 2025년 8월</div>
                  <v-list dense class="mt-2">
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>MAPC01 툴 추가 (Fab R3 지원)</v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>Vue Query 도입으로 캐싱 성능 개선</v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>차트 테마 적용으로 시각화 품질 향상</v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>데이터 트렌드 시계열 차트에 Lot ID 표시</v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>검색어 자동 저장 및 복원 기능</v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>컴포넌트 크기 최적화</v-list-item-title>
                    </v-list-item>
                    <v-list-item>
                      <template v-slot:prepend>
                        <v-icon size="small" color="success">mdi-check</v-icon>
                      </template>
                      <v-list-item-title>Profile, Align, Tip 이미지 정보 추가</v-list-item-title>
                    </v-list-item>
                  </v-list>
                </div>
              </v-timeline-item>

              <v-timeline-item dot-color="grey" size="small">
                <div>
                  <div class="font-weight-bold">버전 1.0.0 - 2025년 7월</div>
                  <div class="text-body-2 text-medium-emphasis mt-1">
                    초기 출시 - MAP608 툴 지원, 기본 검색 및 시각화 기능
                  </div>
                </div>
              </v-timeline-item>
            </v-timeline>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
// Page metadata
defineOptions({
  name: 'AboutPage'
})
</script>

<style scoped>
.line-height-relaxed {
  line-height: 1.7;
}
</style>