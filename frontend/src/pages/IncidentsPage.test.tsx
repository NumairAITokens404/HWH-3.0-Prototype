import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { IncidentsPage } from './IncidentsPage'

describe('incidents page', () => {
  it('resets every incident filter', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <IncidentsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    const search = screen.getByRole('textbox', { name: /search incidents/i })
    const status = screen.getByRole('combobox', { name: /filter status/i })
    const severity = screen.getByRole('combobox', { name: /filter severity/i })
    const service = screen.getByRole('combobox', { name: /filter service/i })

    await user.type(search, 'queue')
    await user.selectOptions(status, 'RESOLVED')
    await user.selectOptions(severity, 'LOW')
    await user.selectOptions(service, 'queue-service')
    await user.click(screen.getByRole('button', { name: /reset filters/i }))

    expect(search).toHaveValue('')
    expect(status).toHaveValue('')
    expect(severity).toHaveValue('')
    expect(service).toHaveValue('')
  })
})
