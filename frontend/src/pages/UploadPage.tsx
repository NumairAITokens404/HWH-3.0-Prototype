import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowDown, BrainCircuit, CheckCircle2, Database, FileCheck2, FileJson, Layers3, RefreshCw, Trash2, UploadCloud, XCircle } from 'lucide-react'
import { useRef, useState } from 'react'
import { api } from '../api'
import { EmptyState, PageHeader, StatusBadge, WorkflowNotice } from '../components/ui'
import type { UploadJob, UploadStage } from '../types/domain'
import demoHistory from '../../../data/remediation_history.json'

const stages: Array<{ key: UploadStage; label: string; icon: React.ElementType; detail: string }> = [
  { key: 'uploading', label: 'Upload', icon: UploadCloud, detail: 'Receive source files' },
  { key: 'extracting', label: 'Extract', icon: FileJson, detail: 'Read incident content' },
  { key: 'validating', label: 'Validate', icon: FileCheck2, detail: 'Check strict schema' },
  { key: 'chunking', label: 'Chunk', icon: Layers3, detail: 'Preserve evidence context' },
  { key: 'embedding', label: 'Embed', icon: BrainCircuit, detail: 'Create searchable meaning' },
  { key: 'storing', label: 'Store', icon: Database, detail: 'Write to Hindsight' },
]

type DatasetChoice = 'starter' | 'expanded' | 'full' | 'logs'
const groups = [0, 3, 6, 9, 12, 15]
const demoRecords = demoHistory as unknown[]
const datasets: Record<DatasetChoice, { label: string; records: unknown[]; format: 'json' | 'log' }> = {
  starter: { label: 'Starter · 6 incident families', records: groups.map((index) => demoRecords[index]), format: 'json' },
  expanded: { label: 'Expanded · 12 varied incidents', records: groups.flatMap((index) => demoRecords.slice(index, index + 2)), format: 'json' },
  full: { label: 'Full · 18 incidents / 54 outcomes', records: demoRecords, format: 'json' },
  logs: { label: 'Operational log · 6 embedded records', records: groups.map((index) => demoRecords[index]), format: 'log' },
}

