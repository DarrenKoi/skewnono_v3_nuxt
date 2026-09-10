// Whether the skewvoir dashboard's parameter chip row (ParamNav) is expanded.
//
// Collapsed by default: 파라미터 요약 already lists every parameter and selects
// them on row click, so the chips are a second way to do the same thing — and a
// recipe with hundreds of parameters turns them into a wall that pushes the
// inspection panels off screen.
//
// Persisted rather than component-local because Workspace swaps views with
// `v-if`: the dashboard unmounts whenever you visit 상관/FDC, so a local ref
// would forget the choice on every round trip. usePersistedState carries it
// across client-side navigation AND full reloads.

export const useSkewvoirParamNavOpen = () =>
  usePersistedState<boolean>(
    'skewvoir:param-nav-open',
    'skewnono:skewvoir.paramNavOpen',
    {
      default: () => false,
      normalize: parsed => parsed === true,
      // Collapsed is the default, so storage only ever holds the deviation
      // from it — hiding the row again drops the key instead of writing false.
      isEmpty: value => !value
    }
  )
