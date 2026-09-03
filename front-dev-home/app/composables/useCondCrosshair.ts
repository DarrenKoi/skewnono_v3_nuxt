// Whether recipe-open image modals draw the tool's marks (crosshair + white
// box) from the image's cond.txt. One reviewer preference shared by every
// modal and kept across reloads; on by default because the marks are the
// point of opening the image at full size.
export const useCondCrosshair = () =>
  usePersistedState<boolean>(
    'recipe-open-crosshair',
    'skewnono:recipe-open:crosshair',
    {
      default: () => true,
      normalize: parsed => parsed !== false,
      isEmpty: value => value === true
    }
  )
