// 횡전개 "보유" 리스트를 recipe_version 단위로 쪼개는 순수 로직.
//
// One flat table hides the thing the page exists to answer — which tools are on
// which revision. Splitting per version turns "scan the version column" into
// "read the group headers", and lets version/generated_at leave the row cells
// entirely (they are constant inside a group).

import type { LateralRecipeRow, LateralRecipeVersion } from '~/composables/useLateralRecipeApi'

export interface LateralVersionGroup {
  key: string
  version: number | null
  generatedAt: string | null
  rows: LateralRecipeRow[]
}

export const UNKNOWN_VERSION_KEY = 'unknown'

export const groupReadyRowsByVersion = (
  rows: LateralRecipeRow[],
  versions: LateralRecipeVersion[] = []
): LateralVersionGroup[] => {
  const generatedAtByVersion = new Map<number, string>()
  for (const version of versions) {
    generatedAtByVersion.set(version.recipe_version, version.generated_at)
  }

  const buckets = new Map<string, LateralVersionGroup>()

  for (const row of rows) {
    if (!row.recipe_ready) continue

    const version = row.recipe_version
    const key = version === null ? UNKNOWN_VERSION_KEY : String(version)
    let bucket = buckets.get(key)

    if (!bucket) {
      bucket = {
        key,
        version,
        generatedAt: version === null ? null : generatedAtByVersion.get(version) ?? null,
        rows: []
      }
      buckets.set(key, bucket)
    }

    // A row's own timestamp backfills the header when the response's
    // `versions[]` doesn't carry this revision.
    if (bucket.generatedAt === null) {
      bucket.generatedAt = row.recipe_generated_at
    }

    bucket.rows.push(row)
  }

  for (const bucket of buckets.values()) {
    bucket.rows.sort((a, b) => a.eqp_id.localeCompare(b.eqp_id))
  }

  // Latest version first; the version-less bucket always sinks to the bottom.
  return [...buckets.values()].sort((a, b) => {
    if (a.version === null) return 1
    if (b.version === null) return -1
    return b.version - a.version
  })
}
