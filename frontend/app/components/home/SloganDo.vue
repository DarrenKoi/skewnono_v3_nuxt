<!-- 슬로건의 'Do' 연결고리 마크. 공개된 We Do Technology 로고타입처럼 D 의 둥근 몸통이 가파르게
     교차해 정원(o)으로 이어지는 한 획입니다(∞ 의 왼쪽 고리가 D). 교차점에서 두 획이 원에 접선으로
     붙어야 'D 옆의 o' 가 아니라 한 마크로 읽힙니다. 높이는 대문자 높이(0.72em)에 맞추고 획 바깥
     가장자리를 기준선에 앉힙니다. 글자 'Do' 는 sr-only 로 남겨 읽기와 복사에서 슬로건이 이어지게 합니다. -->
<template>
  <span class="mx-[0.06em] inline-block">
    <svg
      aria-hidden="true"
      viewBox="0 0 171 101"
      class="inline-block h-[0.72em] w-[1.22em] overflow-visible align-baseline"
    >
      <path
        d="M8 6.5 H36 C62 6.5 78.3 39.4 90.8 61 L100.6 78 A34 34 0 1 0 100.6 44 L90.8 61 C78.3 82.6 62 94.5 36 94.5 H8 Z"
        fill="none"
        stroke="var(--sk-corp-orange)"
        stroke-width="12"
        stroke-linejoin="round"
      />
    </svg>
    <span class="sr-only">Do</span>
  </span>
</template>
