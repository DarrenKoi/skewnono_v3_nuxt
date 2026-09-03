// Whether recipe image modals draw the tool's marks (crosshair + white-box centre)
// from the image's cond.txt. One reviewer preference shared by every modal and
// kept across reloads; on by default because the marks are the point of
// opening the image at full size.
export const useCondCrosshair = () =>
  persistedFlag('recipe-open-crosshair', 'skewnono:recipe-open:crosshair', true)
