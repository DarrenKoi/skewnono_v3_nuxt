// Pure helpers for the live alarm board. Everything here is deterministic
// and clock-free so the board's time-dependent behaviour can be tested
// without faking timers.

// Mirrors AlarmEvent in back_dev_home/.../live_alarm/contracts.py, which is
// itself the office DataFrame flattened to snake_case. Every field is a string
// but occurred_epoch, and none is optional: the server sends "" rather than
// omitting a key, so a row never has to be tested for presence before display.
export interface LiveAlarmEvent {
  id: string
  rawid: string
  eqp_id: string
  alarm_modelname: string
  alid: string
  al_code: string
  al_type: string
  // The coarse grouping the badge and the counters use. MANY alids share one
  // kind (9007 and 9035 are both 'meas'), so `alarm_name` is what says which
  // failure it actually was.
  kind: 'align' | 'meas'
  alarm_name: string
  occurred_at: string
  occurred_epoch: number
  lot_id: string
  cassette_id: string
  recipe_id: string
  ppid: string
  operation_desc: string
  step_id: string
  lot_type_cd: string
  meseventname: string
  eq_stat: string
}

export type FeedStatus = 'live' | 'stale' | 'not_configured'

export interface LiveAlarmPayload {
  fab_name: string
  tool_type: string
  feed_status: FeedStatus
  // Last SUCCESSFUL office fetch — null when there has never been one. The
  // server stamps it only on success, so it ages during an outage rather
  // than claiming freshness over data that never arrived.
  fetched_at: string | null
  covered_since: string | null
  server_now: string
  board_window_sec: number
  // Alarms in this FACILITY's feed whose equipment is absent from the
  // sem_list roster, so they belong to no fab. Shown as a count, never as
  // rows: they cannot be attributed to any fab, let alone this one. Scope is
  // the facility, not the fab — sibling fabs (M16A/B/C) read one shared board
  // and therefore report the same number.
  unmatched_count: number
  events: LiveAlarmEvent[]
}

// Which ids arrived since the previous poll. Per-viewer by design: "new"
// means new to the person watching, not new to the fab.
export const diffNewIds = (prev: string[], next: string[]): string[] => {
  const seen = new Set(prev)
  return next.filter(id => !seen.has(id))
}

export const formatElapsed = (ms: number): string => {
  if (ms < 1000) return '방금'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}초 전`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}분 전`
  return `${Math.floor(minutes / 60)}시간 전`
}

export const boardCounts = (events: LiveAlarmEvent[]): { align: number, meas: number } => ({
  align: events.filter(e => e.kind === 'align').length,
  meas: events.filter(e => e.kind === 'meas').length
})

// Badge text per kind. '측정 실패' rather than the old '측정 연속 실패': the
// retired 9100 was a consecutive-failure counter, while 9007/9035 fire on a
// single failed pattern detection or auto-measurement. AL_TEXT (alarm_name) is
// what distinguishes the two, so the badge stays the coarse label.
export const KIND_LABEL: Record<LiveAlarmEvent['kind'], string> = {
  align: 'Align Fail',
  meas: '측정 실패'
}

// How many distinct lots the board touches. Worth its own number because the
// alarm count alone reads the same whether one lot tripped four tools or four
// unrelated lots each tripped one — the first is a lot problem, the second a
// fleet problem, and they are acted on differently. Blank lot_ids are ignored
// rather than counted as one shared unknown lot.
export const distinctLotCount = (events: LiveAlarmEvent[]): number =>
  new Set(events.map(e => e.lot_id).filter(Boolean)).size
