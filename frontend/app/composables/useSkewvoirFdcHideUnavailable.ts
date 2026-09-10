// Whether the FDC 파라미터 매트릭스 hides params whose CD relation is 평가 불가
// (constant axis, too few pairs, no pairs).
//
// Off by default: showing everything is the honest baseline, and the reasons in
// the tooltip are how a user learns WHY a param is unevaluable. The toggle
// exists because on real data many channels sit constant, and each one drags a
// sparkline row plus a "한 축의 분산이 없습니다" line into the linked-axis
// tooltip — noise once the user has understood it.
//
// Persisted rather than component-local because Workspace swaps views with
// `v-if`: the FDC view unmounts whenever you visit 대시보드/상관, so a local
// ref would forget the choice on every round trip.
export const useSkewvoirFdcHideUnavailable = () =>
  usePersistedState<boolean>(
    'skewvoir:fdc-hide-unavailable',
    'skewnono:skewvoir.fdcHideUnavailable',
    {
      default: () => false,
      normalize: parsed => parsed === true,
      // Showing everything is the default, so storage only holds the deviation
      // from it — switching back to show drops the key instead of writing false.
      isEmpty: value => !value
    }
  )
