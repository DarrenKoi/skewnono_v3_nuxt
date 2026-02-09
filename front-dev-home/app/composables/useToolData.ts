import type { ToolType, Fab } from '~/stores/navigation'

export interface ToolTypeConfig {
  id: ToolType
  label: string
  count: number
}

export interface FabConfig {
  id: Fab
  label: string
  hasAlerts?: boolean
}

export const useToolData = () => {
  const toolTypes: ToolTypeConfig[] = [
    { id: 'cd-sem', label: 'CD-SEM', count: 250 },
    { id: 'hv-sem', label: 'HV-SEM', count: 48 },
    { id: 'verity-sem', label: 'VeritySEM', count: 24 },
    { id: 'provision', label: 'Provision', count: 12 }
  ]

  const fabs: FabConfig[] = [
    { id: 'all', label: 'All' },
    { id: 'R3', label: 'R3' },
    { id: 'M11', label: 'M11' },
    { id: 'M12', label: 'M12' },
    { id: 'M14', label: 'M14', hasAlerts: true },
    { id: 'M15', label: 'M15' },
    { id: 'M16', label: 'M16' }
  ]

  const getToolTypeByRoute = (route: string): ToolType | null => {
    const match = route.match(/\/ebeam\/(cd-sem|hv-sem|verity-sem|provision)/)
    return match ? match[1] as ToolType : null
  }

  const getFabByRoute = (route: string): Fab | null => {
    const match = route.match(/\/ebeam\/[^/]+\/([^/]+)/)
    if (match && match[1]) {
      const fabId = match[1].toUpperCase()
      const fab = fabs.find(f => f.id === fabId || f.id.toLowerCase() === match[1])
      return fab?.id ?? null
    }
    return null
  }

  return {
    toolTypes,
    fabs,
    getToolTypeByRoute,
    getFabByRoute
  }
}
