import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, expect, it, vi } from 'vitest'
import { api } from '../api'
import { EvaluationPage } from './EvaluationPage'

afterEach(() => { cleanup(); vi.restoreAllMocks() })

it('renders measured metrics and refreshes them on request', async () => {
  const data = await api.getEvaluation()
  vi.spyOn(api, 'getEvaluation').mockResolvedValue({ ...data, evaluationStatus: 'ready', metrics: [
    { name: 'Held-out action accuracy', withoutMemory: '0%', withMemory: '75%', improved: true, delta: 75 },
  ] })
  const refresh = vi.spyOn(api, 'refreshEvaluation').mockResolvedValue()
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EvaluationPage /></QueryClientProvider>)
  expect(await screen.findByText('75%')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Refresh metrics' }))
  expect(refresh).toHaveBeenCalledOnce()
})

it('renders long method and action names in separate wrapping cells', async () => {
  const data = await api.getEvaluation()
  vi.spyOn(api, 'getEvaluation').mockResolvedValue({ ...data, evaluationStatus: 'ready', cases: [{
    incidentId: 'TEST-003', expectedAction: 'rollback_connection_pool_change',
    recommendedAction: 'rollback_connection_pool_change', status: 'RECOMMENDATION_READY',
    retrievedIds: ['INC-107'], relevantIds: ['INC-107'], method: 'deterministic_history_baseline',
  }] })
  render(<QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}><EvaluationPage /></QueryClientProvider>)
  const method = await screen.findByText('deterministic history baseline')
  const expected = screen.getAllByText('rollback_connection_pool_change')[0]
  expect(method).toHaveClass('break-words')
  expect(expected).toHaveClass('break-words')
  expect(method.parentElement).not.toBe(expected.parentElement)
})
