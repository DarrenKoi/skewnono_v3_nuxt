// Pure: parse one fdc doc's `values` list (which starts with the fdc_key)
// into a typed shape per §6.3. The judgment token is the first non-numeric
// string at/after index 3; numeric values after it form the profile.

export type FdcKey = 'TemperatureEChuck' | 'LaserPower' | 'SPMVoltages' | 'ContactpinConductionInfo'

export interface TemperatureValue { position: string, temp: number }
export interface LaserPowerValue { pairs: { x: number, y: number }[] }
export interface SpmVoltagesValue { channel: string, judgment: string, profile: number[] }
export interface ContactpinValue { channel: string, judgment: string, values: number[] }

export type FdcParsed
  = | { key: 'TemperatureEChuck', data: TemperatureValue }
    | { key: 'LaserPower', data: LaserPowerValue }
    | { key: 'SPMVoltages', data: SpmVoltagesValue }
    | { key: 'ContactpinConductionInfo', data: ContactpinValue }
    | { key: string, data: null }

const num = (v: unknown): number => {
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : NaN
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
    const judgment = ji >= 0 ? String(values[ji]) : ''
    const profile = (ji >= 0 ? values.slice(ji + 1) : []).map(num).filter(Number.isFinite)
    return { key, data: { channel, judgment, profile } }
  }

  if (key === 'ContactpinConductionInfo') {
    const channel = String(values[2] ?? '')
    const ji = judgmentIndex(values, 3)
    const judgment = ji >= 0 ? String(values[ji]) : ''
    const vals = (ji >= 0 ? values.slice(ji + 1) : []).map(num).filter(Number.isFinite)
    return { key, data: { channel, judgment, values: vals } }
  }

  return { key, data: null }
}
