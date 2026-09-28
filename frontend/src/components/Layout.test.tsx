import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { Layout } from './Layout'

describe('notification center', () => {
  it('opens from the bell and shows live session status', async () => {
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><MemoryRouter><Layout /></MemoryRouter></QueryClientProvider>)

    await user.click(screen.getByRole('button', { name: 'Notifications' }))

    expect(await screen.findByRole('dialog', { name: 'Notification center' })).toBeInTheDocument()
    expect(await screen.findByText(/learning score/i)).toBeInTheDocument()
  })
})
