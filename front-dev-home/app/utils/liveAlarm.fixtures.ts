// Test-only builder for LiveAlarmEvent. Lives beside the type rather than
// inside one test file because two suites need it, and because the contract
// has 19 fields: an inline literal per suite means every field the backend
// adds has to be pasted into both, and a suite that skips one stops compiling
// for a reason unrelated to what it tests.
//
// Not imported by any app module, so it is never bundled.
import type { LiveAlarmEvent } from './liveAlarm.ts'

export const makeAlarmEvent = (over: Partial<LiveAlarmEvent> = {}): LiveAlarmEvent => ({
  id: '881423',
  rawid: '881423',
  eqp_id: 'EQ1',
  alarm_modelname: 'CG6300',
  alid: '9006',
  al_code: 'C06',
  al_type: 'warning',
  kind: 'align',
  alarm_name: 'ALIGNMENT FAIL',
  occurred_at: '2026-07-23 10:00:00+09:00',
  occurred_epoch: 1,
  lot_id: 'NX4201.1',
  cassette_id: 'FOUP103',
  recipe_id: '',
  ppid: '',
  operation_desc: '',
  step_id: '1004',
  lot_type_cd: 'PROD',
  meseventname: 'waferload',
  eq_stat: 'proc',
  ...over
})
