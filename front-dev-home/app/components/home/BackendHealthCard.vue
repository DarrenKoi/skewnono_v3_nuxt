<template>
  <div
    class="sk-health-card"
    :class="`sk-health-card--${overallStatus}`"
  >
    <div class="sk-health-card__head">
      <span class="sk-health-card__title">시스템 상태</span>
      <span class="sk-health-card__stamp">{{ stampLabel }}</span>
    </div>

    <div class="sk-health-card__summary">
      <span class="sk-health-card__dot sk-health-card__dot--lg">
        <span
          v-if="overallStatus === 'up'"
          class="sk-health-card__dot-halo"
        />
        <span class="sk-health-card__dot-core" />
      </span>
      <div class="sk-health-card__summary-text">
        <span class="sk-health-card__headline">{{ headline }}</span>
        <span class="sk-health-card__subline">{{ subline }}</span>
      </div>
    </div>

    <button
      type="button"
      class="sk-health-card__toggle"
      :aria-expanded="expanded"
      aria-controls="sk-health-details"
      @click="expanded = !expanded"
    >
      <span>{{ expanded ? '간단히 보기' : '자세히 보기' }}</span>
      <span
        class="sk-health-card__chev"
        :class="{ 'sk-health-card__chev--open': expanded }"
        aria-hidden="true"
      >▾</span>
    </button>

    <div
      v-if="expanded"
      id="sk-health-details"
      class="sk-health-card__details"
    >
      <div
        v-for="svc in services"
        :key="svc.id"
        class="sk-health-card__row"
        :class="`sk-health-card__row--${svc.status}`"
      >
        <span class="sk-health-card__dot">
          <span
            v-if="svc.status === 'up'"
            class="sk-health-card__dot-halo"
          />
          <span class="sk-health-card__dot-core" />
        </span>
        <span class="sk-health-card__label">{{ svc.label }}</span>
        <span class="sk-health-card__latency">{{ formatLatency(svc.latency_ms) }}</span>
        <span class="sk-health-card__badge">{{ STATUS_LABEL[svc.status] }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ServiceHealth, ServiceStatus } from '~/composables/useBackendHealthApi'

const props = defineProps<{
  services: ServiceHealth[]
  checkedAt: string
}>()

const STATUS_LABEL: Record<ServiceStatus, string> = {
  up: 'Connected',
  down: 'Down'
}

// 기술 컴포넌트명 → 사용자 언어. 새 서비스가 추가되면 두 매핑에 같이 추가하지
// 않으면 자세히 보기에는 보이지만 요약에서 누락됩니다 (fallback 으로 svc.label 사용).
const USER_COPY_OK: Record<string, string> = {
  opensearch: '검색 가능',
  minio: '데이터 저장 정상',
  redis: '캐시 정상'
}

const USER_COPY_DOWN: Record<string, string> = {
  opensearch: '검색 불가',
  minio: '데이터 저장 오류',
  redis: '캐시 오류'
}

const expanded = ref(false)

const overallStatus = computed<ServiceStatus>(() =>
  props.services.some(s => s.status === 'down') ? 'down' : 'up'
)

const headline = computed(() => {
  if (props.services.length === 0) return '확인 중…'
  const downCount = props.services.filter(s => s.status === 'down').length
  if (downCount === 0) return '전체 정상'
  return `${downCount}개 항목 점검 필요`
})

const subline = computed(() =>
  props.services
    .map((s) => {
      const table = s.status === 'up' ? USER_COPY_OK : USER_COPY_DOWN
      return table[s.id] ?? s.label
    })
    .join(' · ')
)

const formatLatency = (ms: number | null) => (ms == null ? '—' : `${ms}ms`)

// 보이지 않는 동안에는 1Hz 타이머를 멈춥니다 — Vue 가 매초 리액티비티를
// 플러시하는 것을 막기 위함.
const now = ref(Date.now())
let timer: ReturnType<typeof setInterval> | null = null

const startTimer = () => {
  if (timer) return
  now.value = Date.now()
  timer = setInterval(() => {
    now.value = Date.now()
  }, 1000)
}

const stopTimer = () => {
  if (!timer) return
  clearInterval(timer)
  timer = null
}

const onVisibility = () => {
  if (document.hidden) stopTimer()
  else startTimer()
}

onMounted(() => {
  startTimer()
  document.addEventListener('visibilitychange', onVisibility)
})

onBeforeUnmount(() => {
  stopTimer()
  document.removeEventListener('visibilitychange', onVisibility)
})

