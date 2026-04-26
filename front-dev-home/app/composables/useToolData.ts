import type { ToolType } from '~/stores/navigation'

export interface ToolTypeConfig {
  id: ToolType
  label: string
  count: number
  enabled: boolean
}

export const useToolData = () => {
  const toolTypes: ToolTypeConfig[] = [
    { id: 'cd-sem', label: 'CD-SEM', count: 0, enabled: true },
    { id: 'hv-sem', label: 'HV-SEM', count: 0, enabled: true },
    { id: 'verity-sem', label: 'VeritySEM', count: 0, enabled: false },
    { id: 'provision', label: 'Provision', count: 0, enabled: false }
  ]

  return {
    toolTypes
  }
}
