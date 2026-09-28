"""Explain a historical recovery sequence with a deterministic baseline.

No LLM, risk authorization, memory writes, or tool execution occurs here.
Observed sequences support a hypothesis, not proof that an action caused recovery.
"""

from agents.remediation_memory import RemediationMemory
from schemas.incident import Incident
from schemas.investigation import InvestigationResult
from schemas.remediation import RemediationAction


class IncidentInvestigator:
    def __init__(self, memory: RemediationMemory):
        self.memory = memory

    def investigate(self, incident: Incident) -> InvestigationResult:
        analysis = self.memory.analyze(incident)
        result = InvestigationResult(
            incident_id=incident.incident_id, status="INSUFFICIENT_EVIDENCE",
            reasoning="No comparable verified recovery sequence was found; investigate manually.",
            historical_evidence=analysis.evidence, action_summary=analysis.actions,
        )
        # A candidate must be the fix immediately before a final verified retry.
        # One support vote per incident prevents repeated attempts inflating support.
        candidates = {}
        for evidence in analysis.evidence:
            if len(evidence.outcomes) < 2:
                continue
            fix, retry = evidence.outcomes[-2:]
            if (fix.verified and fix.result == "SUCCESS" and fix.reprocessing_result is None
                    and retry.verified and retry.result == "SUCCESS"
                    and retry.reprocessing_result == "SUCCESS" and fix.action != retry.action):
                candidates.setdefault(fix.action, []).append(evidence)
        # Contradictory attempts remain visible and prevent a confident suggestion.
        blocked = {item.action for item in analysis.actions if item.failed or item.partial or item.unverified}
        candidates = {action: records for action, records in candidates.items() if action not in blocked}
        if not candidates:
            return result
        ranking = sorted(candidates, key=lambda action: (-len(candidates[action]), action))
        if len(ranking) > 1 and len(candidates[ranking[0]]) == len(candidates[ranking[1]]):
            result.reasoning = "Historical recovery sequences support competing fixes equally; investigate manually."
            return result
        action = ranking[0]
        support = candidates[action]
        # Consider every comparable record, including records with unsuccessful fixes.
        causes = {item.root_cause for item in analysis.evidence}
        if None in causes or len(causes) != 1:
            result.reasoning = "Comparable incidents have missing or conflicting root causes; investigate manually."
            return result
        risks = {outcome.risk_level for item in analysis.evidence for outcome in item.outcomes
                 if outcome.action == action}
        risk = max(risks, key={"LOW": 0, "MEDIUM": 1, "HIGH": 2}.__getitem__)
        # Explicit heuristic: mean similarity, discounted for small sample counts.
        confidence = round(sum(item.similarity for item in support) / (len(support) + 1), 3)
        ids = ", ".join(item.incident_id for item in support)
        reason = (f"{action} was followed by verified successful reprocessing in {ids}. "
                  "Retry outcomes depend on their position in the sequence. "
                  "This is historical evidence, not proof of the current root cause. "
                  "Risk is copied conservatively from history; execution needs the decision layer.")
        result.status = "RECOMMENDATION_READY"
        result.likely_root_cause = next(iter(causes))
        result.reasoning = reason
        result.recommended_action = RemediationAction(
            action_name=action, description=f"Review {action} before reprocessing.",
            risk_level=risk, reason=reason, confidence=confidence,
        )
        return result
