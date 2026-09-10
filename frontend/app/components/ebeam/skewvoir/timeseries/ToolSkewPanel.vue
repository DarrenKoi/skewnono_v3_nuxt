<template>
  <!-- Fully confounded: every recipe was run by exactly one tool, so "this tool
       differs" and "this recipe differs" are one statement about one set of
       numbers. Centering within recipe would return three tidy 0.000 rows —
       which reads as perfect agreement between tools that were never compared —
       so the panel refuses to print numbers and says why instead.

       Checked BEFORE the toolCount copy: this set has plenty of tools, so
       '비교할 측정을 추가하세요' would be both wrong and unactionable. -->
  <div
    v-if="!rows.length && confounded"
    class="flex h-56 flex-col items-center justify-center gap-1.5 px-6 text-center"
  >
    <UIcon
      name="i-lucide-unlink"
      class="size-5 text-(--sk-warn)"
    />
    <p class="sk-body">
      recipe {{ skew.recipes }}종을 장비가 하나씩 나눠 측정해, 장비 차이를 recipe 차이와 분리할 수 없습니다.
    </p>
    <p class="sk-hint">
      한 recipe를 장비 2대 이상이 측정한 세트여야 장비 대비가 성립합니다.
    </p>
  </div>

  <!-- buildToolSkew returns [] for BOTH "one tool" and "no data", so the copy
       is chosen by toolCount, not by rows.length. -->
  <div
    v-else-if="!rows.length"
    class="flex h-56 items-center justify-center sk-body"
  >
    {{ toolCount === 1 ? '단일 장비 · 비교 대상 없습니다.' : '비교할 측정을 추가하세요.' }}
  </div>
  <table
    v-else
    class="w-full text-left"
  >
    <thead>
      <tr class="sk-label">
        <th
          scope="col"
          class="py-1"
        >
          장비
        </th>
        <th
          scope="col"
          class="py-1 text-right"
        >
          n
        </th>
        <!-- The unit rides the three value columns' headers rather than every
             row: a table of bare numbers is the one lens of the three that
             does not say what it is measuring. `unitSuffix` is '' for a
             parameter that legitimately has none, so no stray parentheses. -->
        <th
          scope="col"
          class="py-1 text-right whitespace-nowrap"
        >
          평균{{ unitSuffix }}
        </th>
        <!-- The header names WHICH baseline, because with more than one recipe
             in the set it is no longer a single set-wide number: each
             measurement is centered on its own recipe's median before the
             tools are averaged. -->
        <th
          scope="col"
          class="py-1 text-right whitespace-nowrap"
        >
          {{ baselineLabel }} 대비{{ unitSuffix }}
        </th>
        <th
          scope="col"
          class="py-1 text-right whitespace-nowrap"
        >
          σ{{ unitSuffix }}
        </th>
        <th
          scope="col"
          class="py-1 pl-3"
        >
          편차
        </th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="r in rows"
        :key="r.eqpId"
        class="border-t border-(--sk-border-soft)"
      >
        <!-- `.sk-value-num` (DESIGN.md: "A numeric value (mono + tabular
             figures)") for every number and for the equipment id, matching the
             sibling dashboard/ParamSummary.vue table rather than the 14px body
             copy this used to borrow. -->
        <td class="py-1 sk-value-num">
          {{ r.eqpId }}
        </td>
        <td class="py-1 text-right sk-value-num">
          {{ r.n }}
        </td>
        <td class="py-1 text-right sk-value-num">
          {{ r.mean.toFixed(3) }}
        </td>
        <!-- A tool that ran only recipes no other tool ran has no comparison to
             be offset FROM. It keeps its 평균 row — that is a raw fact — but the
             offset is '—', never 0. -->
        <td class="py-1 text-right sk-value-num">
          <template v-if="r.offset == null">
            —
          </template>
          <template v-else>
            {{ signed(r.offset) }}
            <span
              v-if="mixed"
              class="sk-hint"
            >· recipe {{ r.recipes }}종</span>
          </template>
        </td>
        <td class="py-1 text-right sk-value-num">
          {{ r.sigma == null ? '—' : r.sigma.toFixed(3) }}
        </td>
        <td class="py-1 pl-3">
          <!-- Offset POINT with a ±σ interval around it — not a bar from zero.
               A filled bar reads as a magnitude; this reads as an estimate and
               its uncertainty, which is what the numbers actually are. -->
          <div
            v-if="r.offset != null"
            class="relative h-4 w-full"
          >
            <span class="absolute inset-y-0 left-1/2 w-px bg-(--sk-border)" />
            <span
              v-if="r.sigma != null"
              class="absolute top-1/2 h-px -translate-y-1/2 bg-(--sk-brand)/50"
              :style="intervalStyle(r)"
            />
            <span
              class="absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-(--sk-brand)"
              :style="{ left: `${pos(r.offset)}%` }"
            />
          </div>
          <span
            v-else
            class="sk-hint"
          >이 장비만 쓴 recipe</span>
        </td>
      </tr>
    </tbody>
  </table>
</template>

<script setup lang="ts">
import type { ToolSkewResult, ToolSkewRow } from '~/utils/skewvoirAnalysis/timeSeries'

const props = defineProps<{
  skew: ToolSkewResult
  /** Distinct equipment in the set — distinguishes "one tool" from "no data". */
  toolCount: number
  unit: string
}>()

const rows = computed(() => props.skew.rows)

const mixed = computed(() => props.skew.recipes > 1)

// Tools exist, recipes are mixed, and not one recipe was run by two of them —
// so the set carries no tool contrast at all.
const confounded = computed(() =>
  props.toolCount > 1 && mixed.value && props.skew.contrastRecipes === 0
)

const baselineLabel = computed(() => (mixed.value ? 'recipe별 기준' : '세트 기준'))

const signed = (v: number): string => `${v >= 0 ? '+' : ''}${v.toFixed(3)}`

// `label (unit)`, the same shape the trend / distribution charts give their
// axis names — and empty when the parameter carries no unit, so the header
// never renders a bare `()`.
const unitSuffix = computed(() => (props.unit ? ` (${props.unit})` : ''))

// The track is scaled so the widest reach in the set — offset plus its sigma
// whisker — just fits. Scaling on offset alone would push a noisy tool's
// interval off the end of its row.
const maxAbs = computed(() =>
  rows.value.reduce(
    (m, r) => (r.offset == null ? m : Math.max(m, Math.abs(r.offset) + (r.sigma ?? 0))),
    0
  ) || 1)

/** Percent position across the track, 50% = 기준 (zero). */
const pos = (value: number): number => 50 + (value / maxAbs.value) * 50

const intervalStyle = (r: ToolSkewRow) => {
  const offset = r.offset ?? 0
  const lo = pos(offset - (r.sigma ?? 0))
  const hi = pos(offset + (r.sigma ?? 0))
  return { left: `${lo}%`, width: `${hi - lo}%` }
}
</script>
