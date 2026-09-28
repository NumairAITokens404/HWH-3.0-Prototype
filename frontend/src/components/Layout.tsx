import { Activity, Bell, CheckSquare, Database, FlaskConical, Menu, ServerCog, Upload, X } from 'lucide-react'
import { useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'
import clsx from 'clsx'

const links = [
  { to: '/', label: 'Overview', icon: Activity, end: true },
  { to: '/incidents', label: 'Incidents', icon: ServerCog },
  { to: '/memory', label: 'Memory', icon: Database },
  { to: '/memory/upload', label: 'Ingest records', icon: Upload },
  { to: '/approvals', label: 'Approvals', icon: CheckSquare, count: 2 },
  { to: '/evaluation', label: 'Evaluation', icon: FlaskConical },
]

function Navigation({ close }: { close: () => void }) {
  return <>
    <div className="flex h-14 items-center gap-2.5 border-b border-white/10 px-4">
      <span className="grid h-8 w-8 grid-cols-2 gap-0.5 rounded-md bg-white p-1.5" aria-hidden="true"><span className="rounded-sm bg-blue-600" /><span className="rounded-sm bg-[#6941C6]" /><span className="rounded-sm bg-[#15803D]" /><span className="rounded-sm bg-[#B45309]" /></span>
      <div><p className="text-[13px] font-semibold leading-4">Adaptive Incident</p><p className="text-[10px] text-slate-400">Operations console</p></div>
    </div>
    <div className="px-3 pb-2 pt-4 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">Workspace</div>
    <nav className="space-y-0.5 px-2.5" aria-label="Primary navigation">
      {links.map(({ to, label, icon: Icon, end, count }) => <NavLink key={to} to={to} end={end} onClick={close} className={({ isActive }) => clsx('relative flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] font-medium transition-colors duration-150', isActive ? 'bg-navy-800 text-white before:absolute before:-left-2.5 before:h-5 before:w-0.5 before:bg-blue-500' : 'text-slate-400 hover:bg-white/5 hover:text-slate-100')}>
        <Icon size={16} /><span className="flex-1">{label}</span>{count && <span className="min-w-5 rounded-full bg-amber-100 px-1.5 py-0.5 text-center text-[10px] font-bold text-amber-800">{count}</span>}
      </NavLink>)}
    </nav>
    <div className="mt-auto border-t border-white/10 p-3">
      <div className="flex items-start gap-2 rounded-md border border-white/10 bg-white/[0.03] p-2.5"><span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-emerald-500" /><div><p className="text-[11px] font-semibold text-slate-200">Simulation ready</p><p className="mt-0.5 text-[10px] leading-4 text-slate-500">No production systems are connected.</p></div></div>
    </div>
  </>
}

export function Layout() {
  const [open, setOpen] = useState(false)
  return <div className="min-h-screen bg-canvas">
    <aside className="fixed inset-y-0 left-0 z-40 hidden w-56 flex-col bg-navy-950 text-white lg:flex"><Navigation close={() => setOpen(false)} /></aside>
    {open && <div className="fixed inset-0 z-50 lg:hidden"><button className="absolute inset-0 bg-slate-950/40" aria-label="Close navigation" onClick={() => setOpen(false)} /><aside className="relative flex h-full w-64 flex-col bg-navy-950 text-white"><Navigation close={() => setOpen(false)} /><button onClick={() => setOpen(false)} className="absolute right-2.5 top-2.5 rounded-md p-2 text-slate-400 hover:bg-white/5" aria-label="Close navigation"><X size={18} /></button></aside></div>}
    <div className="lg:pl-56">
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b bg-white px-4 md:px-6">
        <div className="flex items-center gap-3"><button className="rounded-md border p-2 lg:hidden" onClick={() => setOpen(true)} aria-label="Open navigation"><Menu size={18} /></button><div><p className="text-[13px] font-semibold text-navy-900">Production operations</p><p className="hidden text-[11px] text-muted sm:block">Evidence and recovery state</p></div></div>
        <div className="flex items-center gap-3"><span className="hidden rounded-md border bg-slate-50 px-2.5 py-1.5 text-[11px] font-medium text-muted md:inline-flex">Environment: demo</span><button className="relative rounded-md border p-2 text-muted transition-colors duration-150 hover:bg-slate-50" aria-label="Notifications"><Bell size={16} /><span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-amber-600" /></button><span className="grid h-8 w-8 place-items-center rounded-full bg-navy-800 text-[11px] font-semibold text-white" title="On-call engineer">OE</span></div>
      </header>
      <main className="mx-auto max-w-[1320px] p-4 md:p-6"><Outlet /></main>
    </div>
  </div>
}
