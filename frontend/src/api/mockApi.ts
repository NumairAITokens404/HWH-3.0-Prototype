import historyJson from '../../../data/remediation_history.json'
import casesJson from '../../../data/test_incidents.json'
import type { IncidentApi, IncidentFilters, MemoryFilters } from './client'
import type { EvaluationSummary, Incident, IncidentListItem, IncidentMemory, IncidentWorkspace, RiskLevel, UploadJob, UploadStage } from '../types/domain'

type EvaluationCase = { incident: Incident; expected_root_cause: string; expected_action: string; relevant_incident_ids: string[]; actions_to_avoid_before_remediation: string[] }
const memories = (historyJson as unknown as IncidentMemory[]).map((memory, index) => ({ ...memory, final_outcome: 'SUCCESS' as const, source_filename: index < 9 ? 'incident-postmortems-q2.json' : 'incident-postmortems-q3.json', chunk_refs: [`chunk-${index + 1}-summary`, `chunk-${index + 1}-failed-action`, `chunk-${index + 1}-recovery`] }))
const cases = casesJson as unknown as EvaluationCase[]
const riskByAction: Record<string, RiskLevel> = { reset_customer_pin: 'LOW', refresh_payment_routing: 'MEDIUM', rollback_connection_pool_change: 'HIGH', quarantine_poison_message: 'MEDIUM', reset_safe_cache: 'LOW', switch_downstream_endpoint: 'HIGH' }
const liveIncidents: IncidentListItem[] = cases.map((item, index) => ({ ...item.incident, status: index === 0 || index === 4 ? 'RESOLVED' : index === 1 || index === 2 ? 'APPROVAL_REQUIRED' : 'INVESTIGATING', occurred_at: new Date(Date.now() - index * 41 * 60_000).toISOString() }))
const wait = (ms = 120) => new Promise((resolve) => setTimeout(resolve, ms))
const approvalState = new Map<string, 'approved' | 'rejected'>()
let mockUploads: UploadJob[] = []
let mockMemoryRecords: IncidentMemory[] = []

function workspaceFor(id: string): IncidentWorkspace {
  const item = cases.find((entry) => entry.incident.incident_id === id) ?? cases[0]
  const incident = liveIncidents.find((entry) => entry.incident_id === item.incident.incident_id) ?? liveIncidents[0]
  const evidence = item.relevant_incident_ids.slice(0, 2).map((evidenceId, index) => {
    const memory = memories.find((record) => record.incident.incident_id === evidenceId)!
    return { incident_id: evidenceId, similarity: index === 0 ? 0.96 : 0.89, root_cause: memory.root_cause, outcomes: memory.outcomes }
  })
  const risk = riskByAction[item.expected_action] ?? 'HIGH'
  const approved = approvalState.get(incident.incident_id) === 'approved'
  const completed = approved || (risk === 'LOW' && incident.status === 'RESOLVED')
  return { incident, likely_root_cause: item.expected_root_cause, recommended_action: item.expected_action, confidence: 0.84, risk_level: risk, reasoning: `${item.expected_action.replaceAll('_', ' ')} is supported by verified recovery sequences in ${evidence.map((entry) => entry.incident_id).join(' and ')}. The failed retry remains visible as evidence.`, investigation_method: 'llm_grounded', model_name: 'qwen3.5:9b', evidence, failed_actions_avoided: item.actions_to_avoid_before_remediation, policy_status: risk === 'LOW' || approved ? 'ALLOWED' : 'HUMAN_APPROVAL_REQUIRED', workflow_status: completed ? 'RESOLVED' : risk === 'LOW' ? 'INVESTIGATING' : 'APPROVAL_REQUIRED', tool_acknowledgement: completed ? 'SUCCESS' : undefined, verification: completed ? { service_healthy: true, operation_recovered: true, result: 'SUCCESS' } : undefined, memory_stored: completed }
}

function filterIncidents(filters: IncidentFilters = {}) {
  const query = filters.query?.toLowerCase().trim()
  return liveIncidents.map((incident) => {
    const decision = approvalState.get(incident.incident_id)
    return decision ? { ...incident, status: decision === 'approved' ? 'RESOLVED' as const : 'INSUFFICIENT_EVIDENCE' as const } : incident
  }).filter((incident) => (!query || `${incident.incident_id} ${incident.service} ${incident.error_code ?? ''}`.toLowerCase().includes(query)) && (!filters.status || incident.status === filters.status) && (!filters.severity || incident.severity === filters.severity) && (!filters.service || incident.service === filters.service))
}
const stages: UploadStage[] = ['uploading', 'extracting', 'validating', 'chunking', 'embedding', 'storing', 'completed']

