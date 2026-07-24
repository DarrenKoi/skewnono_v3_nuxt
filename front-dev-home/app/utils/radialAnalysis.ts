import { quantileSorted } from './stats.ts'

export type RadialModel = 'none' | 'linear' | 'quadratic' | 'cubic'
export type RadialBandMode = 'none' | 'iqr' | 'confidence' | 'prediction'

export interface RadialSample {
  sequence: number
  radius: number
  value: number
  x?: number
  y?: number
  sector?: string
}

export interface RadialAnalyzedPoint extends RadialSample {
  fitted: number | null
  residual: number | null
  leverage: number | null
}

export interface RadialCurvePoint {
  radius: number
  value: number
  confidenceLower: number | null
  confidenceUpper: number | null
  predictionLower: number | null
  predictionUpper: number | null
}

export interface RadialBin {
  radius: number
  q1: number
  median: number
  q3: number
  count: number
}

export interface RadialFitMetrics {
  n: number
  distinctRadii: number
  parameterCount: number
  radiusMin: number
  radiusMax: number
  radiusSpan: number
  r2: number | null
  adjustedR2: number | null
  rmse: number | null
  residualStd: number | null
  residualMad: number | null
  cvRmse: number | null
  spanDelta: number | null
  maxAbsResidual: number | null
  maxResidualSequence: number | null
}

export interface RadialProfileResult {
  model: RadialModel
  degree: number | null
  status: 'raw' | 'fitted' | 'insufficient'
  warning: string | null
  points: RadialAnalyzedPoint[]
  curve: RadialCurvePoint[]
  bins: RadialBin[]
  /** Coefficients use normalized radius t=(r-mid)/halfSpan, low order first. */
  coefficients: number[] | null
  metrics: RadialFitMetrics
}

export interface RadialAnalysisOptions {
  model?: RadialModel
  binCount?: number
  curveSteps?: number
}

const MODEL_DEGREE: Record<Exclude<RadialModel, 'none'>, number> = {
  linear: 1,
  quadratic: 2,
  cubic: 3
}

const dot = (a: number[], b: number[]): number => {
  let sum = 0
  for (let i = 0; i < a.length; i++) sum += a[i]! * b[i]!
  return sum
}

const backSolve = (R: number[][], b: number[]): number[] | null => {
  const n = b.length
  const x = new Array<number>(n).fill(0)
  for (let i = n - 1; i >= 0; i--) {
    const pivot = R[i]![i]!
    if (Math.abs(pivot) < 1e-11) return null
    let rhs = b[i]!
    for (let j = i + 1; j < n; j++) rhs -= R[i]![j]! * x[j]!
    x[i] = rhs / pivot
  }
  return x
}

// Modified Gram-Schmidt QR. Radius is normalized to [-1, 1] before this runs,
// avoiding the large x^6 terms used by the previous normal-equation fit.
const qrLeastSquares = (X: number[][], y: number[]) => {
  const n = X.length
  const p = X[0]?.length ?? 0
  if (n === 0 || p === 0) return null

  const qCols: number[][] = []
  const R = Array.from({ length: p }, () => new Array<number>(p).fill(0))
  for (let j = 0; j < p; j++) {
    const v = X.map(row => row[j]!)
    for (let i = 0; i < j; i++) {
      const projection = dot(qCols[i]!, v)
      R[i]![j] = projection
      for (let k = 0; k < n; k++) v[k] = v[k]! - projection * qCols[i]![k]!
    }
    const norm = Math.sqrt(dot(v, v))
    if (norm < 1e-11) return null
    R[j]![j] = norm
    qCols[j] = v.map(value => value / norm)
  }

  const qty = qCols.map(q => dot(q, y))
  const coefficients = backSolve(R, qty)
  if (!coefficients) return null

  // (X'X)^-1 = R^-1 (R^-1)' — used for leverage and fit uncertainty.
  const rInverse = Array.from({ length: p }, () => new Array<number>(p).fill(0))
  for (let col = 0; col < p; col++) {
    const unit = new Array<number>(p).fill(0)
    unit[col] = 1
    const solved = backSolve(R, unit)
    if (!solved) return null
    for (let row = 0; row < p; row++) rInverse[row]![col] = solved[row]!
  }
  const covarianceBase = Array.from({ length: p }, (_, i) =>
    Array.from({ length: p }, (_, j) => {
      let sum = 0
      for (let k = 0; k < p; k++) sum += rInverse[i]![k]! * rInverse[j]![k]!
      return sum
    })
  )

  return { coefficients, covarianceBase }
}

const polynomialRow = (t: number, degree: number): number[] =>
  Array.from({ length: degree + 1 }, (_, i) => t ** i)

const evaluate = (coefficients: number[], row: number[]): number =>
  dot(coefficients, row)

const quadraticForm = (row: number[], matrix: number[][]): number => {
  let sum = 0
  for (let i = 0; i < row.length; i++) {
    for (let j = 0; j < row.length; j++) sum += row[i]! * matrix[i]![j]! * row[j]!
  }
  return Math.max(0, sum)
}

