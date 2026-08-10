// Relative (not `~/`) so this module is importable by `npm test`, which runs
// the pure exports below under plain node.
import { joinApiPath } from '../utils/apiPath.ts'

export interface DownloadJobStatus {
  job_id: string
  status: 'running' | 'done' | 'error'
  done: number
  total: number
  ok: number
  ng: number
  failures: { name: string, error: string }[]
}

/** Shape $fetch rejects with: a FetchError carrying the parsed JSON body. */
interface DownloadErrorLike {
  statusCode?: number
  data?: { error?: string, code?: string }
  message?: string
}

// The backend's machine codes are precise but English and terse. Translate the
// ones a gallery user can actually provoke, so the banner says what to do next
// rather than echoing "too many active downloads".
const CODE_MESSAGES: Record<string, string> = {
  too_many_jobs: '동시 다운로드가 이미 최대입니다. 잠시 후 다시 시도해 주세요.',
  unknown_job: '다운로드 작업을 찾을 수 없습니다. 만료되었을 수 있습니다.',
  office_source_unavailable: '장비에 연결하지 못했습니다.',
  invalid_tool_ip: '장비 IP가 올바르지 않습니다.',
  office_configuration_error: '서버 설정이 올바르지 않습니다.'
}

/**
 * Turn anything thrown by a download call into text worth showing.
 *
 * Never returns an empty string: a blank error banner reads as "something
 * broke but we won't say what", which is what swallowing the error did.
 */
export const downloadErrorMessage = (err: unknown): string => {
  const e = (typeof err === 'object' && err !== null ? err : {}) as DownloadErrorLike
  const mapped = e.data?.code ? CODE_MESSAGES[e.data.code] : undefined
  if (mapped) return mapped
  const detail = e.data?.error || e.message
  if (detail && e.statusCode) return `${detail} (HTTP ${e.statusCode})`
  if (detail) return detail
  if (e.statusCode) return `HTTP ${e.statusCode}`
  return '알 수 없는 오류가 발생했습니다.'
}

export const useMsrImageApi = () => {
  const config = useRuntimeConfig()
  const base = config.public.apiBase

  const q = (eqp_ip: string, class_name: string, msr: string) =>
    `eqp_ip=${encodeURIComponent(eqp_ip)}&class_name=${encodeURIComponent(class_name)}&msr=${encodeURIComponent(msr)}`

  // `preview` asks the backend for a browser-renderable rendition. The call-site
  // rule travels with the type — see ImagePreviewOptions in utils/imageKind.ts.
  const imageUrl = (
    eqp_ip: string, class_name: string, msr: string, name: string,
    opts?: ImagePreviewOptions
  ) =>
    `${joinApiPath(base, '/msr-image')}?${q(eqp_ip, class_name, msr)}`
    + `&name=${encodeURIComponent(name)}${opts?.preview ? '&preview=1' : ''}`

  const fetchImageWithCond = async (
    eqp_ip: string, class_name: string, msr: string, name: string,
    opts?: ImagePreviewOptions
  ) => {
    const res = await fetch(imageUrl(eqp_ip, class_name, msr, name, opts))
    if (!res.ok) throw new Error(`image ${name}: ${res.status}`)
    const condRaw = res.headers.get('X-Msr-Cond')
    const blob = await res.blob()
    return { blobUrl: URL.createObjectURL(blob), cond: condRaw ? decodeURIComponent(condRaw) : null }
  }

  // `timeoutMs` is the caller's REMAINING budget, not a constant of this
  // module: the warmer holds images back for WARM_CEILING_MS, and a request
  // that never answers must not outlive that (utils/imageWarm.ts).
  //
  // `retry: 0` is load-bearing. ofetch retries GETs once by default on 408/409/
  // 425/429/5xx, so without it a rate-limited poll is re-sent underneath us —
  // doubling the wall time the budget just sized, and hiding the very failure
  // the caller's own policy is there to classify.
  const budgeted = (timeoutMs: number) => ({ retry: 0 as const, timeout: timeoutMs })

  const startDownloadAll = async (
    eqp_ip: string, class_name: string, msr: string, names: string[] | undefined, timeoutMs: number
  ) => {
    const res = await $fetch<{ job_id: string }>(joinApiPath(base, '/msr-images'), {
      method: 'POST',
      // `names` scopes the job to exactly these files (the parameter-scoped
      // cache warmer); omitted, the server lists and fetches the whole dir.
      body: names?.length ? { eqp_ip, class_name, msr, names } : { eqp_ip, class_name, msr },
      ...budgeted(timeoutMs)
    })
    return res.job_id
  }

  const pollJob = async (job_id: string, timeoutMs: number) =>
    await $fetch<DownloadJobStatus>(
      `${joinApiPath(base, '/msr-images')}/${encodeURIComponent(job_id)}`,
      budgeted(timeoutMs)
    )

  return { imageUrl, fetchImageWithCond, startDownloadAll, pollJob }
}
