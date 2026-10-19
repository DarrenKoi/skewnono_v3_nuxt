<!-- 랜딩 히어로의 슬로건. 회사 슬로건 로크업(We Do Technology | SK hynix)을 위에 두고, 팀 슬로건
     (We Do Metrology)을 한 단계 들여 꺾은 연결선으로 이어 상하위 관계로 읽히게 합니다.
     공개 로크업을 따라 문장형 대소문자, 회색 글자, 주황 'Do' 마크만 색을 씁니다.
     SK CI 두 색(--sk-corp-*)은 이 컴포넌트에서만 씁니다 — DESIGN.md §Colors → Corporate. -->
<template>
  <div>
    <p class="flex flex-wrap items-center gap-x-3 text-[20px] font-medium leading-tight text-(--sk-ink-muted)">
      <span>We <HomeSloganDo /> Technology</span>
      <span
        aria-hidden="true"
        class="h-[1em] w-px bg-(--sk-ink-subtle)"
      />
      <!-- 두 span 을 한 줄에 둬야 사이 공백이 남습니다 (템플릿 whitespace condense). -->
      <span class="font-bold tracking-[-0.01em]"><span class="text-(--sk-corp-red)">SK</span> <span class="text-(--sk-corp-orange)">hynix</span></span>
    </p>
    <div class="relative mt-2 pl-7">
      <span
        aria-hidden="true"
        class="absolute left-2 top-0 h-[55%] w-3 rounded-bl-[var(--sk-r-sidebar)] border-b-2 border-l-2 border-(--sk-ink-subtle)"
      />
      <h1 class="text-[clamp(32px,4vw,44px)] font-medium leading-[1.15] tracking-[-0.01em] text-(--sk-ink)">
        We <HomeSloganDo /> Metrology
      </h1>
    </div>
  </div>
</template>
