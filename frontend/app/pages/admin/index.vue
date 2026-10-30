<template>
  <div class="max-w-7xl mx-auto px-4 py-8 space-y-6">
    <header>
      <h1 class="sk-page-title flex items-center gap-2">
        <UIcon
          name="i-lucide-shield-check"
          class="text-sky-500"
        />
        관리자 도구
        <UBadge
          color="warning"
          variant="subtle"
          size="sm"
        >
          관리자 전용
        </UBadge>
      </h1>
      <p class="sk-meta mt-1">
        방문·요청 분석, 운영 로그, 접근 권한, 배너 공지를 관리하는 화면으로 들어갑니다.
      </p>
    </header>

    <section
      v-if="blocked"
      class="dashboard-surface rounded-lg border border-(--sk-border) p-6 text-center sk-body"
    >
      관리자만 접근할 수 있는 페이지입니다.
    </section>

    <div
      v-else
      class="grid grid-cols-[repeat(auto-fit,minmax(16rem,1fr))] gap-3"
    >
      <NuxtLink
        v-for="link in adminLinks"
        :key="link.to"
        :to="link.to"
        class="dashboard-surface group flex items-start gap-3 rounded-(--sk-r-card) border border-(--sk-border) p-4 transition hover:bg-(--sk-accent-soft)"
      >
        <UIcon
          :name="link.icon"
          class="size-5 shrink-0 mt-0.5 text-(--sk-ink-muted)"
        />
        <div class="min-w-0">
          <div class="text-sm font-medium text-(--sk-ink) flex items-center gap-1.5">
            {{ link.title }}
            <UIcon
              name="i-lucide-arrow-right"
              class="size-3.5 opacity-0 transition group-hover:opacity-100"
            />
          </div>
          <p class="sk-meta mt-0.5">
            {{ link.description }}
          </p>
        </div>
      </NuxtLink>
    </div>
  </div>
</template>

<script setup lang="ts">
useHead({ title: '관리자 도구 | SKEWNONO' })

// Same gate as 방문자 분석: only a caller KNOWN not to be an admin is turned
// away. The App 정보 menu hides this row from them already; this covers the URL.
const { identity } = useIdentity()
const blocked = computed(() => identity.value !== null && !identity.value.is_admin)

// Kept in sync with intro.vue's `section: 'admin'` page guides.
const adminLinks = [
  {
    to: '/admin/visitors',
    icon: 'i-lucide-user-round-search',
    title: '방문자 분석',
    description: 'DAU·WAU·MAU 추이와 누가 얼마나 자주 방문하는지 봅니다.'
  },
  {
    to: '/admin/requests',
    icon: 'i-lucide-activity',
    title: '요청 분석',
    description: '일별 요청 추이와 어떤 기능·사용자에게 요청이 몰리는지 봅니다.'
  },
  {
    to: '/admin/logs',
    icon: 'i-lucide-file-search',
    title: '운영 로그',
    description: 'level·path·사번으로 요청 로그와 오류를 추적합니다.'
  },
  {
    // The 운영 로그 page with its Identity filter preset — token requests are
    // the /endpoints API callers, which no other view separates out.
    to: '/admin/logs?identity_source=token',
    icon: 'i-lucide-key-round',
    title: 'Endpoint 로그',
    description: 'API token으로 호출된 요청만 모아 호출 경로·상태·지연을 봅니다.'
  },
  {
    to: '/admin/access',
    icon: 'i-lucide-shield-check',
    title: '접근 권한 관리',
    description: 'X-사번 차단 예외와 FTP 접속 개인 승인(신청 승인·사번 추가·회수)을 관리합니다.'
  },
  {
    to: '/admin/announcements',
    icon: 'i-lucide-megaphone',
    title: '배너 공지',
    description: '모든 화면 상단에 뜨는 배너 공지를 올리고 내립니다.'
  }
]
</script>
