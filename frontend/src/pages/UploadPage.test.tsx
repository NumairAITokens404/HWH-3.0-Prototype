import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { UploadPage } from './UploadPage'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

describe('memory upload page', () => {
  it('shows the complete ingestion architecture and queues the demo file', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const user = userEvent.setup()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={queryClient}><UploadPage /></QueryClientProvider>)
    expect(screen.getByText('From source file to reusable evidence')).toBeInTheDocument()
    expect(screen.getByText('Preserve evidence context')).toBeInTheDocument()
    expect(screen.getByText('Write to Hindsight')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /load selected dataset/i }))
    expect(await screen.findByText('demo-starter.json')).toBeInTheDocument()
  })
})
