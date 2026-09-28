import type { IncidentApi } from './client'

export const futureEndpoints = {
  createUpload: 'POST /api/memory/uploads',
  getUpload: 'GET /api/memory/uploads/:jobId',
  searchMemory: 'GET /api/memory/search',
  investigate: 'POST /api/incidents/investigate',
  createWorkflow: 'POST /api/workflows',
  submitApproval: 'POST /api/workflows/:incidentId/approval',
  evaluation: 'GET /api/evaluation/summary',
} as const

export function createHttpApi(baseUrl: string): IncidentApi {
  throw new Error(`HTTP API mode at ${baseUrl} requires the documented backend endpoints.`)
}
