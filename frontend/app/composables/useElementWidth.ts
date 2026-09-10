import type { Ref } from 'vue'

// Tracks an element's rendered width. Chart components need it to size symbols
// against the room actually available: the same component renders full-width in
// one panel and half-width in another's side-by-side panes, so point count
// alone cannot tell how crowded the plot is.
//
// Returns 0 until the first measurement lands — callers treat that as
// "unmeasured" and fall back, rather than computing against a zero width.
export const useElementWidth = (elRef: Ref<HTMLElement | null>) => {
  const width = ref(0)
  let observer: ResizeObserver | null = null

  // The element may live behind a v-if and toggle on and off, so rebind rather
  // than observing once at mount.
  watch(elRef, (el) => {
    observer?.disconnect()
    observer = null
    width.value = 0
    if (!el) return
    observer = new ResizeObserver(([entry]) => {
      if (entry) width.value = entry.contentRect.width
    })
    observer.observe(el)
  }, { immediate: true })

  onBeforeUnmount(() => {
    observer?.disconnect()
    observer = null
  })

  return width
}
