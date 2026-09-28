"""Model reasoning validated against historical support before workflow execution."""

from time import perf_counter
from agents.incident_investigator import IncidentInvestigator
from agents.remediation_memory import RemediationMemory
from llm.client import LLMError, StructuredLLM
from llm.prompts import investigation_messages
from schemas.incident import Incident
from schemas.investigation import InvestigationResult


class LLMInvestigator:
    def __init__(self, memory: RemediationMemory, llm: StructuredLLM):
        self.memory = memory
        self.llm = llm

    def investigate(self, incident: Incident) -> InvestigationResult:
        analysis = self.memory.analyze(incident)
        baseline = IncidentInvestigator(self.memory).investigate(incident, analysis)
        started = perf_counter()
        baseline.model_name = self.llm.model
        try:
            proposal = self.llm.generate(investigation_messages(incident, analysis))
        except LLMError as exc:
            baseline.method = "deterministic_fallback"
            baseline.fallback_reason = str(exc)
            baseline.llm_latency_ms = round((perf_counter() - started) * 1000, 3)
            return baseline
        elapsed = round((perf_counter() - started) * 1000, 3)
        evidence_ids = {
            evidence_id
            for item in analysis.evidence
            for evidence_id in (item.incident_id, *(outcome.outcome_id for outcome in item.outcomes))
        }
        if not set(proposal.evidence_ids) <= evidence_ids:
            baseline.method = "deterministic_fallback"
            baseline.fallback_reason = "unknown_evidence_reference"
            baseline.model_proposal = proposal
            baseline.llm_latency_ms = elapsed
            return baseline
        result = baseline.model_copy(deep=True)
        result.method = "llm_grounded"
        result.model_proposal = proposal
        result.llm_latency_ms = elapsed
        if proposal.status == "ABSTAIN":
            if baseline.recommended_action is not None:
                baseline.method = "deterministic_fallback"
                baseline.fallback_reason = "model_abstained_despite_verified_history"
                baseline.model_proposal = proposal
                baseline.llm_latency_ms = elapsed
                return baseline
            result.status = "INSUFFICIENT_EVIDENCE"
            result.recommended_action = None
            result.likely_root_cause = None
            result.reasoning = proposal.explanation
            return result
        # Execution eligibility requires a supported sequence and an explicit citation.
        # Model knowledge alone may produce an advisory proposal, not an executable fix.
        if (baseline.recommended_action is None or not proposal.evidence_ids
                or proposal.action_name != baseline.recommended_action.action_name):
            if baseline.recommended_action is not None:
                baseline.method = "deterministic_fallback"
                baseline.fallback_reason = "model_proposal_not_supported_by_history"
                baseline.model_proposal = proposal
                baseline.llm_latency_ms = elapsed
                return baseline
            result.status = "INSUFFICIENT_EVIDENCE"
            result.recommended_action = None
            result.likely_root_cause = None
            result.reasoning = "Model proposal requires manual review: historical support is insufficient or conflicting. " + proposal.explanation
            return result
        supporting_ids: set[str] = set()
        for item in analysis.evidence:
            if (len(item.outcomes) >= 2 and item.outcomes[-2].action == proposal.action_name
                    and item.outcomes[-2].verified and item.outcomes[-2].result == "SUCCESS"
                    and item.outcomes[-1].verified and item.outcomes[-1].result == "SUCCESS"
                    and item.outcomes[-1].reprocessing_result == "SUCCESS"):
                supporting_ids.update({
                    item.incident_id,
                    item.outcomes[-2].outcome_id,
                    item.outcomes[-1].outcome_id,
                })
        if not set(proposal.evidence_ids) & supporting_ids:
            baseline.method = "deterministic_fallback"
            baseline.fallback_reason = "citations_do_not_support_recovery_sequence"
            baseline.model_proposal = proposal
            baseline.llm_latency_ms = elapsed
            return baseline
        result.reasoning = proposal.explanation
        result.recommended_action.reason = proposal.explanation
        # Keep canonical historical cause, risk, and deterministic confidence. Raw
        # model hypothesis/confidence remain separately visible in model_proposal.
        return result
