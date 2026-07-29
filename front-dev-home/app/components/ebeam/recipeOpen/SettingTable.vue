<template>
  <div class="flex min-w-0 flex-col overflow-hidden rounded-xl border border-zinc-200/70 bg-zinc-50/40 dark:border-zinc-800/60 dark:bg-zinc-900/30">
    <div class="flex shrink-0 items-baseline justify-between gap-2 border-b border-zinc-200/70 px-3.5 py-2 dark:border-zinc-800/60">
      <span class="text-[11px] font-semibold text-zinc-900 dark:text-zinc-100">{{ title }}</span>
      <span
        v-if="block"
        class="truncate font-mono text-[10px] text-(--sk-ink-muted)"
        :title="block.source"
      >{{ block.source }}</span>
    </div>

    <p
      v-if="!block"
      class="px-3.5 py-3 text-[11px] text-(--sk-ink-muted)"
    >
      파일 없음
    </p>

    <div
      v-else
      class="overflow-auto"
    >
      <table class="w-full border-collapse font-mono text-xs">
        <tbody>
          <tr
            v-for="(setting, index) in block.rows"
            :key="setting.key"
            :class="index % 2 ? 'bg-black/[0.014] dark:bg-white/[0.02]' : ''"
          >
            <td class="border-b border-zinc-100 px-3.5 py-1.5 text-[11px] font-semibold whitespace-nowrap text-zinc-700 dark:border-zinc-800/60 dark:text-zinc-300">
              {{ setting.key }}
            </td>
            <td
              class="border-b border-zinc-100 px-3 py-1.5 text-right whitespace-nowrap dark:border-zinc-800/60"
              :class="formatSettingValue(setting.value) === '—'
                ? 'text-(--sk-ink-muted)'
                : 'text-zinc-900 dark:text-zinc-100'"
            >
              {{ formatSettingValue(setting.value) }}
            </td>
          </tr>
        </tbody>
      </table>
      <p
        v-if="!block.rows.length"
        class="px-3.5 py-3 text-[11px] text-(--sk-ink-muted)"
      >
        읽을 수 있는 설정이 없습니다.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * One parsed raw-recipe file, rendered as key/value rows.
 *
 * Deliberately NOT a fixed column layout. The office parser's field names are
 * still unverified, so the rows are whatever it returned, in its own order — an
 * unexpected key renders instead of vanishing, which is how the sixteen
 * invented AmpRow columns this replaces went unnoticed for months.
 */
import type { SettingBlock } from '~/composables/useRecipeParamDetail'
import { formatSettingValue } from '~/utils/recipeView'

defineProps<{
  title: string
  /** `null` when the slot is `non`, the file is absent, or it could not be parsed. */
  block: SettingBlock | null
}>()
</script>
