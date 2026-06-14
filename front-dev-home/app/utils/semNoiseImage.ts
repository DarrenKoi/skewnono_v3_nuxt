// Browser-only helper. Renders a deterministic SEM-noise placeholder PNG that
// mirrors EbeamRecipeOpenSemNoise (a fixed CSS-gradient texture on #23201B), so
// the Excel export shows the same placeholder the compare matrix shows on screen.
//
// IMPORTANT: do NOT import this from recipeCompare.ts. That module is run under
// `node --test`, which has no `document`/`canvas`. The compare view (browser)
// calls this and passes the resulting data URL into downloadCompareWorkbook.

export type SemRole = 'address' | 'measure'

export function renderSemNoisePng(role: SemRole, size = 180): string {
  const canvas = document.createElement('canvas')
  canvas.width = size
  canvas.height = size
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''

  // base fill (matches SemNoise background #23201B)
  ctx.fillStyle = '#23201B'
  ctx.fillRect(0, 0, size, size)

  // diagonal light lines (~45deg): 2px stroke, 5px pitch
  ctx.save()
  ctx.translate(size / 2, size / 2)
  ctx.rotate(Math.PI / 4)
  ctx.translate(-size, -size)
  ctx.strokeStyle = 'rgba(255,255,255,0.04)'
  ctx.lineWidth = 2
  for (let y = 0; y < size * 2; y += 5) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(size * 2, y)
    ctx.stroke()
  }
  ctx.restore()

  // diagonal dark lines (~-30deg): 1px stroke, 3px pitch
  ctx.save()
  ctx.translate(size / 2, size / 2)
  ctx.rotate(-Math.PI / 6)
  ctx.translate(-size, -size)
  ctx.strokeStyle = 'rgba(0,0,0,0.18)'
  ctx.lineWidth = 1
  for (let y = 0; y < size * 2; y += 3) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(size * 2, y)
    ctx.stroke()
  }
  ctx.restore()

  // soft radial highlights
  const glow = (cx: number, cy: number, r: number, alpha: number) => {
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r)
    g.addColorStop(0, `rgba(255,255,255,${alpha})`)
    g.addColorStop(1, 'rgba(255,255,255,0)')
    ctx.fillStyle = g
    ctx.fillRect(0, 0, size, size)
  }
  glow(size * 0.30, size * 0.40, size * 0.60, 0.07)
  glow(size * 0.70, size * 0.70, size * 0.55, 0.05)

  // role badge (MEAS / ADDR) top-left
  const isMeas = role === 'measure'
  const label = isMeas ? 'MEAS' : 'ADDR'
  ctx.font = `bold ${Math.round(size * 0.066)}px monospace`
  ctx.textBaseline = 'middle'
  const padX = size * 0.04
  const textW = ctx.measureText(label).width
  const bx = size * 0.04
  const by = size * 0.04
  const bw = textW + padX * 2
  const bh = size * 0.11
  ctx.fillStyle = isMeas ? '#2f6df0' : '#1f1b16'
  ctx.fillRect(bx, by, bw, bh)
  ctx.fillStyle = '#ffffff'
  ctx.fillText(label, bx + padX, by + bh / 2 + size * 0.004)

  return canvas.toDataURL('image/png')
}