export const mockApi: IncidentApi = {
  async getOverview() { await wait(); return { active: 4, resolved: 2, pendingApprovals: 2, memoryRecords: mockMemoryRecords.length, failedFixesAvoided: mockMemoryRecords.filter((record) => record.outcomes.some((outcome) => outcome.result === 'FAILED')).length, learningCompleted: 0, learningTotal: cases.length, learningScore: 0, recent: liveIncidents.slice(0, 5) } },
  async getIncidents(filters) { await wait(); return filterIncidents(filters) },
  async getIncident(id) { await wait(); return workspaceFor(id) },
  async runWorkflow(id) { await wait(400); return workspaceFor(id) },
  async submitApproval(id, approved) { await wait(450); approvalState.set(id, approved ? 'approved' : 'rejected'); const result = workspaceFor(id); if (!approved) { result.workflow_status = 'INSUFFICIENT_EVIDENCE'; const item = cases.find((entry) => entry.incident.incident_id === id); if (item) { const rejected = memories.find((memory) => memory.incident.service === item.incident.service); if (rejected) mockMemoryRecords = [...mockMemoryRecords, { ...rejected, incident: item.incident, outcomes: [{ ...rejected.outcomes[0], outcome_id: `${id}-rejected`, incident_id: id, action: item.expected_action, result: 'FAILED', lesson_learned: 'Human review rejected the proposed remediation; do not execute without new evidence.' }], final_outcome: 'FAILED', final_resolution: 'HUMAN_REVIEW DENIED: remediation was not executed' }]; } } return result },
  async searchMemory(filters: MemoryFilters = {}) { await wait(); const query = filters.query?.toLowerCase().trim(); return mockMemoryRecords.filter((memory) => { const haystack = `${memory.incident.incident_id} ${memory.incident.service} ${memory.root_cause ?? ''} ${memory.outcomes.map((o) => o.action).join(' ')}`.toLowerCase(); return (!query || haystack.includes(query)) && (!filters.result || memory.outcomes.some((outcome) => outcome.result === filters.result)) && (!filters.service || memory.incident.service === filters.service) }) },
  async createUpload(files) { await wait(); const created = await Promise.all(files.map(async (file, index): Promise<UploadJob> => { const supported = /\.(json|csv|md|txt|log|pdf)$/i.test(file.name); const tooLarge = file.size > 5 * 1024 * 1024; if (supported && !tooLarge && /\.json$/i.test(file.name)) { try { const parsed = JSON.parse(await file.text()) as unknown; const records = Array.isArray(parsed) ? parsed : [parsed]; const ids = new Set(records.map((item) => (item as { incident?: { incident_id?: string } }).incident?.incident_id).filter(Boolean)); mockMemoryRecords = [...mockMemoryRecords, ...memories.filter((memory) => ids.has(memory.incident.incident_id))]; } catch { /* the API/mock validation reports malformed files below */ } } const stored = supported && !tooLarge ? mockMemoryRecords.length : 0; return { id: `upload-${Date.now()}-${index}`, fileName: file.name, size: file.size, stage: !supported || tooLarge ? 'failed' : 'completed', progress: !supported || tooLarge ? 0 : 100, chunks: !supported || tooLarge ? 0 : stored, failedRemediationChunks: !supported || tooLarge ? 0 : mockMemoryRecords.reduce((sum, record) => sum + record.outcomes.filter((outcome) => outcome.result === 'FAILED').length, 0), storedIncidents: stored, error: !supported ? 'Supported formats: JSON, CSV, Markdown, text, log, and PDF.' : tooLarge ? 'File exceeds the 5 MB limit.' : undefined } })); mockUploads = [...created.filter((job) => job.stage === 'completed'), ...mockUploads]; return created },
  async listUploads() { await wait(); return [...mockUploads] },
  async deleteUpload(id) { const job = mockUploads.find((item) => item.id === id); mockUploads = mockUploads.filter((item) => item.id !== id); if (job) mockMemoryRecords = []; await wait() },
  async advanceUpload(job: UploadJob) { await wait(420); if (job.stage === 'failed' || job.stage === 'completed') return job; const next = stages[Math.min(stages.indexOf(job.stage) + 1, stages.length - 1)]; const index = stages.indexOf(next); return { ...job, stage: next, progress: Math.round((index / (stages.length - 1)) * 100), chunks: index >= 3 ? 54 : 0, failedRemediationChunks: index >= 3 ? 18 : 0, storedIncidents: next === 'completed' ? 18 : 0 } },
  async getEvaluation(): Promise<EvaluationSummary> { await wait(); const total = cases.length; const point = { step: 0, label: 'Offline fixture', correct: 0, accepted: 0, total, score: 0, coverage: 0, retrievalPrecision: 0, failedFixAvoidance: 0, memoryRecords: mockMemoryRecords.length }; return { metrics: [{ name: 'Held-out action accuracy', withoutMemory: '0%', withMemory: '0%', improved: false, delta: 0 }], progress: [point], completed: 0, total, backend: 'mock', methodology: 'Offline frontend fixture. Connect the API for measured results.', cases: cases.map((item) => ({ incidentId: item.incident.incident_id, expectedAction: item.expected_action, recommendedAction: null, status: 'INSUFFICIENT_EVIDENCE', retrievedIds: [], relevantIds: [], method: 'offline_fixture' })) } } ,
  async resetDemo() { approvalState.clear(); mockUploads = []; mockMemoryRecords = []; await wait() },
}
