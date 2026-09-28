"""Deterministic allowlist for synthetic actions; never trust suggested risk."""

from hashlib import sha256
import json
from types import MappingProxyType

from schemas.incident import Incident
from schemas.remediation import RemediationAction
from schemas.workflow import ActionDecision, Approval

# Action -> (service, error code, policy risk). These rules authorize mocks only.
ACTION_POLICY = MappingProxyType({
    "reset_customer_pin": ("customer-service", "PIN_STATE_INVALID", "LOW"),
    "refresh_payment_routing": ("payment-service", "PAYMENT_ROUTE_STALE", "MEDIUM"),
    "rollback_connection_pool_change": ("database-service", "DB_POOL_EXHAUSTED", "HIGH"),
    "quarantine_poison_message": ("queue-service", "QUEUE_POISON_MESSAGE", "MEDIUM"),
    "reset_safe_cache": ("catalog-service", "CACHE_VERSION_MISMATCH", "LOW"),
    "switch_downstream_endpoint": ("fulfillment-service", "DOWNSTREAM_TIMEOUT", "HIGH"),
})


def classify_action(incident: Incident, action: RemediationAction, approval: Approval | None = None) -> ActionDecision:
    rule = ACTION_POLICY.get(action.action_name)
    risk = rule[2] if rule else "HIGH"
    # Bind approval to the full incident, proposed action, and authoritative policy.
    payload = {"incident": incident.model_dump(), "action": action.model_dump(), "policy": rule,
               "approval_policy": "severity-and-action-v2"}
    request_id = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    decision = ActionDecision(status="BLOCKED", action_name=action.action_name,
                              risk_level=risk, request_id=request_id, reason="Unknown action or incompatible incident context.")
    if rule is None or (incident.service.casefold(), (incident.error_code or "").casefold()) != (rule[0], rule[1].casefold()):
        return decision
    if approval is not None:
        if approval.request_id != request_id:
            decision.reason = "Approval does not match this incident and recommendation."
            return decision
        if not approval.approved:
            decision.status = "DENIED"
            decision.reason = "Reviewer denied this action."
            return decision
    if (risk != "LOW" or incident.severity in {"HIGH", "CRITICAL"}) and approval is None:
        decision.status = "HUMAN_APPROVAL_REQUIRED"
        decision.reason = ("Policy requires explicit approval for High/Critical incidents "
                           "and medium/high risk actions.")
    else:
        decision.status = "ALLOWED"
        decision.reason = "Allowed by the local simulation policy."
    return decision
