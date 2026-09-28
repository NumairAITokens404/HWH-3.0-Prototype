import type { EvaluationSummary, IncidentListItem, IncidentMemory, IncidentWorkspace, UploadJob } from '../types/domain'
export interface IncidentFilters { query?: string; status?: string; severity?: string; service?: string }
export interface MemoryFilters { query?: string; result?: string; service?: string }
export interface IncidentApi {
  getOverview(): Promise<{ active: number; resolved: number; pendingApprovals: number; memoryRecords: number; failedFixesAvoided: number; learningCompleted: number; learningTotal: number; learningScore: number; recent: IncidentListItem[] }>
  getIncidents(filters?: IncidentFilters): Promise<IncidentListItem[]>
  getIncident(id: string): Promise<IncidentWorkspace>
  runWorkflow(id: string): Promise<IncidentWorkspace>
  submitApproval(id: string, approved: boolean, reviewer: string): Promise<IncidentWorkspace>
  searchMemory(filters?: MemoryFilters): Promise<IncidentMemory[]>
  createUpload(files: File[]): Promise<UploadJob[]>
  listUploads(): Promise<UploadJob[]>
  deleteUpload(id: string): Promise<void>
  advanceUpload(job: UploadJob): Promise<UploadJob>
  getEvaluation(): Promise<EvaluationSummary>
  refreshEvaluation(): Promise<void>
  resetDemo(): Promise<void>
}
