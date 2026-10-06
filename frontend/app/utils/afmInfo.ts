// What the AFM pages read out of a measurement's Info section. Its values are
// text as the tool wrote them, so every rule about their shape lives here.
// No DOM/Nuxt imports so this runs under `node --test`.
import type { AfmInformation } from '~/composables/useAfmDetailApi'

// The Tip Width a measurement recorded, or null where it recorded none: the
// office stores the literal text 'NaN' for that (office 확인 2026-10-06).
// parseFloat, not Number, so a unit in the value ("40.9 nm") survives.
export const tipWidthOf = (information: AfmInformation): number | null => {
  const width = Number.parseFloat(String(information['Tip Width'] ?? ''))
  return Number.isFinite(width) ? width : null
}

// The wafer's slot: the 15-key layout's `Sample Location` (`Slot N`, the real
// slot — office 확인 2026-10-06) or the 13-key layout's `Slot No` (value shape
// OFFICE-VERIFY). The file name's `.nn` tail is NOT a slot.
export const infoSlot = (information: AfmInformation): string | undefined =>
  /Slot\s*(\d+)/i.exec(String(information['Sample Location'] ?? ''))?.[1]
  ?? /\d+/.exec(String(information['Slot No'] ?? ''))?.[0]
