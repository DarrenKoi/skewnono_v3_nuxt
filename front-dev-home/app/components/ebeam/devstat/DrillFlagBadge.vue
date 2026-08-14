<template>
  <!-- 설계상 웨이퍼 전면을 훑는 job 입니다. 이 배지가 없으면 큰 숫자가 초과
       표시 없이 놓인 것이 규칙 고장으로 읽힙니다. -->
  <span
    v-if="variant === 'exempt'"
    class="sk-badge bg-(--sk-muted-surface) font-sans font-semibold text-(--sk-ink-muted) ring-1 ring-(--sk-border) ring-inset"
    :class="large ? 'sk-badge-lg' : ''"
    :title="EXEMPT_TITLE"
  >{{ EXEMPT_LABEL }}</span>
  <span
    v-else
    class="sk-badge bg-(--sk-bad-soft) font-bold text-(--sk-bad) ring-1 ring-(--sk-bad-border) ring-inset"
    :class="large ? 'sk-badge-lg' : ''"
  >{{ label ?? '초과' }} {{ count }}</span>
</template>

<script setup lang="ts">
import { EXEMPT_LABEL, EXEMPT_TITLE } from '~/utils/deviceDrill'

// 초과/면제 배지의 단일 원천. 두 화면(device-statistics 의 Lot 요약 모달,
// measurement-rules 의 위반 슬라이드오버)이 같은 것을 그립니다.
//
// **언제 그릴지는 여기서 정하지 않습니다.** 두 화면의 조건이 실제로 다릅니다 —
// outlier 쪽은 DrillRecipe.flagged 를 보고, 위반 쪽은 flagged_count > 0 을
// 봅니다 (DrillRecipe.flagged 가 gray 판정을 함께 담아서 둘이 갈립니다).
// 그래서 v-if 는 부모에 남기고 이 컴포넌트는 모양만 책임집니다.
defineProps<{
  variant: 'exempt' | 'flagged'
  /** flagged 일 때의 개수. exempt 면 무시됩니다. */
  count?: number
  /** 'flagged' 배지의 말. 서술(초과)과 규범(위반)이 다른 말을 씁니다. */
  label?: string
  /**
   * 뷰포트 80% 슬라이드오버는 22px lot_cd 옆에 서므로 한 단계 큰 배지를 씁니다.
   * 모달 카드는 18px 제목 옆이라 기본 크기입니다 — 색은 같고 크기만 다릅니다.
   */
  large?: boolean
}>()
</script>
