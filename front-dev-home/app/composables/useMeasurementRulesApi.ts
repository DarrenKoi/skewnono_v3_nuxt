import { joinApiPath } from '~/utils/apiPath'
import type { RuleVersion } from '~/utils/ruleEngine'

// RuleVersion (the GET /rules payload shape) lives with the other rule types in
// ruleEngine.ts §2. Mirrors back_dev_home/.../rules.py. save/history/rollback (D12) later.

export const useMeasurementRulesApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const fetchRules = async (facId: string): Promise<RuleVersion> => {
    return await $fetch<RuleVersion>(
      joinApiPath(base, '/cdsem/device-statistics/rules'),
      { query: { fac_id: facId } }
    )
  }

  return { fetchRules }
}
