// Whether recipe image modals draw the tool's marks (crosshair + white-box centre)
// from the image's cond.txt. One reviewer preference shared by every modal and
// kept across reloads; on by default because the marks are the point of
// opening the image at full size.
export const useCondCrosshair = () =>
  persistedFlag('recipe-open-crosshair', 'skewnono:recipe-open:crosshair', true)

// Whether parameter images draw the measurement box (MeasMarks). Separate from
// the crosshair: the two answer different questions and crowd one another.
export const useMeasBox = () =>
  persistedFlag('recipe-open-meas-box', 'skewnono:recipe-open:meas-box', true)
