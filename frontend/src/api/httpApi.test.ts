import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHttpApi } from './httpApi'

afterEach(() => vi.restoreAllMocks())

describe('HTTP API adapter', () => {
  it('requires approval for high severity even when the proposed action is low risk', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({
      incident: { incident_id: 'HELD-007', severity: 'HIGH', service: 'customer-service', environment: 'production', symptoms: [] },
      investigation: { recommended_action: { action_name: 'reset_customer_pin', risk_level: 'LOW', confidence: 0.8 }, historical_evidence: [], reasoning: 'Evidence', method: 'deterministic_history_baseline' },
    }), { status: 200 }))
    const item = await createHttpApi('http://localhost:8000').getIncident('HELD-007')
    expect(item.policy_status).toBe('HUMAN_APPROVAL_REQUIRED')
    expect(item.risk_level).toBe('LOW')
  })
  it('loads and filters incidents from FastAPI', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify([
      { incident_id: 'TEST-001', service: 'customer-service', severity: 'HIGH', symptoms: ['failed'], environment: 'production', error_code: 'PIN_STATE_INVALID', status: 'INVESTIGATING', occurred_at: '2026-09-28T00:00:00Z' },
    ]), { status: 200, headers: { 'Content-Type': 'application/json' } }))
    const api = createHttpApi('http://127.0.0.1:8000/')
    const rows = await api.getIncidents({ service: 'customer-service' })
    expect(rows).toHaveLength(1)
    expect(fetch).toHaveBeenCalledWith('http://127.0.0.1:8000/api/ui/incidents', undefined)
  })

  it('surfaces backend validation details', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(new Response(JSON.stringify({ detail: 'Invalid upload' }), {
      status: 422, headers: { 'Content-Type': 'application/json' },
    }))
    const [job] = await createHttpApi('http://localhost:8000').createUpload([
      new File(['bad'], 'bad.json', { type: 'application/json' }),
    ])
    expect(job.stage).toBe('failed')
    expect(job.error).toBe('Invalid upload')
  })
})
