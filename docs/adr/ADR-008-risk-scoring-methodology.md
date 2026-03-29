# ADR-008: Document Risk Scoring Methodology

## Status
Accepted (implemented)

## Date
2026-03-28

## Context

ContractLens assigns a risk score (0.0–1.0) and risk level (low/medium/high/critical) to each clause using GPT-4o-mini. It then aggregates these into a single document-level risk score. The current aggregation uses a simple average of clause scores.

### Problem: Simple Average Hides Real Risk

Profiling a real document comparison (v1: 30 clauses, v2: 33 clauses) exposed how the simple average misleads users:

| Metric | V1 | V2 | Change |
|---|---|---|---|
| Average risk score | 0.404 | 0.431 | +6.7% |
| Total risk (sum) | 12.11 | 14.22 | +17.4% |
| Median | 0.440 | 0.485 | +10.2% |
| Critical clauses | 1 | 0 | -1 |
| High risk clauses | 4 | 6 | +2 |
| Medium risk clauses | 12 | 16 | +4 |
| Low risk clauses | 13 | 11 | -2 |

V2 is clearly riskier - more high/medium clauses, higher total exposure, risk shifting upward across the distribution. But the UI showed "0.4 → 0.4, Unchanged" because:

1. **Averaging dilutes risk.** Adding low-risk clauses to a risky document lowers the average. A contract with 1 critical clause and 99 boilerplate clauses would score as "low risk".
2. **The trend threshold (0.05 absolute) is too coarse.** A 6.7% relative increase doesn't cross the 0.05 absolute threshold, so it's labeled "unchanged".
3. **Modified clause risk transitions are invisible.** A clause that went from low→high risk is only visible if you read every clause. The summary doesn't track this.
4. **All clauses weighted equally.** An indemnification clause and a notice clause contribute the same to the average, even though indemnification carries far more legal exposure.

### Industry Approaches

Research into how production legal tech and security systems handle this:

**CVSS (Common Vulnerability Scoring System)** - The security industry's standard for aggregating multiple vulnerability findings. The maximum finding drives the overall score. A system with 100 low vulns and 1 critical is rated "critical". Uses multi-factor scoring: exploitability × impact × scope.

**OWASP Risk Rating** - `Risk = Likelihood × Impact` with weighted factors per dimension. Supports tuning weights per business context. Aggregates using highest-risk or decay-weighted approach.

**Legal tech platforms (Sirion, LexCheck)** - Multi-layered architecture. Risk scored per clause type with severity weights. Document-level risk driven by highest-severity findings, not averages. Some use comparison against standard contract databases to benchmark what's "normal" for a given clause type.

**ContractEval benchmark (2025)** - 41 legal risk categories. Evaluates correctness and effectiveness as separate dimensions, acknowledging that a single number can't capture everything.

The common pattern: **maximum-driven scoring with weighted contributions, not simple averaging.**

## Decision

Replace the simple average with a multi-factor scoring model inspired by CVSS and OWASP, adapted for contract risk.

### 1. Document-Level Risk Score Formula

```
document_risk = (
    max_clause_score * 0.4          # Worst clause drives the score
  + top_n_weighted_avg * 0.35       # Top 5 riskiest clauses, severity-weighted
  + concentration_penalty * 0.25    # Penalizes many medium/high risk clauses
)
```

**Why these components:**

- **Max clause score (40%)**: A single critical indemnification clause makes the whole contract risky, regardless of how many safe clauses exist. This matches how lawyers actually evaluate contracts - they focus on the worst terms.
- **Top-N weighted average (35%)**: Looks at the 5 riskiest clauses, weighted by their clause type severity. Captures whether risk is concentrated in one clause or spread across several. Uses the existing `CLAUSE_TYPE_RISK_WEIGHTS` from `classification_service.py`.
- **Concentration penalty (25%)**: Scales with the proportion of clauses above medium risk (score > 0.4). A document where 80% of clauses are medium+ risk is worse than one where only 10% are, even if the max score is the same.

**Concentration penalty formula:**

```python
medium_plus_count = sum(1 for s in scores if s > 0.4)
concentration = medium_plus_count / total_clauses
penalty = min(concentration * 1.2, 1.0)  # Cap at 1.0
```

### 2. Risk Level Determination

Replace fixed-score thresholds with rules that account for distribution:

```python
if any clause is critical:
    level = "critical"
elif high_count >= 3 or (high_count >= 1 and document_risk > 0.55):
    level = "high"
elif medium_count >= total / 2 or document_risk > 0.4:
    level = "medium"
else:
    level = "low"
```

The current code already has this logic for individual documents. The change is aligning the comparison summary to use the same rules.

### 3. Trend Detection (Comparison)

Replace absolute threshold with relative change:

```python
relative_change = (new_score - old_score) / old_score if old_score > 0 else 0

if relative_change > 0.05:      # 5% relative increase
    trend = "increased"
elif relative_change < -0.05:    # 5% relative decrease
    trend = "decreased"
else:
    trend = "unchanged"
```

With the real data: `(0.431 - 0.404) / 0.404 = 0.067` → 6.7% increase → **"increased"**, not "unchanged".

