import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api'
import { IncidentPage } from './IncidentPage'

vi.mock('../api', async () => {
  const { mockApi } = await import('../api/mockApi')
  return { api: mockApi }
})

describe('incident review flow', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks() })

  it('offers review for a High severity incident with a low risk action', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={['/incidents/HELD-007']}><Routes><Route path="/incidents/:id" element={<IncidentPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    await user.click(await screen.findByRole('button', { name: /review action/i }))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /run simulated workflow/i })).not.toBeInTheDocument()
  })

  it('keeps a retry control when recall has no recommended action', async () => {
    const initial = await api.getIncident('TEST-003')
    vi.spyOn(api, 'getIncident').mockResolvedValue({ ...initial, evidence: [], recommended_action: 'No action recommended', workflow_status: 'INSUFFICIENT_EVIDENCE', policy_status: 'BLOCKED' })
    const run = vi.spyOn(api, 'runWorkflow').mockRejectedValue(new Error('Hindsight is offline'))
    const user = userEvent.setup()
    render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><MemoryRouter initialEntries={['/incidents/TEST-003']}><Routes><Route path="/incidents/:id" element={<IncidentPage />} /></Routes></MemoryRouter></QueryClientProvider>)
    await user.click(await screen.findByRole('button', { name: /review action/i }))
    expect(run).toHaveBeenCalledWith('TEST-003')
    expect(await screen.findByRole('alert')).toHaveTextContent('Hindsight is offline')
    expect(screen.getByRole('button', { name: /review action/i })).toBeEnabled()
  })
  it('opens a pending review and displays the approved outcome', async () => {
    const initial = await api.getIncident('TEST-003')
    vi.spyOn(api, 'getIncident').mockResolvedValueOnce({ ...initial, workflow_status: 'INVESTIGATING' })
    const runWorkflow = vi.spyOn(api, 'runWorkflow')
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={['/incidents/TEST-003']}><Routes><Route path="/incidents/:id" element={<IncidentPage />} /></Routes></MemoryRouter></QueryClientProvider>)

    await user.click(await screen.findByRole('button', { name: /review action/i }))

    expect(await screen.findByRole('dialog', { name: /authorize simulated attempt/i })).toBeInTheDocument()
    expect(runWorkflow).toHaveBeenCalledWith('TEST-003')
    await user.type(screen.getByPlaceholderText('Enter your name'), 'Reviewer')
    vi.spyOn(api, 'submitApproval').mockRejectedValueOnce(new Error('Approval service unavailable'))
    await user.click(screen.getByRole('button', { name: /approve simulated action/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Approval service unavailable')
    vi.restoreAllMocks()
    await user.click(screen.getByRole('button', { name: /approve simulated action/i }))
    expect(await screen.findByText('Observed state')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
    expect(screen.queryByRole('button', { name: /review action/i })).not.toBeInTheDocument()
  })
})
