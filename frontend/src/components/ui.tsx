import { AlertCircle, AlertTriangle, CheckCircle2, Clock3, Database, Inbox, LoaderCircle, ShieldAlert, X, XCircle } from 'lucide-react'
import clsx from 'clsx'
import type { Outcome } from '../types/domain'

const tones: Record<string, string> = {
  SUCCESS: 'border-green-200 bg-[#F0FDF4] text-[#15803D]', RESOLVED: 'border-green-200 bg-[#F0FDF4] text-[#15803D]', COMPLETED: 'border-green-200 bg-[#F0FDF4] text-[#15803D]', PASSED: 'border-green-200 bg-[#F0FDF4] text-[#15803D]', ALLOWED: 'border-green-200 bg-[#F0FDF4] text-[#15803D]',
  FAILED: 'border-red-200 bg-[#FEF3F2] text-[#B42318]', CRITICAL: 'border-red-200 bg-[#FEF3F2] text-[#B42318]', HIGH: 'border-red-200 bg-[#FEF3F2] text-[#B42318]', BLOCKED: 'border-red-200 bg-[#FEF3F2] text-[#B42318]',
  PARTIAL: 'border-amber-200 bg-[#FFFBEB] text-[#B45309]', MEDIUM: 'border-amber-200 bg-[#FFFBEB] text-[#B45309]', APPROVAL_REQUIRED: 'border-amber-200 bg-[#FFFBEB] text-[#B45309]', HUMAN_APPROVAL_REQUIRED: 'border-amber-200 bg-[#FFFBEB] text-[#B45309]',
  LOW: 'border-blue-200 bg-blue-50 text-blue-700', INVESTIGATING: 'border-blue-200 bg-blue-50 text-blue-700', INSUFFICIENT_EVIDENCE: 'border-line bg-slate-50 text-muted',
}
const labels: Record<string, string> = { SUCCESS: 'Success', RESOLVED: 'Resolved', COMPLETED: 'Completed', PASSED: 'Passed', FAILED: 'Failed', CRITICAL: 'Critical', HIGH: 'High', MEDIUM: 'Medium', LOW: 'Low', PARTIAL: 'Partial recovery', APPROVAL_REQUIRED: 'Approval required', HUMAN_APPROVAL_REQUIRED: 'Approval required', INVESTIGATING: 'Investigating', ALLOWED: 'Allowed by policy', INSUFFICIENT_EVIDENCE: 'Insufficient evidence', BLOCKED: 'Blocked' }

export function StatusBadge({ value, label }: { value: string; label?: string }) {
  return <span data-status={value} className={clsx('status-badge inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold', tones[value] ?? 'border-line bg-slate-50 text-muted')}>{label ?? labels[value] ?? value.replaceAll('_', ' ').toLowerCase()}</span>
}

