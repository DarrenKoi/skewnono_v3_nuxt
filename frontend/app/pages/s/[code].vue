<script setup lang="ts">
/**
 * Short-link resolver. `/s/<code>` looks the code up and replaces itself with
 * the target screen.
 *
 * `replace`, not `push`: this URL is a forwarding address, not a place. Left in
 * the history stack, Back from the analysis screen would land here and forward
 * again, trapping the reader.
 *
 * The "not found" state is a first-class outcome, not an error page. These
 * links live in messengers and reports for months, so opening one whose code
 * expired is routine — and the 404 has to say which of the two things happened
 * (wrong code vs. store down), because they send someone to different places.
 */
interface ShortLinkResponse {
  code: string
  target: string
  created_at: string
}

const route = useRoute()
const code = computed(() => String(route.params.code ?? ''))

const { data, error } = await useAsyncData(
  () => `short-link-${code.value}`,
  () => $fetch<ShortLinkResponse>(`/api/short-links/${encodeURIComponent(code.value)}`),
  { watch: [code] }
)

// A 503 is the store being unreachable, which is worth distinguishing: the link
// is probably fine and retrying is the right advice, where a 404 means the code
// itself is wrong or aged out and retrying will never help.
const unavailable = computed(() => (error.value as { statusCode?: number } | null)?.statusCode === 503)

watchEffect(() => {
  const target = data.value?.target
  if (target) navigateTo(target, { replace: true })
})
</script>

<template>
  <div class="flex min-h-screen items-center justify-center p-6">
    <!-- Resolving: no spinner card. The lookup is a single Redis GET and the
         page is gone in one frame; a card that flashes in and out reads as a
         glitch rather than as progress. -->
    <p
      v-if="!error"
      class="text-sm text-(--sk-ink-muted)"
    >
      링크를 여는 중입니다...
    </p>

    <UCard
      v-else
      class="w-full max-w-md"
    >
      <template #header>
        <h1 class="text-lg font-medium text-(--sk-ink)">
          {{ unavailable ? '지금은 링크를 열 수 없습니다' : '링크를 찾을 수 없습니다' }}
        </h1>
      </template>

      <p class="text-sm text-(--sk-ink-muted)">
        <template v-if="unavailable">
          링크 저장소에 연결하지 못했습니다. 잠시 후 다시 시도해 주십시오.
          링크 자체는 유효할 수 있습니다.
        </template>
        <template v-else>
          이 짧은 링크는 만료되었거나 존재하지 않습니다.
          링크를 공유한 분에게 다시 요청해 주십시오.
        </template>
      </p>

      <p class="mt-3 font-mono text-xs break-all text-(--sk-ink-muted)">
        /s/{{ code }}
      </p>

      <template #footer>
        <UButton
          to="/"
          color="neutral"
          variant="soft"
          size="sm"
          icon="i-lucide-home"
          label="홈으로"
        />
      </template>
    </UCard>
  </div>
</template>