const stampLabel = computed(() => {
  if (!props.checkedAt) return 'checking…'
  const ts = Date.parse(props.checkedAt)
  if (Number.isNaN(ts)) return 'checking…'
  const seconds = Math.max(0, Math.round((now.value - ts) / 1000))
  if (seconds < 1) return 'just now'
  if (seconds < 60) return `${seconds}초 전 확인`
  const minutes = Math.floor(seconds / 60)
  return `${minutes}분 전 확인`
})
</script>

<style scoped>
.sk-health-card {
  width: 100%;
  max-width: 100%;
  padding: 12px 14px;
  background: var(--sk-muted-surface);
  border: 1px solid var(--sk-border);
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-family: 'Public Sans', 'Noto Sans KR', system-ui, sans-serif;
}

@media (min-width: 768px) {
  .sk-health-card {
    width: auto;
    min-width: 340px;
    max-width: 420px;
  }
}

/* Card-level color follows the worst status — summary dot inherits via
   currentColor, expanded rows override per-row. */
.sk-health-card--up {
  color: var(--sk-ok);
  --sk-status-soft: var(--sk-ok-soft);
  --sk-status-border: var(--sk-ok-border);
}

.sk-health-card--down {
  color: var(--sk-bad);
  --sk-status-soft: var(--sk-bad-soft);
  --sk-status-border: var(--sk-bad-border);
}

.sk-health-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--sk-border-soft);
}

.sk-health-card__title {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.2em;
  color: var(--sk-ink-subtle);
  text-transform: uppercase;
}

.sk-health-card__stamp {
  font-size: 10px;
  color: var(--sk-ink-subtle);
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
}

.sk-health-card__summary {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 4px 2px 2px;
}

.sk-health-card__summary-text {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.sk-health-card__headline {
  font-size: 14px;
  font-weight: 700;
  color: var(--sk-ink);
  letter-spacing: -0.01em;
}

.sk-health-card__subline {
  font-size: 11.5px;
  color: var(--sk-ink-muted);
  line-height: 1.4;
}

.sk-health-card__toggle {
  appearance: none;
  background: transparent;
  border: none;
  border-top: 1px solid var(--sk-border-soft);
  margin-top: 2px;
  padding: 8px 2px 2px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  font-family: inherit;
  font-size: 11px;
  font-weight: 600;
  color: var(--sk-ink-muted);
  letter-spacing: 0.02em;
}

.sk-health-card__toggle:hover {
  color: var(--sk-ink);
}

.sk-health-card__chev {
  display: inline-block;
  font-size: 12px;
  transition: transform 150ms ease;
}

.sk-health-card__chev--open {
  transform: rotate(180deg);
}

.sk-health-card__details {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding-top: 4px;
}

.sk-health-card__row {
  display: grid;
  grid-template-columns: 14px 1fr auto auto;
  gap: 10px;
  align-items: center;
  padding: 5px 2px;
}

.sk-health-card__row--up {
  color: var(--sk-ok);
  --sk-status-soft: var(--sk-ok-soft);
  --sk-status-border: var(--sk-ok-border);
}

.sk-health-card__row--down {
  color: var(--sk-bad);
  --sk-status-soft: var(--sk-bad-soft);
  --sk-status-border: var(--sk-bad-border);
}

.sk-health-card__dot {
  position: relative;
  width: 7px;
  height: 7px;
  display: inline-block;
}

.sk-health-card__dot--lg {
  width: 10px;
  height: 10px;
  flex-shrink: 0;
}

.sk-health-card__dot-core {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: currentColor;
}

.sk-health-card__dot-halo {
  position: absolute;
  inset: 0;
  border-radius: 999px;
  background: currentColor;
  opacity: 0.35;
  animation: sk-pulse 1.6s ease-out infinite;
}

.sk-health-card__label {
  font-size: 12px;
  font-weight: 600;
  color: var(--sk-ink);
}

.sk-health-card__latency {
  font-size: 10px;
  font-family: 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, Consolas, monospace;
  color: var(--sk-ink-subtle);
  text-align: right;
  min-width: 52px;
}

.sk-health-card__badge {
  font-size: 9.5px;
  font-weight: 700;
  letter-spacing: 0.4px;
  text-transform: uppercase;
  padding: 2px 7px;
  border-radius: 4px;
  min-width: 70px;
  text-align: center;
  color: currentColor;
  background: var(--sk-status-soft);
  border: 1px solid var(--sk-status-border);
}
</style>
