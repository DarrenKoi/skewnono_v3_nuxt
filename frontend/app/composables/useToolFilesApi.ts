import type { ToolType } from '~/utils/toolType'
import { toolSlug } from '~/utils/toolType'
import { joinApiPath } from '~/utils/apiPath'
import { downloadBlob } from '~/utils/tableExport'
import type { ToolFilesAccess, ToolFilesListing } from '~/utils/toolFiles'

export interface ToolFilesTarget {
  toolType: ToolType
  fab: string
  eqpId: string
}

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
    target.value ? `tool-files:${target.value.toolType}:${target.value.eqpId}:${path.value ?? ''}` : 'tool-files:none'
  )
  return useAsyncData(
    key,
    () => {
      const current = target.value
      if (!current) return Promise.resolve(null)
      return $fetch<ToolFilesListing>(apiUrl(current, 'list'), {
        query: { fab: current.fab, eqp_id: current.eqpId, path: path.value }
      })
    },
    { watch: [key] }
  )
}

// fetch, not an <a href>: a refused or failed download answers JSON, and a
// plain link would save that JSON under the file's name.
export const downloadToolFile = async (target: ToolFilesTarget, path: string, name: string) => {
  const query = new URLSearchParams({ fab: target.fab, eqp_id: target.eqpId, path })
  const response = await fetch(`${apiUrl(target, 'download')}?${query}`)
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw Object.assign(new Error(`download failed: ${response.status}`), { data, status: response.status })
  }
  downloadBlob(name, await response.blob())
}

// Writes answer only when the server's `access.can_write` is true; a page that
// shows no write controls otherwise never sends these.
export const uploadToolFile = (target: ToolFilesTarget, dir: string, file: File) => {
  const form = new FormData()
  form.append('fab', target.fab)
  form.append('eqp_id', target.eqpId)
  form.append('dir', dir)
  form.append('file', file)
  return $fetch<{ path: string }>(apiUrl(target, 'upload'), { method: 'POST', body: form })
}

export const deleteToolFile = (target: ToolFilesTarget, path: string) =>
  $fetch<{ deleted: string }>(apiUrl(target, 'delete'), {
    method: 'POST',
    body: { fab: target.fab, eqp_id: target.eqpId, path }
  })
