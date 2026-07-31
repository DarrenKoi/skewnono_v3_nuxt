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

  /**
   * 여러 fab 의 룰을 한 번에. 룰이 없는 fab 은 `null` 입니다.
   *
   * **404 만** null 로 바꿉니다. 429·5xx 는 그대로 던집니다 — "이 fab 에는 룰이
   * 없다"(D22 로 폐기된 M 계열)와 "물어보지 못했다" 는 다른 사실입니다. 후자를
   * 조용히 "룰 없음" 으로 칠하면, 사무실에서 Redis 가 죽었을 때 화면이 오류 대신
   * 전 lot "판정 없음" 이라는 그럴듯한 거짓을 보여줍니다.
   */
  const fetchRulesForFabs = async (
    facIds: string[]
  ): Promise<Record<string, RuleVersion | null>> => {
    const unique = [...new Set(facIds)]
    const entries = await Promise.all(unique.map(async (facId) => {
      try {
        return [facId, await fetchRules(facId)] as const
      } catch (err) {
        const status = (err as { statusCode?: number, status?: number }).statusCode
          ?? (err as { status?: number }).status
        if (status === 404) return [facId, null] as const
        throw err
      }
    }))
    return Object.fromEntries(entries)
  }

  return { fetchRules, fetchRulesForFabs }
}
