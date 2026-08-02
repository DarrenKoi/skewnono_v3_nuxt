// The row shape the comparison page's Lot 요약 table consumes: a bucket summary
// row, plus the rule verdict (lotHealth), plus the measurement profile
// (deviceProfile). Kept here rather than in either producer because it is the
// join of two independent surfaces — health comes from the rules API, the
// profile from recipe_params — and neither should have to know about the other.
import type { HealthAugmentedRow } from './lotHealth'
import type { DeviceProfile } from './deviceProfile'

export type ProfiledLotRow = HealthAugmentedRow & DeviceProfile & { has_profile: boolean }