const median = (values: number[]): number => {
  const sorted = [...values].sort((a, b) => a - b)
  return quantileSorted(sorted, 0.5)
}

const radialBins = (samples: RadialSample[], requested?: number): RadialBin[] => {
  if (samples.length === 0) return []
  const radii = samples.map(sample => sample.radius)
  const min = Math.min(...radii)
  const max = Math.max(...radii)
  const distinct = new Set(radii.map(radius => radius.toPrecision(12))).size
  if (max === min) {
    const values = samples.map(sample => sample.value).sort((a, b) => a - b)
    return [{
      radius: min,
      q1: quantileSorted(values, 0.25),
      median: quantileSorted(values, 0.5),
      q3: quantileSorted(values, 0.75),
      count: values.length
    }]
  }

  const automatic = Math.max(4, Math.min(10, Math.round(Math.sqrt(samples.length))))
  const count = Math.max(1, Math.min(distinct, Math.round(requested ?? automatic)))
  const buckets = Array.from({ length: count }, () => [] as RadialSample[])
  for (const sample of samples) {
    const index = Math.min(count - 1, Math.floor(((sample.radius - min) / (max - min)) * count))
    buckets[index]!.push(sample)
  }
  return buckets.flatMap((bucket) => {
    if (bucket.length === 0) return []
    const values = bucket.map(sample => sample.value).sort((a, b) => a - b)
    return [{
      radius: median(bucket.map(sample => sample.radius)),
      q1: quantileSorted(values, 0.25),
      median: quantileSorted(values, 0.5),
      q3: quantileSorted(values, 0.75),
      count: values.length
    }]
  })
}

// Two-sided 95% Student-t critical values. Linear interpolation is unnecessary
// here because degrees of freedom are integers; normal limit after df=30.
const T95 = [
  0, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262,
  2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093,
  2.086, 2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042
]
const t95 = (degreesOfFreedom: number): number =>
  degreesOfFreedom <= 30 ? T95[Math.max(1, degreesOfFreedom)]! : 1.96

const emptyMetrics = (samples: RadialSample[]): RadialFitMetrics => {
  const radii = samples.map(sample => sample.radius)
  const radiusMin = radii.length ? Math.min(...radii) : 0
  const radiusMax = radii.length ? Math.max(...radii) : 0
  return {
    n: samples.length,
    distinctRadii: new Set(radii.map(radius => radius.toPrecision(12))).size,
    parameterCount: 0,
    radiusMin,
    radiusMax,
    radiusSpan: radiusMax - radiusMin,
    r2: null,
    adjustedR2: null,
    rmse: null,
    residualStd: null,
    residualMad: null,
    cvRmse: null,
    spanDelta: null,
    maxAbsResidual: null,
    maxResidualSequence: null
  }
}

