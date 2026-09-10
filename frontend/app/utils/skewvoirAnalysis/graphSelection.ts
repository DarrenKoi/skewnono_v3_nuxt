export type GraphSelectionId = `cd:${string}` | `fdc:${string}`

export const cdGraphId = (parameter: string): GraphSelectionId =>
  `cd:${parameter}`

export const fdcGraphId = (parameter: string): GraphSelectionId =>
  `fdc:${parameter}`

export const graphSelectionIds = (
  cdParameter: string,
  fdcParameters: readonly string[]
): GraphSelectionId[] => [
  cdGraphId(cdParameter),
  ...fdcParameters.map(fdcGraphId)
]

export const selectCdOnly = (cdParameter: string): GraphSelectionId[] => [
  cdGraphId(cdParameter)
]

export const toggleGraphSelection = (
  selected: readonly GraphSelectionId[],
  id: GraphSelectionId
): GraphSelectionId[] =>
  selected.includes(id)
    ? selected.filter(candidate => candidate !== id)
    : [...selected, id]

export const reconcileGraphSelection = (
  selected: readonly GraphSelectionId[],
  previousAvailable: readonly GraphSelectionId[],
  nextAvailable: readonly GraphSelectionId[]
): GraphSelectionId[] => {
  const previousWasFullySelected = previousAvailable.length > 0
    && previousAvailable.every(id => selected.includes(id))

  if (previousWasFullySelected) return [...nextAvailable]

  return nextAvailable.filter(id => selected.includes(id))
}

export const addGraphSelection = (
  selected: readonly GraphSelectionId[],
  id: GraphSelectionId
): GraphSelectionId[] =>
  selected.includes(id) ? [...selected] : [...selected, id]
