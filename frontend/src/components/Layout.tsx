import { useQuery } from '@tanstack/react-query'
import clsx from 'clsx'
import { Activity, Bell, CheckSquare, ChevronRight, Database, FlaskConical, Menu, Moon, ServerCog, Sun, Upload, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom'
import { api } from '../api'

const links = [
  { to: '/', label: 'Overview', icon: Activity, end: true },
  { to: '/incidents', label: 'Incidents', icon: ServerCog },
  { to: '/approvals', label: 'Approvals', icon: CheckSquare },
  { to: '/memory', label: 'Memory', icon: Database, end: true },
  { to: '/memory/upload', label: 'Ingest', icon: Upload },
  { to: '/evaluation', label: 'Evaluation', icon: FlaskConical },
]
type Theme = 'light' | 'dark'
function initialTheme(): Theme {
  const saved = localStorage.getItem('dashboard-theme-v2')
  return saved === 'light' || saved === 'dark' ? saved : 'dark'
}

function Navigation({ close, pendingApprovals }: { close: () => void; pendingApprovals: number }) {
  return <nav className="main-nav" aria-label="Primary navigation">{links.map(({ to, label, icon: Icon, end }) => <NavLink key={to} to={to} end={end} onClick={close} className={({ isActive }) => clsx('nav-link', isActive && 'nav-link-active')}><Icon size={16} strokeWidth={1.8} /><span>{label}</span>{to === '/approvals' && pendingApprovals > 0 && <span className="nav-count">{pendingApprovals}</span>}</NavLink>)}</nav>
}

export function Layout() {
  const { pathname } = useLocation()
  const [open, setOpen] = useState(false)
  const [notificationsOpen, setNotificationsOpen] = useState(false)
  const [theme, setTheme] = useState<Theme>(initialTheme)
  const notificationRef = useRef<HTMLDivElement>(null)
  const { data } = useQuery({ queryKey: ['overview'], queryFn: () => api.getOverview(), refetchInterval: 30000 })
  const pendingApprovals = data?.pendingApprovals ?? 0
  const active = data?.active ?? 0
  const attentionCount = pendingApprovals + active

  useEffect(() => { window.scrollTo(0, 0); setOpen(false); setNotificationsOpen(false) }, [pathname])
  useEffect(() => { document.documentElement.dataset.theme = theme; localStorage.setItem('dashboard-theme-v2', theme) }, [theme])
  useEffect(() => {
    if (!notificationsOpen) return
    function dismiss(event: MouseEvent) { if (!notificationRef.current?.contains(event.target as Node)) setNotificationsOpen(false) }
    function escape(event: KeyboardEvent) { if (event.key === 'Escape') setNotificationsOpen(false) }
    document.addEventListener('mousedown', dismiss); document.addEventListener('keydown', escape)
    return () => { document.removeEventListener('mousedown', dismiss); document.removeEventListener('keydown', escape) }
  }, [notificationsOpen])

  return <div className="app-shell min-h-screen bg-canvas">
    <header className="topbar"><div className="topbar-inner"><Link to="/" className="brand" aria-label="Adaptive Incident home"><span className="brand-mark" aria-hidden="true"><span /><span /><span /></span><span>adaptive<span className="brand-accent">/</span>incident</span></Link><div className="desktop-nav"><Navigation close={() => setOpen(false)} pendingApprovals={pendingApprovals} /></div><div className="top-actions"><button type="button" className="header-icon" aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'} title={theme === 'light' ? 'Dark mode' : 'Light mode'} onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}</button><div className="relative" ref={notificationRef}><button type="button" className="header-icon relative" aria-label="Notifications" aria-expanded={notificationsOpen} aria-controls="notification-center" onClick={() => setNotificationsOpen((value) => !value)}><Bell size={18} />{attentionCount > 0 && <span className="notification-count">{attentionCount > 9 ? '9+' : attentionCount}</span>}</button>{notificationsOpen && <div id="notification-center" role="dialog" aria-label="Notification center" className="notification-panel absolute right-0 top-12 z-40 w-[min(22rem,calc(100vw-2rem))] overflow-hidden"><div className="flex items-center justify-between border-b px-5 py-4"><div><p className="text-sm font-bold text-ink">Activity</p><p className="mt-0.5 text-xs text-muted">{attentionCount ? `${attentionCount} item${attentionCount === 1 ? '' : 's'} need attention` : 'All caught up'}</p></div><button type="button" className="header-icon !h-8 !w-8" onClick={() => setNotificationsOpen(false)} aria-label="Close notifications"><X size={15} /></button></div><div className="max-h-[min(26rem,60vh)] overflow-y-auto divide-y divide-line">{pendingApprovals > 0 && <Link to="/approvals" onClick={() => setNotificationsOpen(false)} className="notification-item"><span className="notification-symbol"><CheckSquare size={16} /></span><span className="min-w-0 flex-1"><strong>{pendingApprovals} approval{pendingApprovals === 1 ? '' : 's'} waiting</strong><small>Review proposed actions</small></span><ChevronRight size={15} className="text-faint" /></Link>}{active > 0 && <Link to="/incidents" onClick={() => setNotificationsOpen(false)} className="notification-item"><span className="notification-symbol"><ServerCog size={16} /></span><span className="min-w-0 flex-1"><strong>{active} active incident{active === 1 ? '' : 's'}</strong><small>Continue response work</small></span><ChevronRight size={15} className="text-faint" /></Link>}{attentionCount === 0 && <p className="px-5 py-6 text-center text-xs text-muted">No incidents or approvals need attention.</p>}</div><Link to="/incidents" onClick={() => setNotificationsOpen(false)} className="notification-footer">Open incident queue <ChevronRight size={15} /></Link></div>}</div><button className="header-icon mobile-menu-button" onClick={() => setOpen((value) => !value)} aria-label={open ? 'Close navigation' : 'Open navigation'}>{open ? <X size={19} /> : <Menu size={19} />}</button></div></div>{open && <div className="mobile-nav"><Navigation close={() => setOpen(false)} pendingApprovals={pendingApprovals} /></div>}</header>
    <main className="mx-auto max-w-[1320px] px-5 pb-16 pt-9 md:px-8 md:pt-14"><Outlet /></main>
  </div>
}
