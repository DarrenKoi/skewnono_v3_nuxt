<template>
  <UHeader>
    <template #left>
      <NuxtLink
        to="/"
        class="flex items-center"
      >
        <AppLogo />
      </NuxtLink>
    </template>

    <template #right>
      <UButton
        to="/information"
        icon="i-lucide-info"
        color="neutral"
        variant="ghost"
        aria-label="프로젝트 정보"
      >
        <span class="hidden sm:inline">
          정보
        </span>
      </UButton>
      <UButton
        to="/settings"
        icon="i-lucide-settings"
        color="neutral"
        variant="ghost"
        aria-label="Settings"
      />
      <UColorModeButton />
    </template>
  </UHeader>
</template>
