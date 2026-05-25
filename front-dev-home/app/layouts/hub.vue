<template>
  <div class="relative isolate min-h-screen flex flex-col text-zinc-900 dark:text-zinc-100">
    <div
      class="dashboard-bg-layer"
      aria-hidden="true"
    />
    <NavAppHeader />

    <main class="flex-1">
      <slot />
    </main>

    <footer class="border-t-(--sk-border) py-4">
      <div class="max-w-7xl mx-auto px-4 text-center text-sm text-zinc-500 dark:text-zinc-400">
        SKEWNONO v3 - Metrology Solution
      </div>
    </footer>
  </div>
</template>