export const analyzeRadialProfile = (
  input: RadialSample[],
  options: RadialAnalysisOptions = {}
): RadialProfileResult => {
  const model = options.model ?? 'linear'
  const samples = input
    .filter(sample => Number.isFinite(sample.radius) && Number.isFinite(sample.value) && sample.radius >= 0)
    .sort((a, b) => a.radius - b.radius || a.sequence - b.sequence)
  const bins = radialBins(samples, options.binCount)
  const metrics = emptyMetrics(samples)

  if (model === 'none') {
    return {
      model,
      degree: null,
      status: 'raw',
      warning: null,
      points: samples.map(sample => ({ ...sample, fitted: null, residual: null, leverage: null })),
      curve: [],
      bins,
      coefficients: null,
      metrics
    }
  }

  const degree = MODEL_DEGREE[model]
  const parameterCount = degree + 1
  metrics.parameterCount = parameterCount
  if (samples.length < parameterCount + 1) {
    return {
      model,
      degree,
      status: 'insufficient',
      warning: `${model} fit requires at least ${parameterCount + 1} measured sites`,
      points: samples.map(sample => ({ ...sample, fitted: null, residual: null, leverage: null })),
      curve: [],
      bins,
      coefficients: null,
      metrics
    }
  }
  if (metrics.distinctRadii < parameterCount || metrics.radiusSpan <= 1e-9) {
    return {
      model,
      degree,
      status: 'insufficient',
      warning: `${model} fit requires at least ${parameterCount} distinct radii`,
      points: samples.map(sample => ({ ...sample, fitted: null, residual: null, leverage: null })),
      curve: [],
      bins,
      coefficients: null,
      metrics
    }
  }

  const mid = (metrics.radiusMin + metrics.radiusMax) / 2
  const halfSpan = metrics.radiusSpan / 2
  const normalized = samples.map(sample => (sample.radius - mid) / halfSpan)
  const X = normalized.map(t => polynomialRow(t, degree))
  const y = samples.map(sample => sample.value)
  const solved = qrLeastSquares(X, y)
  if (!solved) {
    return {
      model,
      degree,
      status: 'insufficient',
      warning: 'fit is singular for the available radius layout',
      points: samples.map(sample => ({ ...sample, fitted: null, residual: null, leverage: null })),
      curve: [],
      bins,
      coefficients: null,
      metrics
    }
  }

  const fitted = X.map(row => evaluate(solved.coefficients, row))
  const residuals = y.map((value, i) => value - fitted[i]!)
  const leverages = X.map(row => quadraticForm(row, solved.covarianceBase))
  const sse = residuals.reduce((sum, residual) => sum + residual ** 2, 0)
  const meanY = y.reduce((sum, value) => sum + value, 0) / y.length
  const total = y.reduce((sum, value) => sum + (value - meanY) ** 2, 0)
  const df = samples.length - parameterCount
  const residualVariance = df > 0 ? sse / df : null
  const residualMedian = median(residuals)
  const residualMad = 1.4826 * median(residuals.map(residual => Math.abs(residual - residualMedian)))
  const r2 = total > 0 ? 1 - sse / total : null
  const adjustedR2 = r2 != null && df > 0
    ? 1 - (1 - r2) * ((samples.length - 1) / df)
    : null
  const press = residuals.map((residual, i) => {
    const divisor = 1 - leverages[i]!
    return divisor > 1e-9 ? residual / divisor : null
  })
  const validPress = press.filter((value): value is number => value != null && Number.isFinite(value))
  const maxIndex = residuals.reduce((best, residual, i) =>
    Math.abs(residual) > Math.abs(residuals[best]!) ? i : best, 0)

  Object.assign(metrics, {
    r2,
    adjustedR2,
    rmse: Math.sqrt(sse / samples.length),
    residualStd: residualVariance != null ? Math.sqrt(residualVariance) : null,
    residualMad,
    cvRmse: validPress.length === samples.length
      ? Math.sqrt(validPress.reduce((sum, value) => sum + value ** 2, 0) / validPress.length)
      : null,
    spanDelta: fitted[fitted.length - 1]! - fitted[0]!,
    maxAbsResidual: Math.abs(residuals[maxIndex]!),
    maxResidualSequence: samples[maxIndex]!.sequence
  })

  const critical = residualVariance != null ? t95(df) : null
  const steps = Math.max(20, Math.min(240, Math.round(options.curveSteps ?? 80)))
  const curve = Array.from({ length: steps + 1 }, (_, i): RadialCurvePoint => {
    const radius = metrics.radiusMin + (metrics.radiusSpan * i) / steps
    const t = (radius - mid) / halfSpan
    const row = polynomialRow(t, degree)
    const value = evaluate(solved.coefficients, row)
    if (residualVariance == null || critical == null) {
      return { radius, value, confidenceLower: null, confidenceUpper: null, predictionLower: null, predictionUpper: null }
    }
    const leverage = quadraticForm(row, solved.covarianceBase)
    const confidenceMargin = critical * Math.sqrt(residualVariance * leverage)
    const predictionMargin = critical * Math.sqrt(residualVariance * (1 + leverage))
    return {
      radius,
      value,
      confidenceLower: value - confidenceMargin,
      confidenceUpper: value + confidenceMargin,
      predictionLower: value - predictionMargin,
      predictionUpper: value + predictionMargin
    }
  })

  return {
    model,
    degree,
    status: 'fitted',
    warning: null,
    points: samples.map((sample, i) => ({
      ...sample,
      fitted: fitted[i]!,
      residual: residuals[i]!,
      leverage: leverages[i]!
    })),
    curve,
    bins,
    coefficients: solved.coefficients,
    metrics
  }
}

// The y-axis window for a rendered radial profile: the extent of everything the
// chart actually draws for the given band mode — scatter values, fit curve,
// radial-median line, and the active band's bounds — padded so points don't sit
// on the frame. Explicit min/max (instead of ECharts `scale: true`) guarantees
// the axis re-fits every new data selection; a rebuilt option can never carry a
// previous selection's window along.
export const radialYExtent = (
  profile: RadialProfileResult,
  band: RadialBandMode
): { min: number, max: number } | null => {
  const values: number[] = []
  for (const p of profile.points) values.push(p.value)
  for (const c of profile.curve) {
    values.push(c.value)
    if (band === 'confidence' && c.confidenceLower != null && c.confidenceUpper != null) {
      values.push(c.confidenceLower, c.confidenceUpper)
    }
    if (band === 'prediction' && c.predictionLower != null && c.predictionUpper != null) {
      values.push(c.predictionLower, c.predictionUpper)
    }
  }
  for (const b of profile.bins) {
    values.push(b.median)
    if (band === 'iqr') values.push(b.q1, b.q3)
  }

  const finite = values.filter(v => Number.isFinite(v))
  if (finite.length === 0) return null
  const lo = Math.min(...finite)
  const hi = Math.max(...finite)
  // 6% headroom each side; a flat profile still gets a visible window.
  const pad = (hi - lo) * 0.06 || Math.max(Math.abs(hi) * 0.05, 0.5)
  return { min: lo - pad, max: hi + pad }
}
