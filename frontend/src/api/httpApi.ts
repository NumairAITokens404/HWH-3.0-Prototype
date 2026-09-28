import type { IncidentApi, IncidentFilters, MemoryFilters } from './client'
import type { EvaluationSummary, IncidentListItem, IncidentMemory, IncidentWorkspace, Result, UploadJob } from '../types/domain'

type Evidence = { incident_id: string; similarity: number; root_cause?: string | null; outcomes: IncidentMemory['outcomes'] }
type Investigation = { incident_id: string; status: string; likely_root_cause?: string | null; recommended_action?: { action_name: string; risk_level: 'LOW' | 'MEDIUM' | 'HIGH'; reason: string; confidence: number } | null; reasoning: string; historical_evidence: Evidence[]; method: IncidentWorkspace['investigation_method']; model_name?: string | null; fallback_reason?: string | null }
type Workflow = { incident_id: string; status: string; investigation: Investigation; decision?: { status: IncidentWorkspace['policy_status']; risk_level: 'LOW' | 'MEDIUM' | 'HIGH'; request_id: string } | null; remediation?: { result: Result } | null; verification?: { service_healthy: boolean; operation_recovered: boolean; result: Result } | null; memory_stored: boolean }
type Detail = { incident: Omit<IncidentListItem, 'status' | 'occurred_at'>; investigation: Investigation; workflow?: Workflow | null }

export function createHttpApi(baseUrl: string): IncidentApi {
  const root = baseUrl.replace(/\/$/, '')
  const workflows = new Map<string, Workflow>()
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(root + path, init)
    const payload = await response.json().catch(() => null)
    if (!response.ok) throw new Error(payload && typeof payload === 'object' && 'detail' in payload ? String(payload.detail) : `API request failed (${response.status})`)
    return payload as T
  }
  const uiStatus = (value?: string): IncidentWorkspace['workflow_status'] => ({ SUCCESS: 'RESOLVED', HUMAN_APPROVAL_REQUIRED: 'APPROVAL_REQUIRED', DENIED: 'INSUFFICIENT_EVIDENCE', BLOCKED: 'APPROVAL_REQUIRED', FAILED: 'PARTIAL' } as Record<string, IncidentWorkspace['workflow_status']>)[value ?? ''] ?? (value as IncidentWorkspace['workflow_status'] | undefined) ?? 'INVESTIGATING'
  function toWorkspace(item: Detail, workflow?: Workflow | null): IncidentWorkspace {
    if (workflow) workflows.set(workflow.incident_id, workflow)
    const investigation = workflow?.investigation ?? item.investigation
    const action = investigation.recommended_action
    return { incident: { ...item.incident, status: uiStatus(workflow?.status), occurred_at: '2026-09-28T00:00:00+00:00' }, likely_root_cause: investigation.likely_root_cause ?? 'Insufficient historical evidence', recommended_action: action?.action_name ?? 'No action recommended', confidence: action?.confidence ?? 0, risk_level: workflow?.decision?.risk_level ?? action?.risk_level ?? 'HIGH', reasoning: investigation.reasoning, investigation_method: investigation.method, model_name: investigation.model_name ?? undefined, fallback_reason: investigation.fallback_reason ?? undefined, evidence: investigation.historical_evidence, failed_actions_avoided: investigation.historical_evidence.flatMap((e) => e.outcomes.filter((o) => o.result === 'FAILED').map((o) => o.action)).filter((v, i, all) => all.indexOf(v) === i), policy_status: workflow?.decision?.status ?? (action?.risk_level === 'LOW' ? 'ALLOWED' : 'HUMAN_APPROVAL_REQUIRED'), workflow_status: uiStatus(workflow?.status), tool_acknowledgement: workflow?.remediation?.result, verification: workflow?.verification ?? undefined, memory_stored: workflow?.memory_stored ?? false }
  }
  const getDetail = (id: string) => request<Detail>(`/api/ui/incidents/${encodeURIComponent(id)}`)
  return {
    getOverview: () => request('/api/ui/overview'),
    async getIncidents(filters: IncidentFilters = {}) { const rows = await request<IncidentListItem[]>('/api/ui/incidents'); const q = filters.query?.trim().toLowerCase(); return rows.filter((row) => (!q || `${row.incident_id} ${row.service} ${row.error_code ?? ''}`.toLowerCase().includes(q)) && (!filters.status || row.status === filters.status) && (!filters.severity || row.severity === filters.severity) && (!filters.service || row.service === filters.service)) },
    async getIncident(id) { const item = await getDetail(id); return toWorkspace(item, item.workflow) },
    async runWorkflow(id) { const result = await request<Workflow>(`/api/ui/incidents/${encodeURIComponent(id)}/workflow`, { method: 'POST' }); return toWorkspace(await getDetail(id), result) },
    async submitApproval(id, approved, reviewer) { let workflow = workflows.get(id); if (!workflow) workflow = (await getDetail(id)).workflow ?? undefined; if (!workflow?.decision?.request_id) workflow = await request<Workflow>(`/api/ui/incidents/${encodeURIComponent(id)}/workflow`, { method: 'POST' }); if (!workflow.decision?.request_id) throw new Error('The workflow did not create an approval request.'); const token = import.meta.env.VITE_APPROVAL_TOKEN as string | undefined; const result = await request<Workflow>(`/api/ui/incidents/${encodeURIComponent(id)}/approval`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ request_id: workflow.decision.request_id, approved, reviewer }) }); return toWorkspace(await getDetail(id), result) },
    async searchMemory(filters: MemoryFilters = {}) { const params = new URLSearchParams(); if (filters.query) params.set('q', filters.query); if (filters.result) params.set('result', filters.result); if (filters.service) params.set('service', filters.service); const rows = await request<IncidentMemory[]>(`/api/ui/memory?${params}`); return rows.map((row) => ({ ...row, source_filename: row.source_filename ?? 'memory store', chunk_refs: row.chunk_refs ?? row.outcomes.filter((o) => o.result !== 'SUCCESS').map((o) => o.outcome_id) })) },
    async createUpload(files) { return Promise.all(files.map(async (file, index): Promise<UploadJob> => { const form = new FormData(); form.append('file', file); try { const result = await request<{ incident_count: number; failed_remediation_chunk_count: number }>('/api/memory/uploads', { method: 'POST', body: form }); return { id: `upload-${Date.now()}-${index}`, fileName: file.name, size: file.size, stage: 'completed', progress: 100, chunks: result.incident_count + result.failed_remediation_chunk_count, failedRemediationChunks: result.failed_remediation_chunk_count, storedIncidents: result.incident_count } } catch (error) { return { id: `upload-${Date.now()}-${index}`, fileName: file.name, size: file.size, stage: 'failed', progress: 0, chunks: 0, failedRemediationChunks: 0, storedIncidents: 0, error: error instanceof Error ? error.message : 'Upload failed' } } })) },
    async advanceUpload(job) { return job },
    getEvaluation: (): Promise<EvaluationSummary> => request('/api/ui/evaluation'),
  }
}
