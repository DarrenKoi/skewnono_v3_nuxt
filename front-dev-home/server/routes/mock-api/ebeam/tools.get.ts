import { mockEbeamToolInventoryResponse } from '~/mock-data/ebeam-tool-inventory/ebeam-tool-inventory'

const cloneRows = <T>(rows: T[]) => rows.map(row => ({ ...row }))

export default defineEventHandler(() => ({
  'cd-sem': cloneRows(mockEbeamToolInventoryResponse['cd-sem']),
  'hv-sem': cloneRows(mockEbeamToolInventoryResponse['hv-sem']),
  'verity-sem': cloneRows(mockEbeamToolInventoryResponse['verity-sem']),
  'provision': cloneRows(mockEbeamToolInventoryResponse.provision)
}))
