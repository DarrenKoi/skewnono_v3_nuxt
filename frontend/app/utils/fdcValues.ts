import { median } from './stats.ts'

// Pure: parse one fdc doc's `values` list (which starts with the fdc_key)
// into a typed shape per §6.3. The judgment token is the first non-numeric
// string at/after index 3; numeric values after it form the profile.

export type FdcKey = 'TemperatureEChuck' | 'LaserPower' | 'SPMVoltages' | 'ContactpinConductionInfo'

export interface TemperatureValue { position: string, temp: number }
export interface LaserPowerValue { pairs: { x: number, y: number }[] }
export interface SpmVoltagesValue { channel: string, fitModel: string, profile: number[] }
export interface ContactpinValue { channel: string, judgment: string, values: number[] }

export type FdcParsed
  = | { key: 'TemperatureEChuck', data: TemperatureValue }
    | { key: 'LaserPower', data: LaserPowerValue }
    | { key: 'SPMVoltages', data: SpmVoltagesValue }
    | { key: 'ContactpinConductionInfo', data: ContactpinValue }
    | { key: string, data: null }

// A comma decimal ('25,0') is written by some tools (the network_fdc_cdsem
// sample carries one); read it as 25.0 rather than dropping it.
const COMMA_DECIMAL = /^\s*-?\d+,\d+\s*$/
const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  if (Number.isFinite(n)) return n
  return typeof v === 'string' && COMMA_DECIMAL.test(v) ? Number(v.replace(',', '.')) : NaN
}
const isNumeric = (v: unknown): boolean => Number.isFinite(num(v))

// Index of the first non-numeric token at/after `from` (the judgment slot).
const judgmentIndex = (values: unknown[], from: number): number => {
  for (let i = from; i < values.length; i++) if (!isNumeric(values[i])) return i
  return -1
}

export const parseFdcValues = (values: unknown[]): FdcParsed => {
  const key = String(values[0] ?? '')

  if (key === 'TemperatureEChuck') {
    return { key, data: { position: String(values[2] ?? ''), temp: num(values[3]) } }
  }

  if (key === 'LaserPower') {
    return {
      key,
      data: {
        pairs: [
          { x: num(values[2]), y: num(values[3]) },
          { x: num(values[4]), y: num(values[5]) }
        ]
      }
    }
  }

  if (key === 'SPMVoltages') {
    const channel = String(values[2] ?? '')
    const ji = judgmentIndex(values, 3)
    const fitModel = ji >= 0 ? String(values[ji]) : ''
    // CG5000 writes no fit-model token: the profile follows the three header
    // numbers directly (office 확인 2026-09-29).
    const profile = values.slice(ji >= 0 ? ji + 1 : 6).map(num).filter(Number.isFinite)
    return { key, data: { channel, fitModel, profile } }
  }

  if (key === 'ContactpinConductionInfo') {
    const channel = String(values[2] ?? '')
    const ji = judgmentIndex(values, 3)
    const judgment = ji >= 0 ? String(values[ji]) : ''
    // Positional, NOT filtered: the first four are the margin numbers and the
    // last is the counter, so a dropped cell must not shift the rest.
    const vals = (ji >= 0 ? values.slice(ji + 1) : []).map(num)
    return { key, data: { channel, judgment, values: vals } }
  }

  return { key, data: null }
}

export const contactpinState = (judgment: string): 'ok' | 'warn' | 'bad' | 'unknown' => {
  if (judgment === 'Conduction') return 'ok'
  if (judgment === 'UnstableConduction') return 'warn'
  if (judgment === 'NotConduction') return 'bad'
  return 'unknown'
}

// Raw-doc accessors shared with FdcPanel, so the doc shape is read in one place.
export const fdcDocValues = (doc: Record<string, unknown>): unknown[] => Array.isArray(doc.values) ? doc.values : []
export const fdcDocTs = (doc: Record<string, unknown>): string => String(doc.timestamp ?? '')
export const fdcEpoch = (ts: string): number => new Date(ts.replace(' ', 'T')).getTime()

export const contactpinRows = (docs: Record<string, unknown>[]) => {
  const previous = new Map<string, { time: number, counter: number }>()
  return [...docs].sort((a, b) => fdcDocTs(a).localeCompare(fdcDocTs(b))).map((doc) => {
    const parsed = parseFdcValues(fdcDocValues(doc))
    if (parsed.key !== 'ContactpinConductionInfo') return null
    const { channel, judgment, values } = parsed.data as ContactpinValue
    const raw = values.slice(0, 4)
    const last = values[values.length - 1]
    const counter = values.length > 4 && Number.isFinite(last) ? last : undefined
    const time = fdcEpoch(fdcDocTs(doc))
    const prev = previous.get(channel)
    // First row of a channel, a zero gap or a counter reset has no rate.
    const rate = prev && counter !== undefined && time > prev.time && counter >= prev.counter
      ? (counter - prev.counter) / ((time - prev.time) / 86400000)
      : null
    if (Number.isFinite(time) && counter !== undefined) previous.set(channel, { time, counter })
    return {
      ts: fdcDocTs(doc), channel, judgment, state: contactpinState(judgment), values: raw,
      spread: raw.length === 4 && raw.every(Number.isFinite) ? Math.max(...raw) - Math.min(...raw) : null, rate
    }
  }).filter(row => row !== null)
}

export const spmDeviationSeries = (docs: Record<string, unknown>[]) => {
  const channels = new Map<string, { ts: string, profile: number[] }[]>()
  for (const doc of docs) {
    const parsed = parseFdcValues(fdcDocValues(doc))
    if (parsed.key !== 'SPMVoltages') continue
    const { channel, profile } = parsed.data as SpmVoltagesValue
    const items = channels.get(channel) ?? []
    items.push({ ts: fdcDocTs(doc), profile })
    channels.set(channel, items)
  }
  return [...channels.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([channel, items]) => {
    const counts = new Map<number, number>()
    for (const item of items) counts.set(item.profile.length, (counts.get(item.profile.length) ?? 0) + 1)
    const length = [...counts.entries()].sort((a, b) => b[1] - a[1] || b[0] - a[0])[0]?.[0] ?? 0
    const valid = items.filter(item => item.profile.length === length && length > 0)
    const center = Array.from({ length }, (_, i) => median(valid.map(item => item.profile[i]!)))
    const points = valid.map(item => ({
      ts: item.ts,
      value: Math.sqrt(item.profile.reduce((sum, v, i) => sum + (v - center[i]!) ** 2, 0) / length)
    })).sort((a, b) => a.ts.localeCompare(b.ts))
    return { channel, points }
  })
}

export const fdcDailyMeans = (points: { ts: string, value: number }[]) => {
  const days = new Map<string, { sum: number, count: number }>()
  for (const { ts, value } of points) {
    if (!Number.isFinite(value)) continue
    const day = ts.slice(0, 10)
    const current = days.get(day) ?? { sum: 0, count: 0 }
    current.sum += value
    current.count++
    days.set(day, current)
  }
  return [...days.entries()].sort(([a], [b]) => a.localeCompare(b))
    .map(([day, { sum, count }]) => ({ ts: `${day}T12:00:00`, value: sum / count }))
}
