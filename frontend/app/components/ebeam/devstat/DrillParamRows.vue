<template>
  <!-- 표가 아니라 라벨 달린 행입니다. 열이 셋뿐이고 헤더도 없어서, <table> 이
       주는 정렬 이점보다 작은 글자의 대가가 큽니다. -->
  <div class="border-t border-(--sk-border)">
    <div
      v-for="param in parameters"
      :key="param.name"
      class="px-4 py-1.5"
      :class="param.flagged ? 'bg-(--sk-bad-soft)' : ''"
    >
      <!-- 배경 tint 는 행 전체를 덮되 글자는 max-w 안에 묶습니다. 슬라이드오버가
           뷰포트의 80% 라, 이름과 값을 양 끝으로 밀어 두면 둘 사이를 1000px 넘게
           눈으로 건너야 합니다. -->
      <div class="flex max-w-2xl items-center gap-3">
        <span
          class="min-w-0 flex-1"
          :class="dense ? 'sk-field-name' : 'font-mono text-[15px] text-(--sk-ink)'"
        >{{ param.name }}</span>
        <!-- mother/son — idp 의 Mother_Para 그대로(ruleEngine.paramRole). mother 만
             accent 로 띄웁니다: 한 image 그룹에서 주인은 하나이고 나머지는 전부
             son 이라, son 까지 색을 주면 배지가 아니라 벽지가 됩니다. -->
        <span class="w-16 flex-none text-center">
          <span
            class="sk-badge ring-1 ring-inset"
            :class="param.role === 'mother'
              ? 'bg-(--sk-accent-tint) text-(--sk-accent) ring-(--sk-accent-border)'
              : 'bg-(--sk-muted-surface) text-(--sk-ink-muted) ring-(--sk-border)'"
          >{{ param.role }}</span>
        </span>
        <span
          class="w-16 flex-none text-right font-semibold text-(--sk-ink)"
          :class="dense ? 'sk-field-value' : 'font-mono text-base tabular-nums'"
        >{{ param.point_count }}</span>
        <span class="w-28 flex-none text-right sk-field-label tabular-nums">{{ param.note ?? '' }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DrillParameter } from '~/utils/deviceDrill'

// 파라미터 행 목록의 단일 원천. 두 화면이 같은 네 열(이름 · mother/son ·
// point_count · 꼬리표)을 같은 폭으로 그립니다.
//
// **색은 공유하고 크기는 나눕니다.** 초과 tint 는 어느 화면에서나 --sk-bad 라야
// 하지만 글자 크기는 그렇지 않습니다 — 뷰포트 80% 슬라이드오버와 모달 카드
// 안쪽은 서로 다른 타입 스케일 위에 있고, 하나로 맞추면 한쪽이 반드시 틀립니다.
defineProps<{
  parameters: DrillParameter[]
  /**
   * 모달 카드 안쪽인가. 참이면 카드용 유틸리티 클래스(13/14px)를, 거짓이면
   * 슬라이드오버의 15/16px 를 씁니다.
   */
  dense?: boolean
}>()
</script>
