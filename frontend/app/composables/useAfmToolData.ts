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
    // Mirrors backend/afm/providers/mock.py TOOL_CONFIGS. MAP608=PKG, MAPC01=R3 and
    // 5EAP1501=M15 are user-confirmed (2026-10-07); nothing the office loads names a fab.
    {
      fab: 'PKG',
      tools: [
        { id: 'map608', label: 'MAP608' }
      ]
    },
    {
      fab: 'R3',
      tools: [
        { id: 'mapc01', label: 'MAPC01' }
      ]
    },
    {
      fab: 'M15',
      tools: [
        { id: '5eap1501', label: '5EAP1501' }
      ]
    }
  ]

  const afmToolHref = (tool: AfmTool) => `/afm/${tool.id}`

  return {
    fabs,
    afmToolHref
  }
}
