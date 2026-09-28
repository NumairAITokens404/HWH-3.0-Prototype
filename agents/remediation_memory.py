"""Retrieve comparable evidence and count outcomes without LLM arithmetic."""

from memory.hindsight_client import HindsightClient
from memory.memory_retriever import retrieve_history
from schemas.incident import Incident
from schemas.investigation import ActionSummary, HistoricalEvidence, MemoryAnalysis


class RemediationMemory:
    def __init__(self, client: HindsightClient):
        self.client = client

    def analyze(self, incident: Incident) -> MemoryAnalysis:
        """Use the top five matches, retaining same-service/environment/error cases.

        Missing error codes or weak matches cannot support this initial baseline.
        All ordered outcomes remain visible, even when they are unverified.
        """
        evidence = []
        actions: dict[str, ActionSummary] = {}
        for match in retrieve_history(self.client, incident, limit=5):
            past = match.memory.incident
            if (match.score < 0.7 or not incident.error_code or not past.error_code
                    or past.service.casefold() != incident.service.casefold()
                    or past.environment.casefold() != incident.environment.casefold()
                    or past.error_code.casefold() != incident.error_code.casefold()):
                continue
            evidence.append(HistoricalEvidence(
                incident_id=past.incident_id, similarity=match.score,
                root_cause=match.memory.root_cause, outcomes=match.memory.outcomes,
            ))
            for outcome in match.memory.outcomes:
                summary = actions.setdefault(outcome.action, ActionSummary(action=outcome.action))
                if not outcome.verified:
                    summary.unverified += 1
                elif outcome.result == "SUCCESS":
                    summary.successful += 1
                elif outcome.result == "FAILED":
                    summary.failed += 1
                else:
                    summary.partial += 1
        return MemoryAnalysis(evidence=evidence, actions=sorted(actions.values(), key=lambda item: item.action))
