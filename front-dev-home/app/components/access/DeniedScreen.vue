<template>
  <div class="flex min-h-screen items-center justify-center bg-zinc-50 px-4 dark:bg-zinc-950">
    <div class="dashboard-surface w-full max-w-md rounded-xl border border-(--sk-border) p-8 text-center">
      <div class="mx-auto flex size-14 items-center justify-center rounded-full bg-red-50 dark:bg-red-950/40">
        <UIcon
          name="i-lucide-shield-x"
          class="size-7 text-red-500"
        />
      </div>
      <h1 class="mt-4 text-xl font-semibold text-zinc-950 dark:text-zinc-50">
        접근 권한이 없습니다
      </h1>
      <p class="mt-2 text-sm leading-6 text-zinc-500 dark:text-zinc-400">
        현재 계정으로는 스큐노노 서비스를 이용할 수 없습니다.<br>
        이용이 필요하시면 관리자에게 접근 권한을 요청해 주세요.
      </p>
      <div class="mt-5 rounded-lg bg-zinc-100 px-4 py-3 text-sm text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
        관리자 문의: 사번
        <span class="font-semibold tabular-nums">2067928</span>
      </div>
    </div>
  </div>
</template>
