import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { UploadPage } from './UploadPage'

describe('memory upload page', () => {
  it('shows the complete ingestion architecture and queues the demo file', async () => {
    const user = userEvent.setup()
    render(<UploadPage />)
    expect(screen.getByText('From source file to reusable evidence')).toBeInTheDocument()
    expect(screen.getByText('Complete incident records')).toBeInTheDocument()
    expect(screen.getByText('Failed remediation memory')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /load demo dataset/i }))
    expect(await screen.findByText('remediation_history.json')).toBeInTheDocument()
  })
})
