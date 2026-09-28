import { ArrowDown, BrainCircuit, CheckCircle2, Database, FileCheck2, FileJson, Layers3, RefreshCw, UploadCloud, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { api } from '../api'
import { PageHeader, StatusBadge, WorkflowNotice } from '../components/ui'
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
const order = ['uploading', 'extracting', 'validating', 'chunking', 'embedding', 'storing', 'completed']

export function UploadPage() {
  const [jobs, setJobs] = useState<UploadJob[]>([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    const active = jobs.find((job) => job.stage !== 'completed' && job.stage !== 'failed')
    if (!active) return
    const timer = window.setTimeout(async () => {
      const next = await api.advanceUpload(active)
      setJobs((current) => current.map((job) => job.id === next.id ? next : job))
    }, 650)
    return () => window.clearTimeout(timer)
  }, [jobs])

  async function addFiles(files: File[]) {
    if (!files.length) return
    const created = await api.createUpload(files)
    setJobs((current) => [...created, ...current])
  }
  function loadDemo() {
    addFiles([new File([JSON.stringify(demoHistory)], 'remediation_history.json', { type: 'application/json' })])
  }
  const complete = jobs.filter((job) => job.stage === 'completed')
  return <><PageHeader eyebrow="Memory ingestion" title="Upload incident records" description="Turn completed incident records into searchable Hindsight memory while retaining the full validated source and its ordered outcomes." action={<button className="btn-secondary" onClick={loadDemo}><FileJson size={17} />Load demo dataset</button>} />
    <WorkflowNotice type="memory">Files are validated and stored by the configured backend. Complete records remain authoritative; embeddings support retrieval when Hindsight is active.</WorkflowNotice>
    <section className="panel mt-5 p-5"><p className="eyebrow">Architecture</p><h2 className="mt-1 font-bold text-navy-900">From source file to reusable evidence</h2><div className="mt-5 grid gap-2 md:grid-cols-6">{stages.map(({ key, label, icon: Icon, detail }, index) => <div key={key} className="relative"><div className="rounded-xl border bg-slate-50 p-3 text-center"><span className="mx-auto grid h-9 w-9 place-items-center rounded-lg bg-white text-blue-700 shadow-sm"><Icon size={18} /></span><p className="mt-2 text-xs font-bold">{label}</p><p className="mt-1 text-[10px] leading-4 text-slate-500">{detail}</p></div>{index < stages.length - 1 && <ArrowDown className="mx-auto my-1 text-slate-300 md:absolute md:-right-3 md:top-9 md:-rotate-90" size={18} />}</div>)}</div><div className="mt-4 grid gap-3 rounded-xl border border-purple-200 bg-purple-50 p-4 sm:grid-cols-2"><div className="flex gap-3"><Database className="shrink-0 text-purple-700" size={20} /><div><p className="text-sm font-bold text-purple-950">Complete incident records</p><p className="text-xs leading-5 text-purple-800">Validated source of truth for sequence, IDs, and outcomes.</p></div></div><div className="flex gap-3"><XCircle className="shrink-0 text-red-600" size={20} /><div><p className="text-sm font-bold text-purple-950">Failed remediation memory</p><p className="text-xs leading-5 text-purple-800">Negative evidence stays searchable so ineffective fixes are not repeated.</p></div></div></div></section>
    <section className="panel mt-5 p-5"><div onDragEnter={(event) => { event.preventDefault(); setDragging(true) }} onDragOver={(event) => event.preventDefault()} onDragLeave={() => setDragging(false)} onDrop={(event) => { event.preventDefault(); setDragging(false); addFiles(Array.from(event.dataTransfer.files)) }} className={`rounded-xl border-2 border-dashed p-8 text-center transition ${dragging ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50'}`}><UploadCloud className="mx-auto text-blue-600" size={34} /><h2 className="mt-3 font-bold text-navy-900">Drop incident JSON files here</h2><p className="mt-1 text-sm text-slate-500">Multiple files supported · JSON only · 5 MB maximum per file</p><button className="btn-primary mt-4" onClick={() => inputRef.current?.click()}>Choose files</button><input ref={inputRef} type="file" multiple accept=".json,application/json" className="sr-only" onChange={(event) => addFiles(Array.from(event.target.files ?? []))} /></div></section>
    {jobs.length > 0 && <section className="panel mt-5"><div className="panel-header"><div><p className="eyebrow">Processing queue</p><h2 className="mt-1 font-bold text-navy-900">{jobs.length} file{jobs.length === 1 ? '' : 's'}</h2></div>{complete.length > 0 && <StatusBadge value="COMPLETED" />}</div><div className="divide-y">{jobs.map((job) => <article key={job.id} className="p-5"><div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div className="flex min-w-0 items-center gap-3">{job.stage === 'completed' ? <CheckCircle2 className="shrink-0 text-emerald-600" /> : job.stage === 'failed' ? <XCircle className="shrink-0 text-red-600" /> : <RefreshCw className="shrink-0 animate-spin text-blue-600" />}<div className="min-w-0"><p className="truncate text-sm font-bold">{job.fileName}</p><p className="text-xs text-slate-500">{(job.size / 1024).toFixed(1)} KB · {job.stage.replaceAll('_', ' ')}</p></div></div>{job.stage === 'failed' && <button className="btn-secondary" onClick={() => setJobs((current) => current.map((item) => item.id === job.id ? { ...item, stage: 'uploading', progress: 8, error: undefined } : item))}><RefreshCw size={15} />Retry</button>}</div>{job.error ? <p className="mt-3 rounded-lg bg-red-50 p-3 text-xs font-medium text-red-700">{job.error}</p> : <><div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600 transition-all duration-500" style={{ width: `${job.progress}%` }} /></div><div className="mt-3 grid grid-cols-3 gap-2 text-center"><div className="rounded-lg bg-slate-50 p-2"><p className="text-lg font-bold">{job.chunks}</p><p className="text-[10px] uppercase text-slate-500">Chunks</p></div><div className="rounded-lg bg-red-50 p-2"><p className="text-lg font-bold text-red-700">{job.failedRemediationChunks}</p><p className="text-[10px] uppercase text-red-600">Failed-fix chunks</p></div><div className="rounded-lg bg-emerald-50 p-2"><p className="text-lg font-bold text-emerald-700">{job.storedIncidents}</p><p className="text-[10px] uppercase text-emerald-600">Stored incidents</p></div></div><div className="mt-4 flex flex-wrap gap-1.5">{stages.map((stage) => { const currentIndex = order.indexOf(job.stage); const stageIndex = order.indexOf(stage.key); return <span key={stage.key} className={`rounded-full px-2 py-1 text-[10px] font-bold ${job.stage === 'completed' || stageIndex < currentIndex ? 'bg-emerald-100 text-emerald-700' : stageIndex === currentIndex ? 'bg-blue-100 text-blue-700' : 'bg-slate-100 text-slate-400'}`}>{stage.label}</span> })}</div></>}</article>)}</div></section>}
  </>
}
