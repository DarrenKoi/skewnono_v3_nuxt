// Presentation order for a measurement's parameters: by the mp_number carried
// on the file's rows (primary key), then by sequence — the order the points
// were actually measured in. The backend's `parameters` array order is
// arbitrary, so the navigator chips and the 파라미터 요약 table both sort
// through this helper to agree with the row data.
//
// A row with mp_number < 0 is a metadata-only point (no measurement); its
// mp_number is a sentinel, not a real MP, so a parameter's rank prefers its
// non-negative mp_numbers and falls back to the sentinel rows only when the
// parameter has nothing else. Parameters with no rows at all sort last, in
// their incoming order.
//
// Pure and framework-free so it runs under raw `node --test`.

interface ParamOrderRow {
  parameter: string
  mp_number: number
  sequence: number
}

// A measurement often OPENS with an unnamed dummy point — a settling shot that
// stabilises the tool before the real MPs start. It carries no parameter name
// (''), but it DOES carry rows and SEM images, so it stays in the parameter list
// and stays selectable; routeQuery's UNNAMED_PARAM_TOKEN is what makes it
// addressable in the URL despite the blank name.
//
// What it must never be is the DEFAULT: it is measured first, so it sorts to the
// head of the mp order and would otherwise be the parameter you land on. These
// helpers separate "named" from "present" so a default pick can prefer the first
// REAL parameter — the next coming one — while an explicit pick of the dummy is
// still honoured.
export const isNamedParam = (parameter: string): boolean => parameter.trim().length > 0

export const namedParams = <T extends { parameter: string }>(items: T[]): T[] =>
  items.filter(item => isNamedParam(item.parameter))

// What to show wherever a parameter NAME is rendered. A blank chip is an
// unreadable click target, so the unnamed MP gets a stand-in rather than
// rendering as nothing.
//
// A PLACEHOLDER, not a word. Descriptive labels ("DUMMY", "이름 없음") are the
// wrong shape here: "DUMMY" is itself a real parameter name that turns up in
// office data, so a label that reads like a name invites confusion with an
// actual parameter that happens to be called that. "-" cannot be mistaken for
// one, and it matches how the rest of the UI already renders an absent value.
export const UNNAMED_PARAM_LABEL = '-'

export const paramLabel = (parameter: string): string =>
  isNamedParam(parameter) ? parameter : UNNAMED_PARAM_LABEL

type ParamRank = [mp: number, seq: number]

const better = (a: ParamRank, b: ParamRank): boolean =>
  a[0] < b[0] || (a[0] === b[0] && a[1] < b[1])

// items: anything carrying a `parameter` name (e.g. MsrParamSummary).
export const sortByRowMpOrder = <T extends { parameter: string }>(
  items: T[],
  rows: ParamOrderRow[]
): T[] => {
  // Best (lowest) [mp, seq] per parameter; measured mp_numbers beat sentinels.
  const measured = new Map<string, ParamRank>()
  const sentinel = new Map<string, ParamRank>()
  for (const r of rows) {
    const target = r.mp_number >= 0 ? measured : sentinel
    const rank: ParamRank = [r.mp_number, r.sequence]
    const cur = target.get(r.parameter)
    if (!cur || better(rank, cur)) target.set(r.parameter, rank)
  }

  // Tier 0: has a real (measured) mp_number. Tier 1: sentinel rows only — a
  // sentinel is not a real MP, so these follow every measured parameter.
  // Tier 2: no rows at all. Rank compares only within a tier.
  const rankOf = (p: string): { tier: number, rank: ParamRank | null } => {
    const m = measured.get(p)
    if (m) return { tier: 0, rank: m }
    const s = sentinel.get(p)
    if (s) return { tier: 1, rank: s }
    return { tier: 2, rank: null }
  }

  // Stable: decorate with the incoming index so equal entries keep their order.
  return items
    .map((item, i) => ({ item, i, ...rankOf(item.parameter) }))
    .sort((a, b) => {
      if (a.tier !== b.tier) return a.tier - b.tier
      if (a.rank && b.rank) {
        if (a.rank[0] !== b.rank[0]) return a.rank[0] - b.rank[0]
        if (a.rank[1] !== b.rank[1]) return a.rank[1] - b.rank[1]
      }
      return a.i - b.i
    })
    .map(entry => entry.item)
}
