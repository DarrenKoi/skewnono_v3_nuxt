export interface AfmTool {
  id: string
  label: string
  concept: string
}

export interface AfmFabConfig {
  fab: string
  tools: AfmTool[]
}

export const useAfmToolData = () => {
  const fabs: AfmFabConfig[] = [
    {
      fab: 'R3',
      tools: [
        { id: 'map608', label: 'MAP608', concept: 'Concept A' }
      ]
    },
    {
      fab: 'M12',
      tools: [
        { id: 'mapc01', label: 'MAPC01', concept: 'Concept A' }
      ]
    },
    {
      fab: 'M15',
      tools: [
        { id: '5mapt01', label: '5MAPT01', concept: 'Concept A' }
      ]
    }
  ]

  const afmToolHref = (tool: AfmTool) => `/afm/${tool.id}`

  return {
    fabs,
    afmToolHref
  }
}
