# Phase 3: action policy and simulated remediation

[Documentation index](README.md) | [Next: recovery](phase-4-recovery.md)

**Status: implemented for local simulation.**

## Steps completed

1. Added typed approval, action-decision, scenario, and workflow contracts.
2. Added an immutable allowlist keyed by action, service, and error code.
3. Set authoritative LOW/MEDIUM/HIGH risks independently of the recommendation.
4. Bound reviewer decisions to a hash of the incident, recommendation, and policy rule.
5. Added the Auto Remediation Agent and an execution tool that rechecks authorization.
6. Modeled remediation results in an isolated simulation world.

## Policy

| Action | Risk |
| --- | --- |
| `reset_customer_pin` | LOW, synthetic scenario only |
| `reset_safe_cache` | LOW |
| `refresh_payment_routing` | MEDIUM |
| `quarantine_poison_message` | MEDIUM |
| `rollback_connection_pool_change` | HIGH |
| `switch_downstream_endpoint` | HIGH |

Unknown actions and incompatible incident contexts are blocked. Medium/high risk requires matching approval. Explicit denial stops execution, including when supplied for a low-risk action. The terminal demo pauses at approval; it does not grant approval automatically.

## Checks and boundaries

Workflow tests exercise waiting, approval, denial, mismatched approvals, cross-incident reuse, unknown actions, and a falsely low suggested risk. Reviewer identity is a trusted local input, not an authenticated permission system. No real customer, infrastructure, or security state is changed.
