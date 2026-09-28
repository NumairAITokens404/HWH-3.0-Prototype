import type { IncidentApi } from './client'
import { createHttpApi } from './httpApi'
import { mockApi } from './mockApi'

const mode = import.meta.env.VITE_API_MODE ?? 'mock'
const baseUrl = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'
export const api: IncidentApi = mode === 'http' ? createHttpApi(baseUrl) : mockApi
