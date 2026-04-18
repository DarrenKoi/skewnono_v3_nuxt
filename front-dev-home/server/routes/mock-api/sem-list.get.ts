import { mockSemListResponse } from '~/mock-data/sem-list/sem-list'

export default defineEventHandler(() => mockSemListResponse.map(row => ({ ...row })))
