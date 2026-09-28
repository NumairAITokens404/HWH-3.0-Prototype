import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowLeft, CheckCircle2, CircleDot, Play, ShieldCheck, X } from 'lucide-react'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api'
import { ErrorState, LoadingState, OutcomeTimeline, StatusBadge, WorkflowNotice } from '../components/ui'

export function IncidentPage() {
  const { id = 'TEST-001' } = useParams()
  return <IncidentWorkspace key={id} id={id} />
}

function IncidentWorkspace({ id }: { id: string }) {
  const client = useQueryClient()
  const [approvalOpen, setApprovalOpen] = useState(false)
  const [reviewer, setReviewer] = useState('')
  const { data: current, isLoading, error } = useQuery({ queryKey: ['incident', id], queryFn: () => api.getIncident(id) })
  const refreshShared = () => Promise.all(['incidents', 'overview', 'pending-approvals', 'evaluation', 'memory', 'uploads'].map((key) => client.invalidateQueries({ queryKey: [key] })))
  const workflow = useMutation({
    mutationFn: () => api.runWorkflow(id),
    onSuccess: async (next) => {
      client.setQueryData(['incident', id], next)
      if (next.workflow_status === 'APPROVAL_REQUIRED') setApprovalOpen(true)
      await refreshShared()
    },
  })
  const approval = useMutation({
    mutationFn: (approved: boolean) => api.submitApproval(id, approved, reviewer.trim()),
    onSuccess: async (next) => {
      client.setQueryData(['incident', id], next)
      setApprovalOpen(next.workflow_status === 'BLOCKED')
      await refreshShared()
    },
  })
  if (error) return <ErrorState detail={error.message} />
  if (isLoading || !current) return <LoadingState label="Recalling incident evidence from memory" />
  const hasAction = current.recommended_action !== 'No action recommended'
  const needsReview = ['HIGH', 'CRITICAL'].includes(current.incident.severity) || current.policy_status === 'HUMAN_APPROVAL_REQUIRED'
  const terminal = !!current.verification || current.workflow_status === 'DENIED'
  const busy = workflow.isPending || approval.isPending
  const steps = [
    { label: 'Incident received', done: true },
    { label: 'Historical evidence recalled', done: current.evidence.length > 0 },
    { label: 'Recommendation validated', done: hasAction },
    { label: current.workflow_status === 'DENIED' ? 'Reviewer denied action' : needsReview ? 'Human approval' : 'Policy allowed action', done: current.policy_status === 'ALLOWED' || current.workflow_status === 'DENIED' },
    { label: 'Simulated remediation', done: !!current.tool_acknowledgement },
    { label: 'Operation reprocessed', done: !!current.reprocessing_result },
    { label: 'Independent verification', done: !!current.verification },
    { label: current.verification ? 'Outcome retained in memory' : 'Investigation retained in memory', done: current.memory_stored },
  ]
  const reviewOrRun = () => {
    approval.reset()
    if (current.workflow_status === 'APPROVAL_REQUIRED') setApprovalOpen(true)
    else workflow.mutate()
  }
  return <>
    <Link to="/incidents" className="mb-4 inline-flex items-center gap-2 text-sm font-semibold text-slate-600"><ArrowLeft size={16} />Back to incidents</Link>
    <div className="mb-4 flex flex-col justify-between gap-3 lg:flex-row lg:items-start">
      <div><div className="flex flex-wrap items-center gap-2"><h1 className="font-mono text-xl font-semibold text-navy-900">{id}</h1><StatusBadge value={current.incident.severity} /><StatusBadge value={current.workflow_status} /></div><p className="mt-1.5 text-[13px] text-muted">{current.incident.service} · {current.incident.environment} · <span className="font-mono">{current.incident.error_code}</span></p></div>
      {!terminal && <button className="btn-primary" onClick={reviewOrRun} disabled={busy}>{needsReview ? <ShieldCheck size={16} /> : <Play size={16} />}{workflow.isPending ? 'Learning and investigating…' : needsReview ? 'Review action' : hasAction ? 'Run simulated workflow' : 'Learn and run workflow'}</button>}
    </div>
    {workflow.error && <div role="alert" className="mb-4"><ErrorState title="Workflow needs attention" detail={workflow.error.message} /></div>}
    {workflow.isPending && <div role="status" className="mb-4"><WorkflowNotice type="memory">Recalling evidence, retaining missing demo history when needed, and checking the recommendation. Local memory processing can take a few minutes.</WorkflowNotice></div>}
    {!hasAction && <div className="mb-4 rounded-md border p-4" role="status"><p className="text-sm font-semibold">More evidence is needed</p><p className="mt-1 text-sm text-muted">{current.reasoning}</p><p className="mt-2 text-sm text-muted">Start the workflow to learn from matching bundled history and recall again. You can also <Link to="/memory/upload" className="text-blue-700 underline">upload incident records</Link> and retry.</p></div>}
    <WorkflowNotice type="simulation">Remediation and verification are simulated. High and Critical incidents always require approval; medium and high risk actions also require approval.</WorkflowNotice>
    {!!current.learned_from?.length && <div className="mt-3"><WorkflowNotice type="memory">Learned from bundled source history: <strong>{current.learned_from.join(', ')}</strong>. These records were retained before investigating again.</WorkflowNotice></div>}
    {current.memory_stored && <div className="mt-3"><WorkflowNotice type="memory"><strong>{current.verification ? 'Verified outcome stored in memory.' : 'Investigation and review state stored in memory.'}</strong> <Link to="/memory" className="underline">Inspect retained records</Link>. {current.verification ? 'Later incidents can recall this experience.' : 'Recovery has not been verified.'}</WorkflowNotice></div>}
    <div className="mt-4 grid gap-4 xl:grid-cols-[1.25fr_.75fr]">
      <div className="space-y-4">
        <section className="panel p-4"><p className="eyebrow">Incident context</p><h2 className="section-title mt-1">Symptoms and identifiers</h2><div className="mt-3 flex flex-wrap gap-1.5">{current.incident.symptoms.map((symptom) => <span key={symptom} className="rounded-md border bg-slate-50 px-2.5 py-1.5 text-xs text-navy-700">{symptom}</span>)}</div><dl className="mt-4 grid gap-x-5 gap-y-3 border-t pt-3 sm:grid-cols-2"><div><dt className="data-label">Error message</dt><dd className="mt-1 text-xs text-ink">{current.incident.error_message ?? 'No message supplied'}</dd></div><div><dt className="data-label">Affected reference</dt><dd className="mt-1 font-mono text-xs text-ink">{current.incident.transaction_id ?? current.incident.job_id ?? current.incident.customer_id ?? 'None supplied'}</dd></div></dl>{current.incident.recent_change && <p className="mt-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900"><strong>Recent change:</strong> {current.incident.recent_change}</p>}</section>
        <section className="panel p-4"><p className="eyebrow">Investigation</p><h2 className="section-title mt-1">Recommendation and evidence</h2>
          <div className="mt-4 space-y-4"><div className="grid gap-4 sm:grid-cols-2"><div><p className="data-label">Likely root cause</p><p className="mt-1 text-[13px] font-semibold text-ink">{current.likely_root_cause}</p></div><div><p className="data-label">Recommended action</p><p className="mt-1 font-mono text-xs font-semibold text-blue-700">{current.recommended_action}</p></div></div>
            <div><div className="mb-1.5 flex justify-between text-xs"><span>Historical confidence</span><span>{(current.confidence * 100).toFixed(1)}%</span></div><div className="h-1.5 rounded-full bg-slate-100"><div className="h-full rounded-full bg-blue-600" style={{ width: `${current.confidence * 100}%` }} /></div></div>
            <p className="text-[13px] leading-5 text-muted">{current.reasoning}</p><dl className="grid gap-3 border-y py-3 sm:grid-cols-2"><div><dt className="data-label">Investigation method</dt><dd className="mt-1 text-xs">{current.investigation_method.replaceAll('_', ' ')}</dd></div><div><dt className="data-label">Model</dt><dd className="mt-1 font-mono text-xs">{current.model_name ?? 'Rules only'}</dd></div></dl>
            {current.fallback_reason && <p className="text-xs text-muted">Historical fallback: {current.fallback_reason.replaceAll('_', ' ')}</p>}
            <div className="flex flex-wrap gap-2">{hasAction && <StatusBadge value={current.risk_level} label={`${current.risk_level.toLowerCase()} action risk`} />}<StatusBadge value={current.policy_status} /></div>
            {current.failed_actions_avoided.length > 0 && <div className="rounded-md border border-red-200 bg-red-50 p-3"><p className="data-label text-red-700">Historical failures to consider</p><p className="mt-1 font-mono text-xs font-semibold text-red-900">{current.failed_actions_avoided.join(', ')}</p></div>}
          </div>
        </section>
        <section className="panel p-4"><p className="eyebrow">Recalled memory</p><h2 className="mt-1 font-bold">Successful and failed remediation</h2><div className="mt-4 grid gap-4 lg:grid-cols-2">{!current.evidence.length && <p className="text-sm text-muted">No comparable recovery evidence recalled yet.</p>}{current.evidence.map((item) => <article key={item.incident_id} className="rounded-xl border p-4"><div className="mb-4 flex items-start justify-between"><div><p className="font-mono text-sm font-bold">{item.incident_id}</p><p className="text-xs text-slate-500">{item.root_cause}</p></div><span className="text-xs font-bold text-purple-700">{Math.round(item.similarity * 100)}% match</span></div><OutcomeTimeline outcomes={item.outcomes} /></article>)}</div></section>
      </div>
      <div className="space-y-5"><section className="panel p-5"><p className="eyebrow">Response timeline</p><h2 className="mt-1 font-bold">Current incident</h2><ol className="mt-5 space-y-4">{steps.map((step) => <li key={step.label} className="flex items-center gap-3"><span aria-label={step.done ? 'Completed' : 'Pending'} className={`grid h-7 w-7 place-items-center rounded-full ${step.done ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>{step.done ? <CheckCircle2 size={16} /> : <CircleDot size={15} />}</span><span className={`text-sm ${step.done ? 'font-semibold text-slate-800' : 'text-slate-500'}`}>{step.label}</span></li>)}</ol></section>
        {current.verification && <section className="panel p-4"><p className="eyebrow">Independent verification</p><h2 className="section-title mt-1">Observed state</h2><dl className="mt-3 divide-y rounded-md border"><div className="flex justify-between px-3 py-2.5 text-xs"><dt>Tool acknowledgement</dt><dd><StatusBadge value={current.tool_acknowledgement ?? 'FAILED'} /></dd></div><div className="flex justify-between px-3 py-2.5 text-xs"><dt>Service health</dt><dd>{current.verification.service_healthy ? 'Healthy' : 'Unhealthy'}</dd></div><div className="flex justify-between px-3 py-2.5 text-xs"><dt>Affected operation</dt><dd>{current.verification.operation_recovered ? 'Recovered' : 'Not recovered'}</dd></div><div className="flex justify-between px-3 py-2.5 text-xs"><dt>Overall result</dt><dd><StatusBadge value={current.verification.result} /></dd></div></dl></section>}
      </div>
    </div>
    {approvalOpen && <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950/50 p-4"><div role="dialog" aria-modal="true" aria-labelledby="approval-title" className="w-full max-w-lg rounded-xl bg-white shadow-2xl"><div className="flex items-start justify-between border-b p-5"><div><p className="eyebrow">Bound policy approval</p><h2 id="approval-title" className="mt-1 text-lg font-bold">Authorize simulated attempt</h2></div><button onClick={() => setApprovalOpen(false)} disabled={approval.isPending} className="rounded p-1 text-slate-500" aria-label="Close"><X /></button></div>
      <div className="space-y-4 p-5"><WorkflowNotice type="approval">Approval authorizes one attempt. Independent verification determines recovery, and the observed outcome is retained.</WorkflowNotice><div className="rounded-lg bg-slate-50 p-4"><p className="font-mono text-sm font-bold">{current.recommended_action}</p><div className="mt-2 flex gap-2"><StatusBadge value={current.incident.severity} label={`${current.incident.severity.toLowerCase()} severity`} /><StatusBadge value={current.risk_level} label={`${current.risk_level.toLowerCase()} action risk`} /></div><p className="mt-3 text-sm text-slate-600">Supported by {current.evidence.map((item) => item.incident_id).join(', ')}.</p></div><label className="block"><span className="label">Reviewer name</span><input className="field" value={reviewer} onChange={(event) => setReviewer(event.target.value)} placeholder="Enter your name" /></label>{approval.error && <p role="alert" className="text-sm text-red-700">{approval.error.message}</p>}{current.workflow_status === 'BLOCKED' && <p role="alert" className="text-sm text-red-700">The approval did not match the current recommendation. Close this review and retry.</p>}</div>
      <div className="flex justify-end gap-2 border-t p-5"><button className="btn-secondary text-red-700" disabled={!reviewer.trim() || approval.isPending} onClick={() => approval.mutate(false)}>Reject</button><button className="btn-primary" disabled={!reviewer.trim() || approval.isPending} onClick={() => approval.mutate(true)}>{approval.isPending ? 'Recording decision…' : 'Approve simulated action'}</button></div>
    </div></div>}
  </>
}
