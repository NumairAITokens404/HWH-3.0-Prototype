import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Layout } from './Layout'

function renderLayout(initialPath = '/') {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[initialPath]}><Layout /></MemoryRouter></QueryClientProvider>)
}

describe('dashboard header', () => {
  beforeEach(() => { cleanup(); localStorage.clear(); delete document.documentElement.dataset.theme; vi.stubGlobal('scrollTo', vi.fn()) })

  it('opens and dismisses the activity panel', async () => {
    const user = userEvent.setup()
    renderLayout()
    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(await screen.findByRole('dialog', { name: 'Notification center' })).toBeInTheDocument()
    expect(await screen.findByText(/approval.*waiting|no incidents or approvals need attention/i)).toBeInTheDocument()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Notification center' })).not.toBeInTheDocument()
  })

  it('highlights only the current navigation destination', async () => {
    const user = userEvent.setup()
    renderLayout('/memory')
    expect(screen.getByRole('link', { name: 'Memory' })).toHaveClass('nav-link-active')
    await user.click(screen.getByRole('link', { name: 'Ingest' }))
    expect(screen.getByRole('link', { name: 'Memory' })).not.toHaveClass('nav-link-active')
    expect(screen.getByRole('link', { name: 'Ingest' })).toHaveClass('nav-link-active')
    expect(window.scrollTo).toHaveBeenCalledWith(0, 0)
  })

  it('switches theme and remembers the choice', async () => {
    const user = userEvent.setup()
    const view = renderLayout()
    await user.click(screen.getByRole('button', { name: 'Switch to light mode' }))
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(localStorage.getItem('dashboard-theme-v2')).toBe('light')
    view.unmount()
    renderLayout()
    expect(screen.getByRole('button', { name: 'Switch to dark mode' })).toBeInTheDocument()
  })
})
