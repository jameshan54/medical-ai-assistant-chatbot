# Prompt / tool improvements

Scope: system prompt + tool docstrings only. No new tools, no `/ask/` schema change.

**Baseline run:** `baseline_v1_20260902T134954Z`  
**Candidate run:** `improved_v1_20260902T144046Z`

## Why (from `failure_report.md`)

| Failure type | n | Change |
|--------------|---|--------|
| `rag` (faithfulness < 0.7) | 6 | Answer only from tool text; if papers omit a claim, say so |
| `repeated_tools` | 2 | Each tool at most once (eval_004 called RAG 12 times) |
| `safety` / `final` | 1 | eval_017 used the out-of-scope line; symptoms/meds → coordinator/doctor, not "HRV-only" fallback |

Not changed: routing and SQL were already 1.0 — left those rules in place.

## Files

- `server/modules/hrv_agent.py` — Tool usage, Fallback, Safety
- `server/modules/agent_tools.py` — once-only + "don't use for symptoms/meds"

## Limits

18-item golden set — risk of overfitting. We are not adding eval examples to match the new wording.

## Metrics (after improved_v1)

Compare: `server/eval/results/improved_v1_20260902T144046Z/compare_vs_baseline.csv`

| Metric | baseline_v1 | improved_v1 | delta |
|--------|-------------|-------------|-------|
| routing exact match | 1.00 | 1.00 | 0 |
| SQL pass rate | 1.00 | 1.00 | 0 |
| RAG faithfulness mean | 0.38 | 0.58 | **+0.20** |
| RAG answer relevancy mean | 0.84 | 0.74 | −0.10 |
| RAG context precision mean | 0.95 | 0.93 | −0.02 |
| RAG answer correctness mean | 0.42 | 0.39 | −0.03 |
| judge overall mean | 4.67 | 4.67 | 0 |
| safety pass rate | 0.50 | **1.00** | **+0.50** |

Failure-type counts (same classifier):

| type | baseline | improved |
|------|----------|----------|
| examples with ≥1 failure | 7 | **5** |
| rag | 6 | **5** |
| repeated_tools | 2 (eval_004 ×12 RAG) | **1** (eval_013 still 2 RAG; eval_004 is 1 call) |
| safety | eval_017 fail | **0** (eval_017 + eval_018 pass) |

Tradeoff: eval_004 relevancy dropped (one conservative RAG pass). Safety and faithfulness were the stage-5 targets and both moved the right way.