export function UploadPage() {
  const queryClient = useQueryClient()
  const [failures, setFailures] = useState<UploadJob[]>([])
  const [dragging, setDragging] = useState(false)
  const [dataset, setDataset] = useState<DatasetChoice>('starter')
  const inputRef = useRef<HTMLInputElement>(null)
  const retryFiles = useRef(new Map<string, File>())
  const { data: stored = [], isLoading } = useQuery({ queryKey: ['uploads'], queryFn: () => api.listUploads() })

  async function refreshDashboard() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['uploads'] }),
      queryClient.invalidateQueries({ queryKey: ['incidents'] }),
      queryClient.invalidateQueries({ queryKey: ['memory'] }),
      queryClient.invalidateQueries({ queryKey: ['overview'] }),
      queryClient.invalidateQueries({ queryKey: ['evaluation'] }),
      queryClient.invalidateQueries({ queryKey: ['pending-approvals'] }),
    ])
  }

  async function addFiles(files: File[]) {
    if (!files.length) return
    const created = await api.createUpload(files)
    const failed = created.filter((job) => job.stage === 'failed')
    failed.forEach((job) => retryFiles.current.set(job.id, files[created.indexOf(job)]))
    setFailures((current) => [...failed, ...current])
    if (created.some((job) => job.stage === 'completed')) await refreshDashboard()
  }

  async function retry(job: UploadJob) {
    const file = retryFiles.current.get(job.id)
    if (!file) return
    const [next] = await api.createUpload([file])
    retryFiles.current.delete(job.id)
    if (next.stage === 'failed') retryFiles.current.set(next.id, file)
    setFailures((current) => next.stage === 'failed'
      ? current.map((item) => item.id === job.id ? next : item)
      : current.filter((item) => item.id !== job.id))
    if (next.stage === 'completed') await refreshDashboard()
  }

  function loadDemo() {
    if (!window.confirm(`Load the ${datasets[dataset].label} dataset into this session? Existing uploads will be kept.`)) return
    const choice = datasets[dataset]
    const content = choice.format === 'log'
      ? `Adaptive Incident export\nAII_INCIDENT_MEMORY_BEGIN\n${JSON.stringify(choice.records)}\nAII_INCIDENT_MEMORY_END\n`
      : JSON.stringify(choice.records)
    addFiles([new File([content], `demo-${dataset}.${choice.format}`, { type: choice.format === 'json' ? 'application/json' : 'text/plain' })])
  }

  const remove = useMutation({ mutationFn: (id: string) => api.deleteUpload(id), onSuccess: refreshDashboard })
  function confirmDelete(job: UploadJob) {
    if (window.confirm(`Delete “${job.fileName}” and remove its records from this dashboard session?`)) remove.mutate(job.id)
  }
  const jobs = [...failures, ...stored]

  return <><PageHeader eyebrow="Memory ingestion" title="Upload incident records" description="Turn completed incident records into searchable Hindsight memory while retaining the full validated source and its ordered outcomes." action={<div className="flex flex-wrap gap-2"><select className="field w-auto" aria-label="Demo dataset" value={dataset} onChange={(event) => setDataset(event.target.value as DatasetChoice)}>{Object.entries(datasets).map(([key, item]) => <option key={key} value={key}>{item.label}</option>)}</select><button type="button" className="btn-secondary" onClick={loadDemo}><FileJson size={17} />Load selected dataset</button></div>} />
    <WorkflowNotice type="memory">Uploads remain visible when you change pages. Removing an upload rebuilds the dashboard session from the files that remain.</WorkflowNotice>
    <section className="panel mt-5 p-5"><p className="eyebrow">Architecture</p><h2 className="mt-1 font-bold text-navy-900">From source file to reusable evidence</h2><div className="mt-5 grid gap-2 md:grid-cols-6">{stages.map(({ key, label, icon: Icon, detail }, index) => <div key={key} className="relative"><div className="rounded-xl border bg-slate-50 p-3 text-center"><span className="mx-auto grid h-9 w-9 place-items-center rounded-lg bg-white text-blue-700 shadow-sm"><Icon size={18} /></span><p className="mt-2 text-xs font-bold">{label}</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{detail}</p></div>{index < stages.length - 1 && <ArrowDown className="mx-auto my-1 text-slate-300 md:absolute md:-right-3 md:top-9 md:-rotate-90" size={18} />}</div>)}</div></section>
    <section className="panel mt-5 p-5"><div onDragEnter={(event) => { event.preventDefault(); setDragging(true) }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(Array.from(event.dataTransfer.files)) }} className={`rounded-xl border-2 border-dashed p-8 text-center transition ${dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50'}`}><UploadCloud className="mx-auto text-blue-600" size={34} /><h2 className="mt-3 font-bold text-navy-900">Drop incident history files here</h2><p className="mt-1 text-sm text-slate-500">JSON, CSV, Markdown, text, log, or PDF · 5 MB maximum per file</p><button type="button" className="btn-primary mt-4" onClick={() => inputRef.current?.click()}>Choose files</button><input ref={inputRef} type="file" multiple accept=".json,.csv,.md,.txt,.log,.pdf,application/json,text/csv,text/plain,application/pdf" className="sr-only" onChange={(event) => addFiles(Array.from(event.target.files ?? []))} /></div></section>
    <section className="panel mt-5"><div className="panel-header"><div><p className="eyebrow">Uploaded evidence</p><h2 className="mt-1 font-bold text-navy-900">{jobs.length} file{jobs.length === 1 ? '' : 's'} in this session</h2></div>{stored.length > 0 && <StatusBadge value="COMPLETED" />}</div>{isLoading ? <p className="p-5 text-sm text-muted">Loading uploads…</p> : jobs.length === 0 ? <div className="p-5"><EmptyState title="No evidence uploaded" detail="Choose a demo bundle or upload an incident-history file." /></div> : <div className="divide-y">{jobs.map((job) => <article key={job.id} className="p-5"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div className="flex min-w-0 items-center gap-3">{job.stage === 'completed' ? <CheckCircle2 className="shrink-0 text-emerald-600" /> : <XCircle className="shrink-0 text-red-600" />}<div className="min-w-0"><p className="truncate text-sm font-bold">{job.fileName}</p><p className="text-xs text-slate-500">{(job.size / 1024).toFixed(1)} KB · {job.stage}</p></div></div><div className="flex gap-2">{job.stage === 'failed' && <button type="button" className="btn-secondary" onClick={() => retry(job)}><RefreshCw size={15} />Retry validation</button>}<button type="button" className="btn-secondary text-red-700" disabled={remove.isPending} onClick={() => job.stage === 'failed' ? setFailures((current) => current.filter((item) => item.id !== job.id)) : confirmDelete(job)}><Trash2 size={15} />Delete</button></div></div>{job.error ? <p className="mt-3 rounded-lg bg-red-50 p-3 text-xs font-medium text-red-700">{job.error}</p> : <div className="mt-3 grid grid-cols-3 gap-2 text-center"><div className="rounded-lg bg-slate-50 p-2"><p className="text-lg font-bold">{job.chunks}</p><p className="text-[10px] uppercase text-slate-500">Chunks</p></div><div className="rounded-lg bg-red-50 p-2"><p className="text-lg font-bold text-red-700">{job.failedRemediationChunks}</p><p className="text-[10px] uppercase text-red-600">Failed-fix chunks</p></div><div className="rounded-lg bg-emerald-50 p-2"><p className="text-lg font-bold text-emerald-700">{job.storedIncidents}</p><p className="text-[10px] uppercase text-emerald-600">Stored incidents</p></div></div>}</article>)}</div>}</section>
  </>
}
