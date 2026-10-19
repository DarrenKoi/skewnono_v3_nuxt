<!-- 슬로건의 'Do' 연결고리 마크. 공개된 We Do Technology 로고타입처럼 D 와 o 를 한 획으로
     엮어 ∞ 처럼 교차시킵니다. 높이는 대문자 높이(0.72em)에 맞추고 기준선에 앉힙니다.
     글자 'Do' 는 sr-only 로 남겨, 읽기와 복사에서 슬로건이 그대로 이어지게 합니다. -->
<template>
  <span class="mx-[0.06em] inline-block">
    <svg
      aria-hidden="true"
      viewBox="0 0 100 72"
      class="inline-block h-[0.72em] w-[1em] overflow-visible align-baseline"
    >
      <path
        d="M4 3.5 L22 3.5 C40 3.5 46 20 50 36 C54 56 58 68.5 72 68.5 C86 68.5 94 58 94 44.5 C94 30 86 20.5 72 20.5 C60 20.5 56 32 52 44 C48 58 40 68.5 24 68.5 L4 68.5 Z"
        fill="none"
        stroke="var(--sk-corp-orange)"
        stroke-width="8"
        stroke-linejoin="round"
      />
    </svg>
    <span class="sr-only">Do</span>
  </span>
</template>
