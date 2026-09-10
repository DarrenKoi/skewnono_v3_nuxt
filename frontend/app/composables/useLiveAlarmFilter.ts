// Which alarm kinds the 라이브 알람 board is showing.
//
// One key across every fab and tool, deliberately: a viewer is doing align
// triage or PPID triage today, not choosing a different lens per fab. Twenty
// per-fab keys would be twenty things to keep in sync for a preference that is
// really about the person, not the fab.
//
// Persisted rather than component-local because the board unmounts on every
// fab switch, and re-picking the mode after each navigation is exactly the
// friction this control is meant to remove.
import type { AlarmFilter } from '~/utils/liveAlarm'

const VALID: AlarmFilter[] = ['all', 'align', 'meas']

export const useLiveAlarmFilter = () =>
  usePersistedState<AlarmFilter>(
    'live-alarm:filter',
    'skewnono:live-alarm.filter',
    {
      default: () => 'all',
      // Anything else in storage — a stale value from a future rename, or a
      // hand-edited key — falls back to the default rather than rendering a
      // board with no matching mode.
      normalize: parsed =>
        VALID.includes(parsed as AlarmFilter) ? (parsed as AlarmFilter) : 'all',
      // 'all' is the default, so storage only ever holds the deviation from
      // it: switching back to 전부 보기 drops the key instead of writing it.
      isEmpty: value => value === 'all'
    }
  )