### 4. Risk Transition Tracking (Comparison)

Track risk level changes on modified clauses, not just added/removed:

```python
@dataclass
class RiskSummary:
    # ... existing fields ...
    risk_escalations: int = 0      # Clauses that moved to a higher risk level
    risk_deescalations: int = 0    # Clauses that moved to a lower risk level
```

A clause going from `low` → `high` is a risk escalation. This gets surfaced in the UI alongside "X high risk clauses added".

**Risk level ordering for comparison:**

```python
RISK_LEVEL_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}
```

### 5. Clause Type Weighting in Aggregation

The codebase already defines `CLAUSE_TYPE_RISK_WEIGHTS` in `classification_service.py` (e.g., indemnification: 0.8, notice: 0.2). These weights are used when scoring individual clauses but **not** when aggregating to document level.

In the top-N weighted average:

```python
weighted_scores = [
    clause.risk_score * CLAUSE_TYPE_RISK_WEIGHTS.get(clause.clause_type, 0.3)
    for clause in top_n_clauses
]
top_n_weighted_avg = sum(weighted_scores) / sum(
    CLAUSE_TYPE_RISK_WEIGHTS.get(c.clause_type, 0.3) for c in top_n_clauses
)
```

This means a high-risk indemnification clause (weight 0.8) contributes more than a high-risk notice clause (weight 0.2).

## Edge Cases

| Scenario | Current behavior | New behavior |
|---|---|---|
| 1 critical + 99 low | avg = 0.17 → "low" | max-driven → "critical" |
| All clauses medium (0.45) | avg = 0.45 → "medium" | concentration penalty pushes to high end of medium |
| 0 clauses (empty document) | 0.0 | 0.0 (no change) |
| 1 clause only | avg = that clause | max = top_n = that clause (formula still works) |
| All clauses identical score | avg = that score | Same result - max and avg converge |
| V2 adds many low-risk clauses | avg drops → "decreased" | Max/top-N unchanged → correctly shows "unchanged" |
| Clause goes low→critical | Not tracked | Flagged as risk escalation |

## Implementation

### Files to modify

| File | Change |
|---|---|
| `backend/app/services/risk_scoring.py` | **New file** - document-level risk scoring functions |
| `backend/app/services/comparison_service.py` | Use new scoring for `_compute_risk_summary`, add transition tracking |
| `backend/app/api/documents.py` | Use new scoring for document analysis response |
| `backend/app/api/schemas.py` | Add `risk_escalations`, `risk_deescalations` to comparison schema |
| `backend/app/services/classification_service.py` | Move `CLAUSE_TYPE_RISK_WEIGHTS` to shared location or import from `risk_scoring.py` |

### Why a new file

The risk scoring logic is currently split between `classification_service.py` (per-document summary), `comparison_service.py` (comparison summary), and `documents.py` (API response). All three duplicate the averaging logic. A single `risk_scoring.py` with the formula gives one place to maintain and test.

### Migration

No database migration needed. Risk scores stored on clauses don't change. Only the aggregation formula changes. Document-level risk is computed at read time, not stored.

## Consequences

### Positive

- Document risk score reflects actual legal exposure, not diluted average
- Trend detection catches meaningful changes (6.7% increase is now visible)
- Risk transitions on modified clauses are surfaced
- Clause type severity is used end-to-end (scoring + aggregation)
- Single source of truth for risk calculation logic

### Negative

- Slightly more complex scoring - harder to explain "why is this 0.62?" to users
- Max-driven scoring is more conservative - documents will generally score higher than before
- Existing documents will show different risk scores after the change (no stored scores change, but displayed aggregation changes)

### Trade-offs accepted

- Using a fixed formula rather than a learned/tunable model (simplicity over personalization for now)
- Top-5 for the weighted average is a chosen constant - could be made relative to document size later
- Concentration penalty uses a linear scale - could use a sigmoid for smoother behavior at extremes

## Future Enhancements

1. **Multi-dimensional risk**: Separate scores for financial exposure, compliance risk, and operational risk - surfaced as a radar chart rather than a single number
2. **Benchmark comparison**: Score against a corpus of "standard" contracts to show how a document compares to market norms
3. **User-tunable weights**: Let legal teams adjust clause type weights based on their risk appetite
4. **Confidence-weighted scoring**: Use the classification confidence score to discount uncertain assessments
5. **Historical trending**: Track how a document's risk profile evolves across many versions, not just two

## References

- [CVSS v3.1 Specification](https://www.first.org/cvss/v3.1/specification-document)
- [OWASP Risk Rating Methodology](https://owasp.org/www-community/OWASP_Risk_Rating_Methodology)
- [ContractEval: Benchmarking LLMs for Clause-Level Legal Risk (2025)](https://arxiv.org/abs/2508.03080)
- [Sirion AI Contract Risk Framework](https://www.sirion.ai/library/contract-insights/ai-contract-risk-emerging-markets/)
- [Survey of Classification for Legal Contracts (2025)](https://link.springer.com/article/10.1007/s10462-025-11359-8)
