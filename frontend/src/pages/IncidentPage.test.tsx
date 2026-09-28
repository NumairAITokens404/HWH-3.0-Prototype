import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { IncidentPage } from './IncidentPage'

vi.mock('../api', async () => {
  const { mockApi } = await import('../api/mockApi')
  return { api: mockApi }
})

describe('incident review flow', () => {
  it('starts the workflow before opening an approval review', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={['/incidents/TEST-003']}><Routes><Route path="/incidents/:id" element={<IncidentPage />} /></Routes></MemoryRouter></QueryClientProvider>)

    await user.click(await screen.findByRole('button', { name: /review action/i }))

    expect(await screen.findByRole('dialog', { name: /authorize simulated attempt/i })).toBeInTheDocument()
  })
})
