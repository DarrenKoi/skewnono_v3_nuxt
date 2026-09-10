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

  // The route URL-quotes the sidecar into one header line (newlines included).
  const condOf = (res: Response) => {
    const raw = res.headers.get('X-Msr-Cond')
    return raw ? decodeURIComponent(raw) : null
  }

  const fetchImageWithCond = async (
    eqp_ip: string, class_name: string, msr: string, name: string,
    opts?: ImagePreviewOptions
  ) => {
    const res = await fetch(imageUrl(eqp_ip, class_name, msr, name, opts))
    if (!res.ok) throw new Error(`image ${name}: ${res.status}`)
    const blob = await res.blob()
    return { blobUrl: URL.createObjectURL(blob), cond: condOf(res) }
  }

  // The cond.txt sidecar alone. Usually the URL the <img> loaded, so the
  // browser's HTTP cache (max-age=3600) answers; after an auto-retry the <img>
  // cached a `?retry=N` variant instead (utils/imageRetry.ts), and this GET
  // reaches Flask — still a server cache hit, since the sidecar was stored
  // beside the image. The tool is never revisited either way, and the body is
  // cancelled once the header is in.
  const fetchCond = async (url: string) => {
    const res = await fetch(url)
    if (!res.ok) throw new Error(`cond: ${res.status}`)
    void res.body?.cancel()
    return condOf(res)
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

  return { imageUrl, fetchImageWithCond, fetchCond, startDownloadAll, pollJob }
}
