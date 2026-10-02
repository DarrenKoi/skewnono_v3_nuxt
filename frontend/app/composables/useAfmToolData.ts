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
    // Mirrors backend/afm/providers/mock.py TOOL_CONFIGS. MAPC01=R3 and 5EAP1501=M15
    // are office-confirmed (2026-10-02); MAP608's fab is still OFFICE-VERIFY.
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