export function PageHeader({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return <header className="hero-header mb-6 flex flex-col justify-between gap-6 md:flex-row md:items-end"><div className="min-w-0"><p className="eyebrow mb-1.5">{eyebrow}</p><h1 className="hero-title font-bold text-ink">{title}</h1><p className="mt-4 max-w-2xl text-base leading-7 text-muted">{description}</p></div>{action && <div className="shrink-0">{action}</div>}</header>
}

export function StatCard({ label, value, hint, icon: Icon, tone = 'blue' }: { label: string; value: string | number; hint: string; icon: React.ElementType; tone?: 'blue' | 'green' | 'amber' | 'purple' }) {
  const colors = { blue: 'bg-blue-50 text-blue-700', green: 'bg-[#F0FDF4] text-[#15803D]', amber: 'bg-[#FFFBEB] text-[#B45309]', purple: 'bg-[#F9F5FF] text-memory' }
  return <div className="min-w-0 border-r px-4 py-3.5 last:border-r-0"><div className="flex items-center justify-between gap-2"><p className="truncate text-xs font-medium text-muted">{label}</p><span className={clsx('rounded-md p-1.5', colors[tone])}><Icon size={15} /></span></div><p className="mt-1 text-xl font-semibold tabular-nums text-navy-900">{value}</p><p className="mt-1 truncate text-[11px] text-faint">{hint}</p></div>
}

export function LoadingState({ label = 'Loading operations data' }: { label?: string }) { return <div className="panel flex min-h-40 items-center justify-center gap-2.5 text-[13px] text-muted"><LoaderCircle className="animate-spin text-blue-600" size={18} />{label}</div> }
export function EmptyState({ title, detail }: { title: string; detail: string }) { return <div className="panel flex min-h-40 flex-col items-center justify-center px-6 text-center"><Inbox className="mb-2.5 text-faint" size={24} /><p className="font-semibold text-ink">{title}</p><p className="mt-1 text-[13px] text-muted">{detail}</p></div> }
export function ErrorState({ title = 'Unable to load data', detail }: { title?: string; detail: string }) { return <div className="panel flex min-h-40 flex-col items-center justify-center px-6 text-center"><AlertCircle className="mb-2.5 text-[#B42318]" size={24} /><p className="font-semibold text-ink">{title}</p><p className="mt-1 text-[13px] text-muted">{detail}</p></div> }

export function OutcomeTimeline({ outcomes }: { outcomes: Outcome[] }) {
  return <ol>{outcomes.map((outcome, index) => { const Icon = outcome.result === 'SUCCESS' ? CheckCircle2 : outcome.result === 'FAILED' ? XCircle : AlertTriangle; return <li key={outcome.outcome_id} className="relative flex gap-3 pb-4 last:pb-0"><div className="relative z-10 bg-white py-0.5"><Icon size={17} data-result={outcome.result} className={outcome.result === 'SUCCESS' ? 'text-[#15803D]' : outcome.result === 'FAILED' ? 'text-[#B42318]' : 'text-[#B45309]'} /></div>{index < outcomes.length - 1 && <span className="absolute left-2 top-5 h-[calc(100%-8px)] w-px bg-line" />}<div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><p className="font-mono text-xs font-semibold text-ink">{outcome.action}</p><StatusBadge value={outcome.result} /></div><p className="mt-1 text-xs leading-5 text-muted">{outcome.lesson_learned}</p><p className="mt-1 font-mono text-[10px] text-faint">{outcome.outcome_id} · {outcome.verified ? 'verified' : 'unverified'}</p></div></li> })}</ol>
}

export function WorkflowNotice({ type, children }: { type: 'simulation' | 'memory' | 'approval'; children: React.ReactNode }) {
  const config = type === 'simulation' ? [ShieldAlert, 'border-blue-200 bg-blue-50 text-blue-900'] : type === 'memory' ? [Database, 'border-purple-200 bg-[#F9F5FF] text-purple-900'] : [Clock3, 'border-amber-200 bg-[#FFFBEB] text-amber-900']
  const Icon = config[0] as React.ElementType
  return <div className={clsx('flex gap-2.5 rounded-md border px-3.5 py-2.5 text-[13px] leading-5', config[1])}><Icon className="mt-0.5 shrink-0" size={16} /><div>{children}</div></div>
}

export function ConfirmationDialog({ open, title, description, confirmLabel, tone = 'primary', busy, onClose, onConfirm, children }: { open: boolean; title: string; description: string; confirmLabel: string; tone?: 'primary' | 'danger'; busy?: boolean; onClose: () => void; onConfirm: () => void; children?: React.ReactNode }) {
  if (!open) return null
  return <div className="fixed inset-0 z-50 grid place-items-center bg-navy-950/45 p-4"><div role="dialog" aria-modal="true" aria-labelledby="confirm-title" className="w-full max-w-md rounded-lg border bg-white shadow-xl"><div className="flex items-start justify-between border-b px-5 py-4"><div><h2 id="confirm-title" className="text-base font-semibold text-navy-900">{title}</h2><p className="mt-1 text-xs leading-5 text-muted">{description}</p></div><button onClick={onClose} className="rounded-md p-1 text-faint hover:bg-slate-50 hover:text-muted" aria-label="Close"><X size={17} /></button></div>{children && <div className="px-5 py-4">{children}</div>}<div className="flex justify-end gap-2 border-t px-5 py-3"><button className="btn-secondary" onClick={onClose} disabled={busy}>Cancel</button><button className={tone === 'danger' ? 'btn-danger' : 'btn-primary'} onClick={onConfirm} disabled={busy}>{confirmLabel}</button></div></div></div>
}
