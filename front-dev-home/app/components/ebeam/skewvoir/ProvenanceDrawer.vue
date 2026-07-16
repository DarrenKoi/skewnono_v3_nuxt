<template>
  <USlideover
    :open="provenance.isOpen.value"
    title="근거 보기"
    :description="provenance.label.value ?? '이 수치가 계산된 방식과 원본 데이터'"
    :ui="{ content: 'w-[92vw] sm:max-w-[420px]' }"
    @update:open="onUpdateOpen"
  >
    <template #body>
      <div
        v-if="derived"
        class="space-y-5"
      >
        <!-- Value -->
        <section>
          <p class="mb-2 sk-eyebrow">
            값
          </p>
          <div class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-3 py-2.5">
            <div
              v-if="valueEntries"
              class="space-y-1"
            >
              <div
                v-for="entry in valueEntries"
                :key="entry.key"
                class="flex items-center justify-between gap-2 text-[12.5px]"
              >
                <span class="text-(--sk-ink-muted)">{{ entry.key }}</span>
                <span class="font-mono font-semibold tabular-nums text-(--sk-ink)">{{ entry.formatted }}</span>
              </div>
            </div>
            <p
              v-else
              class="font-mono text-[15px] font-semibold tabular-nums text-(--sk-ink)"
            >
              {{ formatScalar(derived.value) }}<span
                v-if="derived.unit"
                class="ml-1 text-[12px] font-normal text-(--sk-ink-muted)"
              >{{ derived.unit }}</span>
            </p>
          </div>
        </section>

        <!-- Sample / missing -->
        <section>
          <p class="mb-2 sk-eyebrow">
            표본
          </p>
          <div class="flex gap-2">
            <div class="flex-1 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
              <p class="sk-meta">
                사용된 표본 n
              </p>
              <p class="font-mono text-[13px] font-semibold tabular-nums text-(--sk-ink)">
                {{ derived.n }}
              </p>
            </div>
            <div class="flex-1 rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2">
              <p class="sk-meta">
                제외/결측
              </p>
              <p class="font-mono text-[13px] font-semibold tabular-nums text-(--sk-ink)">
                {{ derived.missing }}
              </p>
            </div>
          </div>
        </section>

        <!-- Traceability: transform, reference, version -->
        <section>
          <p class="mb-2 sk-eyebrow">
            계산 방법
          </p>
          <p class="sk-body">
            {{ derived.transform }}
          </p>
        </section>

        <section>
          <p class="mb-2 sk-eyebrow">
            원본 소스
          </p>
          <p class="rounded-(--sk-r-nav) border border-(--sk-border-soft) px-2.5 py-2 font-mono text-[12px] text-(--sk-ink)">
            {{ derived.reference }}
          </p>
        </section>

        <section>
          <p class="mb-2 sk-eyebrow">
            버전
          </p>
          <p class="font-mono text-[11px] text-(--sk-ink-subtle)">
            {{ derived.version }}
          </p>
        </section>
      </div>
      <p
        v-else
        class="sk-body"
      >
        표시할 근거가 없습니다.
      </p>
    </template>
  </USlideover>
</template>

<script setup lang="ts">
// A generic provenance viewer — renders ANY DerivedValue (level, spread,
// coverage, failure, spatial, fixed/dynamic FDC, …). It carries no
// feature-specific knowledge; every chart/table's "근거 보기" action opens the
// SAME drawer via the useProvenance() contract (useProvenance.ts). Mount this
// component once (e.g. at the Workspace root) — it reads its own state, so
// callers never need to pass props.
import { useProvenance } from '~/composables/useProvenance'

const provenance = useProvenance()
const derived = computed(() => provenance.current.value)

const onUpdateOpen = (open: boolean) => {
  if (!open) provenance.close()
}

const formatScalar = (value: unknown): string => {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value.toLocaleString('en-US', { maximumFractionDigits: 4 }) : String(value)
  }
  return String(value)
}

// DynamicFdcSummary (and any other plain-object DerivedValue payload) renders
// as a small key/value breakdown instead of a single scalar.
const valueEntries = computed(() => {
  const value = derived.value?.value
  if (value == null || typeof value !== 'object') return null
  return Object.entries(value as Record<string, unknown>).map(([key, v]) => ({
    key,
    formatted: `${formatScalar(v)}${derived.value?.unit ? ` ${derived.value.unit}` : ''}`
  }))
})
</script>
