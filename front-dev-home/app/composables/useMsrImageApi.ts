import { joinApiPath } from '~/utils/apiPath'

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

  const imageListUrl = (eqp_ip: string, class_name: string, msr: string) =>
    `${joinApiPath(base, '/msr-images')}?${q(eqp_ip, class_name, msr)}`

  const imageUrl = (eqp_ip: string, class_name: string, msr: string, name: string) =>
    `${joinApiPath(base, '/msr-image')}?${q(eqp_ip, class_name, msr)}&name=${encodeURIComponent(name)}`

  const fetchImageList = async (eqp_ip: string, class_name: string, msr: string) => {
    return await $fetch<{ images: string[], total: number }>(imageListUrl(eqp_ip, class_name, msr))
  }

  const fetchImageWithCond = async (eqp_ip: string, class_name: string, msr: string, name: string) => {
    const res = await fetch(imageUrl(eqp_ip, class_name, msr, name))
    if (!res.ok) throw new Error(`image ${name}: ${res.status}`)
    const condRaw = res.headers.get('X-Msr-Cond')
    const blob = await res.blob()
    return { blobUrl: URL.createObjectURL(blob), cond: condRaw ? decodeURIComponent(condRaw) : null }
  }

  const startDownloadAll = async (eqp_ip: string, class_name: string, msr: string) => {
    const res = await $fetch<{ job_id: string }>(joinApiPath(base, '/msr-images'), {
      method: 'POST',
      body: { eqp_ip, class_name, msr }
    })
    return res.job_id
  }

  const pollJob = async (job_id: string) =>
    await $fetch<DownloadJobStatus>(`${joinApiPath(base, '/msr-images')}/${encodeURIComponent(job_id)}`)

  return { imageListUrl, imageUrl, fetchImageList, fetchImageWithCond, startDownloadAll, pollJob }
}
