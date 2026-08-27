// SEM Gallery layout: 격자 lays thumbnails on the die lattice (chip_number
// col,row — the same axes as the wafer map); 목록 is the priority reading order.
// Persisted, like the FDC toggle, because Workspace `v-if`s views away.
export type GalleryLayout = 'lattice' | 'list'

export const useSkewvoirGalleryLayout = () =>
  usePersistedState<GalleryLayout>('skewvoir:gallery-layout', 'skewnono:skewvoir.galleryLayout', {
    default: () => 'lattice',
    normalize: parsed => parsed === 'list' ? 'list' : 'lattice',
    isEmpty: () => false,
    serialize: value => value,
    deserialize: raw => raw
  })

// Thumbnail edge in px. One knob for both layouts: the original-size view is
// the click-to-open viewer, so this only trades density for legibility.
export const GALLERY_CELL_MIN = 72
export const GALLERY_CELL_MAX = 240
export const useSkewvoirGalleryCell = () =>
  usePersistedState<number>('skewvoir:gallery-cell', 'skewnono:skewvoir.galleryCell', {
    default: () => 128,
    normalize: (parsed) => {
      const n = Number(parsed)
      if (!Number.isFinite(n)) throw new Error('not a number')
      return Math.min(GALLERY_CELL_MAX, Math.max(GALLERY_CELL_MIN, n))
    },
    isEmpty: () => false
  })
