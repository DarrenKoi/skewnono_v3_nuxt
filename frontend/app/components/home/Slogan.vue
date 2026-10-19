<!-- 랜딩 히어로의 슬로건. 회사 슬로건(WE DO TECHNOLOGY)을 위에 두고, 팀 슬로건
     (WE DO METROLOGY)을 한 단계 들여 꺾은 연결선으로 이어 상하위 관계로 읽히게 합니다.
     SK CI 두 색(--sk-corp-*)은 이 컴포넌트에서만 씁니다 — DESIGN.md §Colors → Corporate. -->
<template>
  <div>
    <p class="flex flex-wrap items-baseline gap-x-2.5 text-[13px] font-bold uppercase tracking-[0.16em]">
      <span class="normal-case tracking-normal text-(--sk-ink)">SK hynix</span>
      <span class="text-(--sk-ink-muted)">We Do Technology</span>
    </p>
    <div class="relative mt-1.5 pl-7">
      <span
        aria-hidden="true"
        class="absolute left-2 top-0 h-[55%] w-3 rounded-bl-[var(--sk-r-sidebar)] border-b-2 border-l-2 border-(--sk-border)"
      />
      <h1 class="text-[clamp(32px,4vw,44px)] font-bold leading-[1.1] tracking-[-0.01em] text-(--sk-ink)">
        WE DO
        <span class="bg-linear-to-r from-(--sk-corp-red) to-(--sk-corp-orange) bg-clip-text text-transparent">METROLOGY</span>
      </h1>
    </div>
  </div>
</template>
