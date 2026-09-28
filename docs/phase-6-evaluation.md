# Phase 6: measured local evaluation

[Documentation index](README.md)

This document records the evaluation methodology introduced in Phase 6. Both the CLI and live dashboard now use all 12 held-out cases. The dashboard evaluates its current Hindsight namespace and publishes background progress, errors, and completed checkpoints. See [Architecture](architecture.md#measured-learning) for the current product path.

## Run

```powershell
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine rules --output reports/local-rules.json
.venv\Scripts\python.exe -m evaluation.evaluate_memory --engine ollama --output reports/local-ollama.json
```

The standalone CLI compares all 12 `TEST-*` and `HELD-*` cases with empty memory and seeded historical memory. Each case has a fresh isolated store. Evaluation answers are used only by the scorer and simulator, never in the model prompt. The dashboard evaluator runs the same case set against its live memory namespace.

## Metrics

| Metric | Definition |
| --- | --- |
| Raw action accuracy | Proposed action equals the fixture label, before the history guard |
| Accepted action accuracy | Final guarded recommendation equals the label |
| Proposal/accepted coverage | Fraction of all cases with a proposal/accepted recommendation |
| Repeated failed-action rate | Proposals matching a labeled action to avoid before remediation, divided by cases with proposals; null if none |
| Root-cause exact match / token F1 | Text-match proxies, not semantic correctness or causal proof |
| Retrieval precision | Relevant returned IDs divided by returned IDs, averaged over nonempty retrievals |
| Retrieval recall | Relevant returned IDs divided by labeled relevant IDs, averaged over all cases |
| Simulated tool calls | Actual remediation/retry invocations; approvals are never fabricated |
| Recovery / approval counts | Simulator successes and cases paused for human approval |
| Latency / fallback count | Local model call elapsed time and explicit fallback occurrences |

The report includes per-case results and unfamiliar-error, missing-error, and conflicting-history challenges. These challenges must end with insufficient evidence for execution. A model-only advisory hypothesis can still be visible.

## Interpretation

This is a small, intentionally repetitive synthetic demonstration. All six families appear in historical fixtures, so this is not an unseen-family generalization benchmark. The no-memory rules baseline abstains by design. The no-memory LLM may infer correct proposals from service and error names, but the guard cannot authorize them without history. Do not present differences in accepted coverage as an unbiased measurement of LLM improvement.

Two relevant production records are normally used per family; the third labeled record is staging. This explains retrieval recall of 2/3 in the rules baseline despite every selected record being relevant.

Zero tool calls can mean abstention or waiting for approval. Only cases that execute contribute to the mean executed-step metric. These counts do not establish recovery-time savings. Ollama evaluation exits nonzero if comparison rows use fallback, and includes the failure details in the saved report.

Generated local reports are ignored by Git. Share a reviewed report with its model, timestamp, dataset size, and these limitations.

## Archived Phase 6 local run

On 2026-09-28, before the held-out set expanded, `qwen3.5:9b` completed 12 comparison calls across the original 6 cases and three challenges with zero model fallbacks. This table is historical evidence, not the current dashboard result.

| Variant | Raw action accuracy | Accepted accuracy | Accepted coverage | Root-cause token F1 | Mean model latency |
| --- | ---: | ---: | ---: | ---: | ---: |
| Without memory | 1/6 | 0/6 | 0/6 | 0.037 | 1.84 s |
| With memory | 6/6 | 6/6 | 6/6 | 0.841 | 3.62 s |

The memory-backed run repeated none of the labeled failed actions. Two low-risk cases completed simulated recovery and four cases paused for approval. All unknown-error, missing-error, and conflicting-history challenges returned insufficient evidence. These results apply only to the synthetic fixtures and local configuration described above.
