// The SEM sub-image (variant) pick, remembered across points and reloads.
//
// A measurement point shot as several files (HV-SEM -U/-T/-M/-L) shows a chip
// bar; before 2026-08-11 all three hosts of that bar owned a `ref(0)` plus a
// watcher that reset it on every point change, so a reviewer working a wafer at
// one depth re-picked that depth on every site. Here the pick becomes state
// keyed by recipe + parameter, shared by all three hosts and persisted.
//
// The stored value is the chip LABEL ('M', or 'M·TIF' where one sub-position
// is listed under several extensions), never an index — see
// utils/skewvoirAnalysis/variantMemory.ts for why that distinction is
// load-bearing (the suffix set is not fixed across points).
//
// WHY A WRITABLE COMPUTED AND NOT A REF + WATCHER:
//   The index is DERIVED from (this point's names, the remembered label). A ref
//   would need a watcher to re-derive it on every point/parameter change — the
//   very shape whose three copies caused the bug. As a computed there is no
//   reset path to get wrong: changing points re-runs the getter, which either
//   finds the remembered label (or its sub-position) or answers 0.
import type { MaybeRefOrGetter, WritableComputedRef } from 'vue'
import type { SkewvoirAnalysis } from '~/composables/useSkewvoirAnalysis'
import { imageVariantLabels } from '~/utils/imageKind'
import {
  normalizeVariantMemory,
  rememberVariant,
  rememberedVariantIndex,
  variantMemoryKey,
  type VariantMemory
} from '~/utils/skewvoirAnalysis/variantMemory'

/** The shared recipe+parameter → chip-label map. One state key, so the
 * dashboard panel, the gallery viewer and the site drawer read and write ONE
 * memory. */
export const useSkewvoirVariantMemory = () =>
  usePersistedState<VariantMemory>(
    'skewvoir:sem-variant-memory',
    'skewnono:skewvoir.semVariant',
    {
      default: () => ({}),
      normalize: normalizeVariantMemory,
      // No picks yet is the default, so an emptied map drops the key rather
      // than persisting "{}".
      isEmpty: value => Object.keys(value).length === 0
    }
  )

/** The memory key for the analysis context a host is rendering: the focus MSR's
 * recipe plus the active parameter. Null while either is unresolved, which
 * makes the selection below behave exactly as it did before this memory
 * existed (start at the first image, remember nothing). */
export const useSkewvoirVariantKey = (analysis: SkewvoirAnalysis) =>
  computed(() => variantMemoryKey(
    analysis.focusRow.value?.recipe_name,
    analysis.activeParam.value
  ))

/**
 * A `v-model`-able index into `names`, backed by the remembered chip label for
 * `key`. Reading resolves the label against THIS point's names; writing stores
 * the picked chip's list-aware label (possibly rendition-tagged, e.g. 'U·TIF').
 *
 * @param names this point's image files, in pickle order
 * @param key   recipe+parameter key, or null when the context is unresolved
 */
export const useSkewvoirVariantIndex = (
  names: MaybeRefOrGetter<string[]>,
  key: MaybeRefOrGetter<string | null>
): WritableComputedRef<number> => {
  const memory = useSkewvoirVariantMemory()
  return computed({
    get: () => {
      const scope = toValue(key)
      return rememberedVariantIndex(toValue(names), scope ? memory.value[scope] : null)
    },
    set: (index) => {
      const scope = toValue(key)
      const list = toValue(names)
      // An out-of-range index or an unresolved key writes nothing: the getter
      // already answers 0 for both, and storing a guess would outlive the
      // moment that produced it.
      if (!scope || list[index] == null) return
      // The LIST-AWARE label, matching what the chips render and what the
      // getter resolves against — a per-name label is ambiguous when one
      // sub-position is listed under several extensions (-U.jpeg + -U.TIF),
      // which is what made the second such chip unselectable.
      memory.value = rememberVariant(memory.value, scope, imageVariantLabels(list)[index]!)
    }
  })
}
