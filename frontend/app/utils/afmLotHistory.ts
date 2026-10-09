// Pure logic for 측정 상세's 같은 Lot·Slot 측정 block: which measurements of the
// tool's list share the opened one's lot and slot, and which of them an
// "add to group" takes. No DOM/Nuxt imports so it runs under `node --test`.
import type { AfmMeasurement } from '~/composables/useAfmCart'

export interface AfmLotHistory {
  current: AfmMeasurement
  // Same lot and slot, the opened measurement included.
  wafer: AfmMeasurement[]
  // Same lot, another slot.
  otherSlots: AfmMeasurement[]
  // Same lot, slot not recorded: possibly this wafer, so in neither list.
  noSlot: number
}

// Oldest first. formattedDate is "YYYY-MM-DD[ HH:MM:SS]" built from
// measured_time, so it sorts as text; '' (no date) cannot be placed and goes
// last. The file name settles a tie so the order never flips between renders.
const byTime = (a: AfmMeasurement, b: AfmMeasurement) =>
  Number(!a.formattedDate) - Number(!b.formattedDate)
  || a.formattedDate.localeCompare(b.formattedDate)
  || a.filename.localeCompare(b.filename)

// The list writes one slot two ways — `5` read from Info, `07` from the file
// name's tail (docs/datatables/afm/afm_redis.txt, slot_number) — so a numeric
// slot is compared as its number. '' is a slot nobody recorded.
const slotKey = (slot: AfmMeasurement['slotNumber']) => {
  const text = String(slot ?? '').trim()
  return /^\d+$/.test(text) ? String(Number(text)) : text
}

export const lotHistory = (rows: AfmMeasurement[], filename: string): AfmLotHistory | null => {
  const current = rows.find(item => item.filename === filename)
  const lot = current?.lotId.trim()
  const slot = slotKey(current?.slotNumber ?? '')
  if (!current || !lot || !slot) return null
  const sameLot = rows.filter(item => item.lotId.trim() === lot).sort(byTime)
  const slotted = sameLot.filter(item => slotKey(item.slotNumber))
  return {
    current,
    wafer: slotted.filter(item => slotKey(item.slotNumber) === slot),
    otherSlots: slotted.filter(item => slotKey(item.slotNumber) !== slot),
    noSlot: sameLot.length - slotted.length
  }
}

export interface AfmHistoryPick {
  // What the group takes, oldest first.
  add: AfmMeasurement[]
  // Wanted but past the room left in the group.
  leftOut: number
  // Measurements of `history` on another recipe than the opened one.
  otherRecipe: number
}

// A column of one name is not known to be one quantity across recipes, so the
// opened measurement's recipe is the default scope of an add. Where the group
// has less room than the history needs, the measurements nearest the opened
// one in time order are kept (the earlier one on a tie) and the rest counted.
export const pickForGroup = (
  history: AfmMeasurement[],
  current: AfmMeasurement,
  room: number,
  inGroup: (filename: string) => boolean,
  sameRecipeOnly: boolean
): AfmHistoryPick => {
  const ordered = [...history].sort(byTime)
  const at = ordered.findIndex(item => item.filename === current.filename)
  const otherRecipe = ordered.filter(item => item.recipeName !== current.recipeName).length
  const wanted = ordered
    .map((item, index) => ({ item, index }))
    .filter(({ item }) => !inGroup(item.filename) && (!sameRecipeOnly || item.recipeName === current.recipeName))
  const kept = [...wanted]
    .sort((a, b) => Math.abs(a.index - at) - Math.abs(b.index - at) || a.index - b.index)
    .slice(0, Math.max(room, 0))
    .sort((a, b) => a.index - b.index)
  return { add: kept.map(({ item }) => item), leftOut: wanted.length - kept.length, otherRecipe }
}
