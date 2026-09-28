import type { IncidentApi } from './client'
import { mockApi } from './mockApi'

// Page components depend only on IncidentApi. Replace this adapter when the
// documented Python HTTP endpoints are implemented.
export const api: IncidentApi = mockApi
