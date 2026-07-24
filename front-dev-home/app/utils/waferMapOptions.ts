// Display options for the skewvoir wafer map. Shared by the leaf renderer,
// the panel wrapper, the gear popover, and the detail modal so every surface
// speaks the same option contract.
export interface WaferMapOptions {
  crosshair: boolean // X=0 / Y=0 lines through wafer centre
  grid: boolean // die-index gridlines + axis labels
  dieGrid: boolean // die-boundary lines at true die size (chip_pitch), clipped to the wafer
  mpLabels: boolean // print mp_number on each point (Field mode)
  notch: boolean // wafer notch marker (orientation)
  colorMode: 'auto' | 'manual'
  colorMin: number | null // used when colorMode === 'manual'
  colorMax: number | null
}

export const defaultWaferMapOptions = (): WaferMapOptions => ({
  crosshair: false,
  grid: false,
  // On by default: the msr file carries real die info, so the map should show
  // the die layout at its true size out of the box.
  dieGrid: true,
  mpLabels: false,
  notch: true,
  colorMode: 'auto',
  colorMin: null,
  colorMax: null
})

// The enlarge modal opens with the demo-style numbered grid on.
export const detailWaferMapOptions = (): WaferMapOptions => ({
  ...defaultWaferMapOptions(),
  grid: true
})

// Effective color-scale range: a complete, finite, non-inverted manual pair wins;
// otherwise fall back to the data-derived auto range. Number.isFinite rejects
// null and the empty-string/NaN a blank <UInput type="number"> can produce.
export const resolveColorRange = (
  mode: 'auto' | 'manual',
  manualMin: number | null,
  manualMax: number | null,
  auto: { min: number, max: number }
): { min: number, max: number } => {
  if (mode === 'manual'
    && Number.isFinite(manualMin) && Number.isFinite(manualMax)
    && (manualMin as number) < (manualMax as number)) {
    return { min: manualMin as number, max: manualMax as number }
  }
  return auto
}
