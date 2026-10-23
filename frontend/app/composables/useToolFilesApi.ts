import type { ToolType } from '~/utils/toolType'
import { toolSlug } from '~/utils/toolType'
import { joinApiPath } from '~/utils/apiPath'
import { downloadBlob } from '~/utils/tableExport'
import type {
  ToolFilesAccess,
  ToolFilesGrantRow,
  ToolFilesListing,
  ToolFilesRequest,
  ToolFilesRequestRow
} from '~/utils/toolFiles'

export interface ToolFilesTarget {
  toolType: ToolType
  fab: string
  eqpId: string
  // Provision only: its data host (data_ip) instead of the tool (eqp_ip).
  host?: 'data'
}

// Sent with every call so list, download and write all reach the same host.
const targetFields = (target: ToolFilesTarget) => ({
  fab: target.fab,
  eqp_id: target.eqpId,
  ...(target.host ? { host: target.host } : {})
})

const apiUrl = (target: ToolFilesTarget, leaf: string) =>
  joinApiPath(useRuntimeConfig().public.apiBase, `/${toolSlug(target.toolType)}/tool-files/${leaf}`)

// Per person, not per tool: one answer shared by every tool family's page.
export const useToolFilesAccess = () => {
  const url = joinApiPath(useRuntimeConfig().public.apiBase, '/tool-files/access')
  return useAsyncData('tool-files-access', () => $fetch<ToolFilesAccess>(url))
}

// Keyed on tool + path, not cached across visits: a listing is a live view of
// a tool's disk, and access is re-checked on every request.
export const useToolFilesListing = (target: Ref<ToolFilesTarget | null>, path: Ref<string | undefined>) => {
  const key = computed(() =>
    target.value ? `tool-files:${target.value.toolType}:${target.value.eqpId}:${target.value.host ?? 'tool'}:${path.value ?? ''}` : 'tool-files:none'
  )
  return useAsyncData(
    key,
    () => {
      const current = target.value
      if (!current) return Promise.resolve(null)
      return $fetch<ToolFilesListing>(apiUrl(current, 'list'), {
        query: { ...targetFields(current), path: path.value }
      })
    },
    { watch: [key] }
  )
}

// fetch, not an <a href>: a refused or failed download answers JSON, and a
// plain link would save that JSON under the file's name.
const saveResponse = async (request: Promise<Response>, name: string) => {
  const response = await request
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw Object.assign(new Error(`download failed: ${response.status}`), { data, status: response.status })
  }
  downloadBlob(name, await response.blob())
}

export const downloadToolFile = (target: ToolFilesTarget, path: string, name: string) => {
  const query = new URLSearchParams({ ...targetFields(target), path })
  return saveResponse(fetch(`${apiUrl(target, 'download')}?${query}`), name)
}

// One request and one FTP session for all of them; the server spends the
// download cap on the files together.
export const downloadToolFilesZip = (target: ToolFilesTarget, paths: string[], name: string) =>
  saveResponse(fetch(apiUrl(target, 'download-zip'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ...targetFields(target), paths })
  }), name)

// Writes answer only when the server's `access.can_write` is true; a page that
// shows no write controls otherwise never sends these.
export const uploadToolFile = (target: ToolFilesTarget, dir: string, file: File) => {
  const form = new FormData()
  for (const [key, value] of Object.entries(targetFields(target))) form.append(key, value)
  form.append('dir', dir)
  form.append('file', file)
  return $fetch<{ path: string }>(apiUrl(target, 'upload'), { method: 'POST', body: form })
}

export const deleteToolFile = (target: ToolFilesTarget, path: string) =>
  $fetch<{ deleted: string }>(apiUrl(target, 'delete'), {
    method: 'POST',
    body: { ...targetFields(target), path }
  })

// Only `reason` is sent: the server takes the empno from the identity and
// the team from the directory.
export const requestToolFilesAccess = (reason: string) =>
  $fetch<{ verdict: 'granted' | 'pending', request?: ToolFilesRequest }>(
    joinApiPath(useRuntimeConfig().public.apiBase, '/tool-files/requests'),
    { method: 'POST', body: { reason } }
  )

// One key for the panel's overview, so /admin/access can refresh it too.
export const TOOL_FILES_ADMIN_KEY = 'admin-tool-files-grants'

export const useToolFilesAdminApi = () => {
  const base = useRuntimeConfig().public.apiBase
  const url = (leaf: string) => joinApiPath(base, `/admin/tool-files${leaf}`)
  return {
    fetchOverview: () => $fetch<{ grants: ToolFilesGrantRow[], requests: ToolFilesRequestRow[] }>(url('')),
    grant: (empno: string) =>
      $fetch<ToolFilesGrantRow>(url('/grants'), { method: 'POST', body: { empno } }),
    revoke: (empno: string) =>
      $fetch<{ revoked: boolean }>(url('/grants/revoke'), { method: 'POST', body: { empno } }),
    // request_id is the one on screen: a re-request since then answers 409.
    approve: (empno: string, requestId: string) =>
      $fetch<{ approved: string }>(url('/requests/approve'), {
        method: 'POST',
        body: { empno, request_id: requestId }
      }),
    reject: (empno: string, requestId: string) =>
      $fetch<{ rejected: string }>(url('/requests/reject'), {
        method: 'POST',
        body: { empno, request_id: requestId }
      })
  }
}
