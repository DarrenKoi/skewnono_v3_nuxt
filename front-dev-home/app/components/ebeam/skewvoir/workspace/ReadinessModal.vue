<template>
  <UModal
    :open="open"
    title="분석 준비 상태"
    description="호환 그룹 · 제외 측정 · 기능별 준비도"
    :ui="{ content: 'w-[92vw] sm:max-w-xl' }"
    @update:open="emit('update:open', $event)"
  >
    <template #body>
      <div class="space-y-5">
        <!-- Per-capability readiness -->
        <section>
          <p class="mb-2 sk-eyebrow">
            기능별 준비도
          </p>
          <ul class="space-y-1.5">
            <li
              v-for="cap in capabilities"
              :key="cap.key"
              class="flex items-center justify-between gap-2 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2"
            >
              <span class="min-w-0">
                <span class="block truncate text-[12.5px] font-semibold text-(--sk-ink)">{{ cap.label }}</span>
                <span
                  v-if="cap.readiness.reasons.length"
                  class="block truncate text-[11px] text-(--sk-ink-muted)"
                >{{ cap.readiness.reasons.map(reasonLabel).join(', ') }}</span>
              </span>
              <span
                class="shrink-0 rounded-(--sk-r-chip) px-2 py-0.5 text-[11px] font-semibold"
                :class="statusClass(cap.readiness.status)"
              >
                {{ statusLabel(cap.readiness.status) }}
              </span>
            </li>
          </ul>
        </section>

        <!-- Compatibility groups -->
        <section>
          <p class="mb-2 sk-eyebrow">
            호환 그룹 · {{ groups.length }}
          </p>
          <ul
            v-if="groups.length"
            class="space-y-1.5"
          >
            <li
              v-for="(group, i) in groups"
              :key="group.key"
              class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2"
            >
              <div class="flex items-center justify-between gap-2">
                <span class="text-[12px] font-semibold text-(--sk-ink)">그룹 {{ i + 1 }}</span>
                <span class="sk-meta tabular-nums">{{ group.members.length }} MSR</span>
              </div>
              <p class="mt-0.5 truncate font-mono text-[11px] text-(--sk-ink-muted)">
                {{ groupLabel(group) }}
              </p>
              <p class="mt-1 break-all font-mono text-[11px] text-(--sk-ink-subtle)">
                {{ group.members.join(', ') }}
              </p>
            </li>
          </ul>
          <p
            v-else
            class="sk-body"
          >
            아직 로드된 호환 측정이 없습니다.
          </p>
        </section>

        <!-- Excluded MSRs -->
        <section v-if="excluded.length">
          <p class="mb-2 sk-eyebrow">
            제외된 측정 · {{ excluded.length }}
          </p>
          <ul class="space-y-1.5">
            <li
              v-for="entry in excluded"
              :key="entry.msr"
              class="flex items-start justify-between gap-2 rounded-(--sk-r-nav) border border-(--sk-bad-border) bg-(--sk-bad-soft) px-2.5 py-2"
            >
              <span class="truncate font-mono text-[11px] text-(--sk-ink)">{{ entry.msr }}</span>
              <span class="flex shrink-0 flex-wrap justify-end gap-1">
                <span
                  v-for="reason in entry.reasons"
                  :key="reason"
                  class="rounded-(--sk-r-chip) bg-(--sk-bad)/10 px-1.5 py-0.5 text-[10px] font-semibold text-(--sk-bad)"
                >
                  {{ reasonLabel(reason) }}
                </span>
              </span>
            </li>
          </ul>
        </section>
      </div>
    </template>
  </UModal>
</template>

<script setup lang="ts">
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import type { CompatibilityGroup, Readiness } from '~/utils/skewvoirAnalysis/types'

const props = defineProps<{
  analysis: SkewvoirAnalysis
  open: boolean
}>()

const emit = defineEmits<{ 'update:open': [boolean] }>()

const groups = computed(() => props.analysis.manifest.value.groups)
const excluded = computed(() => props.analysis.manifest.value.excluded)

const capabilities = computed(() => {
  const r = props.analysis.manifest.value.readiness
  return [
    { key: 'multiMsrDelta', label: '다중 MSR 편차', readiness: r.multiMsrDelta },
    { key: 'siteVariability', label: '사이트 간 편차', readiness: r.siteVariability },
    { key: 'sameSiteGallery', label: '동일 사이트 갤러리', readiness: r.sameSiteGallery }
  ] satisfies { key: string, label: string, readiness: Readiness }[]
})

const statusLabel = (status: Readiness['status']): string =>
  status === 'ready' ? '준비됨' : status === 'limited' ? '제한적' : '불가'

const statusClass = (status: Readiness['status']): string =>
  status === 'ready'
    ? 'bg-(--sk-ok-soft) text-(--sk-ok)'
    : status === 'limited'
      ? 'bg-(--sk-warn-soft) text-(--sk-warn)'
      : 'bg-(--sk-chip-bg) text-(--sk-ink-muted)'

// Human-readable labels for reason codes (exclusion + readiness reasons).
const REASON_LABELS: Record<string, string> = {
  'recipe-mismatch': '레시피 불일치',
  'layout-mismatch': '레이아웃 불일치',
  'unit-mismatch': '단위 불일치',
  'method-mismatch': '측정 방식 불일치',
  'metadata-missing': '메타데이터 없음',
  'needs-multiple-msrs': '측정 2개 이상 필요',
  'layout-unknown': '레이아웃 정보 없음'
}
const reasonLabel = (reason: string): string => {
  if (reason.startsWith('common-coverage:')) {
    return `공통 사이트 ${reason.split(':')[1]}개`
  }
  return REASON_LABELS[reason] ?? reason
}

const groupLabel = (group: CompatibilityGroup): string => {
  const sig = group.signature
  const recipe = sig.recipe.state === 'known' ? sig.recipe.value.recipeName : '레시피 미상'
  const unit = sig.unit.state === 'known' ? sig.unit.value : '단위 미상'
  return `${recipe} · ${unit}`
}
</script>
