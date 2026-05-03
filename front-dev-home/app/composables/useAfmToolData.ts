export interface AfmTool {
  id: string
  label: string
}

export interface AfmFabConfig {
  fab: string
  tools: AfmTool[]
}

export const useAfmToolData = () => {
  const fabs: AfmFabConfig[] = [
    { fab: 'R3', tools: [{ id: 'map608', label: 'MAP608' }] },
    { fab: 'M12', tools: [{ id: 'mapc01', label: 'MAPC01' }] }
  ]

  const afmToolHref = (tool: AfmTool) => `/afm/${tool.id}`

  return {
    fabs,
    afmToolHref
  }
}
