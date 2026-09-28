import { describe, expect, it } from 'vitest'
import { mockApi } from './mockApi'

describe('mock API adapter', () => {
  it('retrieves complete successful and failed remediation evidence', async () => {
    const workspace = await mockApi.getIncident('TEST-001')
    expect(workspace.evidence).toHaveLength(2)
    expect(workspace.evidence[0].outcomes.map((item) => item.result)).toEqual(['FAILED', 'SUCCESS', 'SUCCESS'])
    expect(workspace.failed_actions_avoided).toContain('reprocess_transaction')
  })

  it('rejects unsupported upload formats', async () => {
    const [job] = await mockApi.createUpload([new File(['text'], 'postmortem.txt', { type: 'text/plain' })])
    expect(job.stage).toBe('failed')
    expect(job.error).toMatch(/JSON/)
  })
})
