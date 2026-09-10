<template>
  <!-- Right side: two labelled menus, not a row of icons. The eight icons that used to sit
       here were a second, unlabelled hierarchy beside the feature tabs — same line, no way
       to tell a fab-scoped feature from a global page, and two icons duplicated across the
       two groups. 실험실 holds the tools, 계정 holds the caller and their own pages; both
       draw their rows from utils/headerNav, the one list the feature tabs also read. -->
  <UHeader>
    <template #left>
      <NuxtLink
        to="/"
        class="flex items-center"
      >
        <AppLogo />
      </NuxtLink>
    </template>

    <NavFeatureTabs />

    <template #right>
      <NavLabMenu />
      <NavAccountMenu />
    </template>
  </UHeader>
</template>
