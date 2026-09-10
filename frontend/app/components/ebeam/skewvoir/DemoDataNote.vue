<template>
  <p
    v-if="isMock"
    class="rounded-(--sk-r-chip) bg-(--sk-warn-soft) px-3 py-2 text-(--sk-warn) sk-meta"
  >
    <span class="font-semibold">데모 데이터</span> — 이 화면의 CD와 FDC는 mock
    생성기에서 같은 값 하나를 바탕으로 만들어집니다. 그래서 여기 보이는 CD↔FDC
    상관은 장비에서 관찰된 신호가 아니라 생성기가 만든 것입니다. 방법을
    확인하는 데는 쓸 수 있어도, 판정 근거로는 쓸 수 없습니다.
  </p>
</template>

<script setup lang="ts">
// The `데모 데이터` marker required by benchmark research §7.3.
//
// The mock biases CD and FDC with ONE per-MSR `health` scalar, so a CD↔FDC
// correlation drawn at home is an artifact of the generator rather than an
// observation. Every screen that draws such a correlation carries this note;
// without it the screen teaches an engineer a relationship the fab never showed.
//
// The gate lives HERE, not at each call site, so the three surfaces cannot drift
// apart on when to warn or on what the warning says. `msr_file` is the feature
// asked about because it supplies both halves of the pair — the CD rows and the
// FDC channels come from the same response.
//
// Silent when the data is real: useDataMode defaults to not-mock while the
// answer is unknown, so a slow or missing answer leaves the screen unmarked
// rather than libelling an office measurement as a demo.
const { isMock } = useDataMode('msr_file')
</script>
