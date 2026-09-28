"""Deterministic metrics with explicit denominators and missing-data handling."""

from collections import Counter
import re
from statistics import mean


def token_f1(prediction: str | None, reference: str) -> float:
    predicted = Counter(re.findall(r"\w+", (prediction or "").casefold()))
    expected = Counter(re.findall(r"\w+", reference.casefold()))
    overlap = sum((predicted & expected).values())
    return 2 * overlap / (sum(predicted.values()) + sum(expected.values())) if predicted and expected else 0.0


def summarize(rows: list[dict]) -> dict:
    if not rows:
        raise ValueError("Cannot summarize an empty evaluation")
    proposals = [row for row in rows if row["proposed_action"] is not None]
    retrieved = [row for row in rows if row["retrieved_ids"]]
    latencies = [row["llm_latency_ms"] for row in rows if row["llm_latency_ms"] is not None]
    executed = [row for row in rows if row["tool_steps"]]
    return {
        "cases": len(rows),
        "raw_action_accuracy": mean(row["proposed_action"] == row["expected_action"] for row in rows),
        "accepted_action_accuracy": mean(row["accepted_action"] == row["expected_action"] for row in rows),
        "proposal_coverage": len(proposals) / len(rows),
        "accepted_coverage": mean(row["accepted_action"] is not None for row in rows),
        "repeated_failed_action_rate_among_proposals": mean(row["proposed_action"] in row["avoid_actions"] for row in proposals) if proposals else None,
        "root_cause_exact_match": mean((row["proposed_root_cause"] or "").strip().casefold() == row["expected_root_cause"].strip().casefold() for row in rows),
        "root_cause_token_f1": mean(token_f1(row["proposed_root_cause"], row["expected_root_cause"]) for row in rows),
        "retrieval_precision_when_nonempty": mean(len(set(row["retrieved_ids"]) & set(row["relevant_ids"])) / len(set(row["retrieved_ids"])) for row in retrieved) if retrieved else None,
        "retrieval_recall": mean(len(set(row["retrieved_ids"]) & set(row["relevant_ids"])) / len(set(row["relevant_ids"])) for row in rows),
        "fallback_count": sum(row["method"] == "deterministic_fallback" for row in rows),
        "mean_llm_latency_ms": mean(latencies) if latencies else None,
        "simulated_tool_calls_total": sum(row["tool_steps"] for row in rows),
        "mean_tool_steps_among_executed_cases": mean(row["tool_steps"] for row in executed) if executed else None,
        "simulated_recoveries": sum(row["workflow_status"] == "SUCCESS" for row in rows),
        "approval_pauses": sum(row["workflow_status"] == "HUMAN_APPROVAL_REQUIRED" for row in rows),
        "tool_steps_note": "Counts actual simulated remediation/retry calls. Approval-paused or abstained cases execute zero calls; this is not recovery-time savings.",
    }
