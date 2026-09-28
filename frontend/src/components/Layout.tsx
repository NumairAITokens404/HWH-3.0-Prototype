import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Activity, Bell, CheckSquare, Database, FlaskConical, Menu, ServerCog, Upload, X } from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink, Outlet } from 'react-router-dom'
import { api } from '../api'

const links = [
  { to: '/', label: 'Overview', icon: Activity, end: true },
  { to: '/incidents', label: 'Incidents', icon: ServerCog },
  { to: '/memory', label: 'Memory', icon: Database },
  { to: '/memory/upload', label: 'Ingest records', icon: Upload },
  { to: '/approvals', label: 'Approvals', icon: CheckSquare },
  { to: '/evaluation', label: 'Evaluation', icon: FlaskConical },
]

function Navigation({ close, pendingApprovals }: { close: () => void; pendingApprovals: number }) {
  return <>
    <div className="flex h-14 items-center gap-2.5 border-b border-white/10 px-4">
      <span className="grid h-8 w-8 grid-cols-2 gap-0.5 rounded-md bg-white p-1.5" aria-hidden="true"><span className="rounded-sm bg-blue-600" /><span className="rounded-sm bg-[#6941C6]" /><span className="rounded-sm bg-[#15803D]" /><span className="rounded-sm bg-[#B45309]" /></span>
      <div><p className="text-[13px] font-semibold leading-4">Adaptive Incident</p><p className="text-[10px] text-slate-400">Operations console</p></div>
    </div>
    <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Workspace</div>
    <nav className="space-y-0.5 px-2.5" aria-label="Primary navigation">
      {links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={close} className={({ isActive }) => clsx('relative flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors duration-150', isActive ? 'bg-navy-800 text-white before:absolute before:-left-2.5 before:h-5 before:w-0.5 before:bg-blue-500' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100')}>
        <Icon size={16} /><span className="flex-1">{label}</span>{to === '/approvals' && pendingApprovals > 0 && <span className="min-w-5 rounded-full bg-amber-100 px-1.5 py-0.5 text-center text-[10px] font-bold text-amber-800">{pendingApprovals}</span>}
      </NavLink>)}
    </nav>
    <div className="mt-auto border-t border-white/10 p-3"><div className="flex items-start gap-2 rounded-md border border-white/10 bg-white/[0.03] p-2.5"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-500" /><div><p className="text-[11px] font-semibold text-slate-200">Simulation ready</p><p className="mt-0.5 text-[10px] leading-4 text-slate-500">No production systems are connected.</p></div></div></div>
  </>
}

export function Layout() {
  const [open, setOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const { data } = useQuery({ queryKey: ['overview'], queryFn: () => api.getOverview() })
  const pendingApprovals = data?.pendingApprovals ?? 0
  const active = data?.active ?? 0
  const hasNotifications = pendingApprovals > 0 || active > 0

  return <div className="min-h-screen bg-canvas">
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-56 flex-col bg-navy-950 text-white lg:flex"><Navigation close={() => setOpen(false)} pendingApprovals={pendingApprovals} /></aside>
    {open && <div className="fixed inset-0 z-50 lg:hidden"><button className="absolute inset-0 bg-slate-950/40" aria-label="Close navigation" onClick={() => setOpen(false)} /><aside className="relative flex h-full w-64 flex-col bg-navy-950 text-white"><Navigation close={() => setOpen(false)} pendingApprovals={pendingApprovals} /><button onClick={() => setOpen(false)} className="absolute right-2.5 top-2.5 rounded-md p-2 text-slate-400 hover:bg-white/5" aria-label="Close navigation"><X size={18} /></button></aside></div>}
    <div className="lg:pl-56">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-white px-4 md:px-6">
        <div className="flex items-center gap-3"><button className="rounded-md border p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={18} /></button><div><p className="text-[13px] font-semibold text-navy-900">Production operations</p><p className="hidden text-[11px] text-muted sm:block">Evidence and recovery state</p></div></div>
        <div className="relative flex items-center gap-3"><span className="hidden rounded-md border bg-slate-50 px-2.5 py-1.5 text-[11px] font-medium text-muted md:inline-flex">Environment: demo</span><button type="button" className="relative rounded-md border p-2 text-muted transition-colors duration-150 hover:bg-slate-50" aria-label="Notifications" aria-expanded={notificationsOpen} onClick={() => setNotificationsOpen((value) => !value)}><Bell size={16} />{hasNotifications && <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-amber-600" />}</button><span className="grid h-8 w-8 place-items-center rounded-full bg-navy-800 text-[11px] font-semibold text-white" title="On-call engineer">OE</span>
          {notificationsOpen && <div role="dialog" aria-label="Notification center" className="absolute right-10 top-11 w-80 overflow-hidden rounded-lg border bg-white shadow-xl"><div className="flex items-center justify-between border-b px-4 py-3"><div><p className="text-sm font-bold text-navy-900">Notifications</p><p className="text-[11px] text-muted">Live session status</p></div><button type="button" className="rounded p-1 text-muted hover:bg-slate-100" onClick={() => setNotificationsOpen(false)} aria-label="Close notifications"><X size={15} /></button></div><div className="divide-y">{pendingApprovals > 0 && <Link to="/approvals" onClick={() => setNotificationsOpen(false)} className="block px-4 py-3 hover:bg-slate-50"><p className="text-xs font-bold text-amber-800">{pendingApprovals} approval{pendingApprovals === 1 ? '' : 's'} waiting</p><p className="mt-1 text-[11px] text-muted">Review actions created from incident workflows.</p></Link>}{active > 0 && <Link to="/incidents" onClick={() => setNotificationsOpen(false)} className="block px-4 py-3 hover:bg-slate-50"><p className="text-xs font-bold text-navy-900">{active} active incident{active === 1 ? '' : 's'}</p><p className="mt-1 text-[11px] text-muted">Continue investigation and verification.</p></Link>}<Link to="/evaluation" onClick={() => setNotificationsOpen(false)} className="block px-4 py-3 hover:bg-slate-50"><p className="text-xs font-bold text-blue-700">Learning score {data?.learningScore.toFixed(1) ?? '0.0'}%</p><p className="mt-1 text-[11px] text-muted">{data?.learningCompleted ?? 0} of {data?.learningTotal ?? 6} checkpoints complete.</p></Link>{!hasNotifications && <p className="px-4 py-5 text-center text-xs text-muted">No incidents or approvals need attention.</p>}</div></div>}
        </div>
      </header>
      <main className="mx-auto max-w-[1320px] p-4 md:p-6"><Outlet /></main>
    </div>
  </div>
}
