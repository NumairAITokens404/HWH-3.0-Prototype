import type { IncidentApi, IncidentFilters, MemoryFilters } from './client'
import type { EvaluationSummary, IncidentListItem, IncidentMemory, IncidentWorkspace, Result, UploadJob } from '../types/domain'

type Evidence = { incident_id: string; similarity: number; root_cause?: string | null; outcomes: IncidentMemory['outcomes'] }
type Investigation = { incident_id: string; status: string; likely_root_cause?: string | null; recommended_action?: { action_name: string; risk_level: 'LOW' | 'MEDIUM' | 'HIGH'; reason: string; confidence: number } | null; reasoning: string; historical_evidence: Evidence[]; method: IncidentWorkspace['investigation_method']; model_name?: string | null; fallback_reason?: string | null }
type Workflow = { incident_id: string; status: string; investigation: Investigation; decision?: { status: IncidentWorkspace['policy_status']; risk_level: 'LOW' | 'MEDIUM' | 'HIGH'; request_id: string } | null; remediation?: { result: Result } | null; reprocessing?: { result: Result } | null; verification?: { service_healthy: boolean; operation_recovered: boolean; result: Result } | null; memory_stored: boolean; learned_from?: string[]; observation_id?: string | null }
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
  const uiStatus = (value?: string): IncidentWorkspace['workflow_status'] => ({ SUCCESS: 'RESOLVED', HUMAN_APPROVAL_REQUIRED: 'APPROVAL_REQUIRED', FAILED: 'PARTIAL' } as Record<string, IncidentWorkspace['workflow_status']>)[value ?? ''] ?? (value as IncidentWorkspace['workflow_status'] | undefined) ?? 'INVESTIGATING'
  function toWorkspace(item: Detail, workflow?: Workflow | null): IncidentWorkspace {
    if (workflow) workflows.set(workflow.incident_id, workflow)
    else workflows.delete(item.incident.incident_id)
    const investigation = workflow?.investigation ?? item.investigation
    const action = investigation.recommended_action
    const status = uiStatus(workflow?.status ?? (!action ? 'INSUFFICIENT_EVIDENCE' : undefined))
    const needsReview = ['HIGH', 'CRITICAL'].includes(item.incident.severity) || action?.risk_level !== 'LOW'
    return {
      incident: { ...item.incident, status, occurred_at: '2026-09-28T00:00:00+00:00' },
      likely_root_cause: investigation.likely_root_cause ?? 'Insufficient historical evidence',
      recommended_action: action?.action_name ?? 'No action recommended', confidence: action?.confidence ?? 0,
      risk_level: workflow?.decision?.risk_level ?? action?.risk_level ?? 'HIGH', reasoning: investigation.reasoning,
      investigation_method: investigation.method, model_name: investigation.model_name ?? undefined,
      fallback_reason: investigation.fallback_reason ?? undefined, evidence: investigation.historical_evidence,
      failed_actions_avoided: investigation.historical_evidence.flatMap((e) => e.outcomes.filter((o) => o.result === 'FAILED').map((o) => o.action)).filter((v, i, all) => all.indexOf(v) === i),
      policy_status: workflow?.decision?.status ?? (!action ? 'BLOCKED' : needsReview ? 'HUMAN_APPROVAL_REQUIRED' : 'ALLOWED'),
      workflow_status: status, tool_acknowledgement: workflow?.remediation?.result,
      reprocessing_result: workflow?.reprocessing?.result, verification: workflow?.verification ?? undefined,
      memory_stored: workflow?.memory_stored ?? false, learned_from: workflow?.learned_from ?? [],
      observation_id: workflow?.observation_id,
    }
  }
  const getDetail = (id: string) => request<Detail>(`/api/ui/incidents/${encodeURIComponent(id)}`)
  return {
    getOverview: () => request('/api/ui/overview'),
    async getIncidents(filters: IncidentFilters = {}) { const rows = await request<IncidentListItem[]>('/api/ui/incidents'); const q = filters.query?.trim().toLowerCase(); return rows.filter((row) => (!q || `${row.incident_id} ${row.service} ${row.error_code ?? ''}`.toLowerCase().includes(q)) && (!filters.status || row.status === filters.status) && (!filters.severity || row.severity === filters.severity) && (!filters.service || row.service === filters.service)) },
    async getIncident(id) { const item = await getDetail(id); return toWorkspace(item, item.workflow) },
    async runWorkflow(id) { const result = await request<Workflow>(`/api/ui/incidents/${encodeURIComponent(id)}/workflow`, { method: 'POST' }); return toWorkspace(await getDetail(id), result) },
    async submitApproval(id, approved, reviewer) { let workflow = workflows.get(id); if (!workflow) workflow = (await getDetail(id)).workflow ?? undefined; if (!workflow?.decision?.request_id) workflow = await request<Workflow>(`/api/ui/incidents/${encodeURIComponent(id)}/workflow`, { method: 'POST' }); if (!workflow.decision?.request_id) throw new Error('The workflow did not create an approval request.'); const token = import.meta.env.VITE_APPROVAL_TOKEN as string | undefined; const result = await request<Workflow>(`/api/ui/incidents/${encodeURIComponent(id)}/approval`, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify({ request_id: workflow.decision.request_id, approved, reviewer }) }); return toWorkspace(await getDetail(id), result) },
    async searchMemory(filters: MemoryFilters = {}) { const params = new URLSearchParams(); if (filters.query) params.set('q', filters.query); if (filters.result) params.set('result', filters.result); if (filters.service) params.set('service', filters.service); const rows = await request<IncidentMemory[]>(`/api/ui/memory?${params}`); return rows.map((row) => ({ ...row, source_filename: row.source_filename ?? 'memory store', chunk_refs: row.chunk_refs ?? row.outcomes.filter((o) => o.result !== 'SUCCESS').map((o) => o.outcome_id) })) },
    async createUpload(files) { return Promise.all(files.map(async (file, index): Promise<UploadJob> => { const form = new FormData(); form.append('file', file); try { return await request<UploadJob>('/api/ui/uploads', { method: 'POST', body: form }) } catch (error) { return { id: `failed-${Date.now()}-${index}`, fileName: file.name, size: file.size, stage: 'failed', progress: 0, chunks: 0, failedRemediationChunks: 0, storedIncidents: 0, error: error instanceof Error ? error.message : 'Upload failed' } } })) },
    listUploads: (): Promise<UploadJob[]> => request('/api/ui/uploads'),
    async deleteUpload(id) { await request(`/api/ui/uploads/${encodeURIComponent(id)}`, { method: 'DELETE' }) },
    async advanceUpload(job) { return job },
    getEvaluation: (): Promise<EvaluationSummary> => request('/api/ui/evaluation'),
    async refreshEvaluation() { await request('/api/ui/evaluation/refresh', { method: 'POST' }) },
    async resetDemo() { await request('/api/ui/reset', { method: 'POST' }) },
  }
}
