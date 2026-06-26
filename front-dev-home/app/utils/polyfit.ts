// Least-squares polynomial fitting via the normal equations. Used by the
// skewvoir Radius Plot to draw the center-to-edge CD signature fit line.

// Solve the linear system A·x = b by Gaussian elimination with partial pivoting.
// Returns null if the matrix is singular (degenerate fit).
const solveLinear = (A: number[][], b: number[]): number[] | null => {
  const n = b.length
  // Augmented matrix copy so callers' arrays are untouched.
  const m = A.map((row, i) => [...row, b[i]!])

  for (let col = 0; col < n; col++) {
    // Partial pivot: move the largest-magnitude row into place for stability.
    let pivot = col
    for (let r = col + 1; r < n; r++) {
      if (Math.abs(m[r]![col]!) > Math.abs(m[pivot]![col]!)) pivot = r
    }
    if (Math.abs(m[pivot]![col]!) < 1e-12) return null
    ;[m[col], m[pivot]] = [m[pivot]!, m[col]!]

    for (let r = 0; r < n; r++) {
      if (r === col) continue
      const factor = m[r]![col]! / m[col]![col]!
      for (let c = col; c <= n; c++) m[r]![c]! -= factor * m[col]![c]!
    }
  }

  return m.map((row, i) => row[n]! / row[i]!)
}

/**
 * Fit y = c0 + c1·x + … + cd·x^d by least squares.
 * Returns coefficients [c0…cd], or null if the fit is degenerate. The effective
 * degree is clamped to the sample count so a handful of points can't overfit.
 */
export const polyfit = (xs: number[], ys: number[], degree: number): number[] | null => {
  const n = xs.length
  if (n === 0 || degree < 1) return null
  const d = Math.min(degree, n - 1)
  if (d < 1) return null

  // Normal equations: A[i][j] = Σ x^(i+j), rhs[i] = Σ y·x^i.
  const A: number[][] = []
  const rhs: number[] = []
  for (let i = 0; i <= d; i++) {
    A[i] = []
    for (let j = 0; j <= d; j++) {
      let s = 0
      for (let k = 0; k < n; k++) s += xs[k]! ** (i + j)
      A[i]![j] = s
    }
    let sb = 0
    for (let k = 0; k < n; k++) sb += ys[k]! * xs[k]! ** i
    rhs[i] = sb
  }

  return solveLinear(A, rhs)
}

// Evaluate a polynomial (Horner-free, coefficients low-order first) at x.
export const polyval = (coeffs: number[], x: number): number =>
  coeffs.reduce((acc, c, i) => acc + c * x ** i, 0)
