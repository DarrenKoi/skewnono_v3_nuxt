/**
 * Who the SPA thinks the caller is.
 *
 * One `useState` cell shared by the route middleware, the identify page and
 * anything greeting the user by name. The middleware runs on every navigation,
 * so a per-caller fetch would put a request in front of each one — and `/api/*`
 * is rate-limited to 50 requests per 5 seconds.
 *
 * Deliberately NOT persisted. The identity's real home is the Flask session
 * cookie; a localStorage copy could disagree with it after the session expires
 * or after a sign-out in another tab, and the stale copy would win on boot.
 */

export interface Member {
  empno: string
  emp_nm: string | null
  dept_nm: string | null
  organ_cd: string | null
  upper_organ_nm: string | null
}

/** The step of the backend's identity chain that named this caller. */
export type IdentitySource = 'token' | 'cookie' | 'declared' | 'local' | 'anonymous'

export interface Identity {
  user_id: string
  identity_source: IdentitySource | null
  is_admin: boolean
  /** Only meaningful for a `declared` identity — a cookie one is authoritative
   * rather than verified, which is a stronger thing. */
  verified: boolean
  member: Member | null
}

export const useIdentity = () => {
  const identity = useState<Identity | null>('identity', () => null)
  const pending = useState<boolean>('identity-pending', () => false)

  /**
   * True only for the shared fallback id. A `declared` identity is weak but
   * attributable, so it is NOT anonymous — that distinction is the whole
   * point of the feature and decides whether the gate fires.
   */
  const isAnonymous = computed(() => identity.value?.identity_source === 'anonymous')

  const refresh = async () => {
    pending.value = true
    try {
      identity.value = await $fetch<Identity>('/api/me')
    } catch {
      // A failed /api/me must not strand the SPA. Leaving `identity` null lets
      // the middleware fall through rather than trapping the user behind a
      // gate it could not evaluate — the backend is what actually refuses data.
      identity.value = null
    } finally {
      pending.value = false
    }
  }

  /** Declare an identity. Returns null on success, or the message to show. */
  const identify = async (empno: string, empNm: string): Promise<string | null> => {
    try {
      identity.value = await $fetch<Identity>('/api/identify', {
        method: 'POST',
        body: { empno, emp_nm: empNm }
      })
      return null
    } catch (error: unknown) {
      const message = (error as { data?: { message?: string } })?.data?.message
      return message ?? '확인에 실패했습니다. 잠시 후 다시 시도해 주세요'
    }
  }

  /** "본인이 아닙니다" — drop the declaration. The response describes who the
   * caller becomes, which may still be a cookie identity. */
  const signOut = async () => {
    identity.value = await $fetch<Identity>('/api/identify', { method: 'DELETE' })
  }

  return { identity, pending, isAnonymous, refresh, identify, signOut }
}
