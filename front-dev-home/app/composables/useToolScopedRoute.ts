import { isHeaderInfoPath } from '~/utils/headerNav'

// Whether the current route sits inside a tool's world: an /ebeam page, or one of the
// top-level pages the header menus lead to — those keep the remembered tool so the feature
// tabs can offer a way back. Everything else (the landing hub, /afm, /thickness,
// /tool-roster, /identify) is outside it, because no CD-SEM/HV-SEM tool has been chosen.
//
// Two consumers, and they must agree: NavFeatureTabs draws the per-feature tabs, NavLabMenu
// draws the 실험실 trigger. Both are services *of* a tool, so both have to vanish in the same
// places. The hub used to offer 실험실 beside the tool chooser — tools for a tool not yet
// picked — which is the case this composable exists to rule out. Deriving one boolean here
// rather than repeating the expression is the same discipline utils/headerNav applies to the
// link list: two copies of a rule drift, one does not.
export const useToolScopedRoute = () => {
  const route = useRoute()
  const isEbeamRoute = useEbeamRoute()
  return computed(() => isEbeamRoute.value || isHeaderInfoPath(route.path))
}
