# ADR-011: Evaluation Framework — Measuring Classification Quality

## Status
Accepted (implemented — baseline: 96.6% type accuracy, 93.1% level accuracy)

## Date
2026-03-28

## Context

ContractLens classifies contract clauses using GPT-4o-mini and assigns risk scores. Currently there is no way to measure whether these classifications are correct. We're deploying an LLM classifier with zero measurement of accuracy.

### What we don't know

- **Clause type accuracy**: Is the model correctly distinguishing "indemnification" from "limitation_of_liability"?
- **Risk level accuracy**: When the model says "high risk", how often is it actually high risk?
- **Risk score calibration**: Do clauses scored 0.7 actually represent more risk than clauses scored 0.4?
- **Error rate**: What percentage of classifications are wrong?
- **Regression detection**: If we change the prompt, model, or chunking — did quality improve or degrade?
- **Domain coverage**: Are there clause types in real contracts that our 15-type taxonomy doesn't cover?

### Why this matters

Every improvement we make (ADR-008 risk scoring, ADR-009 structured outputs, ADR-010 better parsing) changes classification behavior. Without measurement, we can't tell if changes help or hurt. We're flying blind.

### Available Benchmarks

| Dataset | Size | Task | Relevance |
|---|---|---|---|
| **ContractEval** (2025) | 41 risk categories, commercial contracts | Clause-level risk identification | High — direct match to our task |
| **LegalBench** | 162 tasks across legal reasoning | Broad legal NLP evaluation | Medium — includes clause classification |
| **CUAD** | 13,101 labeled clauses from 510 contracts | 41 clause categories | High — largest labeled contract dataset |
| **ACORD** (2025) | Expert-annotated contract clauses | Clause retrieval and identification | High — expert labels |

## Decision

### 1. Build a Gold Standard Test Set

Create a human-labeled dataset from actual ContractLens documents:

**Phase 1 — Bootstrap from existing data (50 clauses):**
- Pull 50 classified clauses spanning all 15 types and 4 risk levels
- Manually review and correct labels
- Include boundary cases (clauses that could be multiple types)
- Store as `tests/evaluation/gold_standard.json`

**Phase 2 — Expand with external data (200+ clauses):**
- Sample from CUAD dataset (already labeled with 41 categories, map to our 15)
- Include ContractEval benchmark samples
- Target: 10-15 clauses per type, balanced across risk levels

**Format:**
```json
{
  "id": "gs-001",
  "text": "Provider shall indemnify, defend, and hold harmless Client...",
  "expected_clause_type": "indemnification",
  "expected_risk_level": "high",
  "expected_risk_score_range": [0.65, 0.85],
  "notes": "One-sided indemnification with no cap",
  "source": "manual_review"
}
```

### 2. Automated Evaluation Pipeline

A script that runs the gold standard through the classifier and reports accuracy:

```python
def evaluate_classifier(test_set: List[GoldStandard]) -> EvaluationReport:
    results = classify_all(test_set)

    return EvaluationReport(
        clause_type_accuracy=calculate_accuracy(results, "clause_type"),
        clause_type_f1=calculate_f1_per_class(results, "clause_type"),
        risk_level_accuracy=calculate_accuracy(results, "risk_level"),
        risk_level_confusion_matrix=build_confusion_matrix(results, "risk_level"),
        risk_score_mae=mean_absolute_error(results, "risk_score"),
        risk_score_correlation=spearman_correlation(results, "risk_score"),
        failures=count_failures(results),
        low_confidence_rate=count_below_threshold(results, 0.6),
    )
```

**Metrics:**

| Metric | What it measures | Target |
|---|---|---|
| Clause type accuracy | % of clauses with correct type | >85% |
| Clause type F1 (per class) | Precision/recall per type | >0.8 for common types |
| Risk level accuracy | % of clauses with correct level | >75% |
| Risk level confusion matrix | Which levels get confused | No critical↔low confusion |
| Risk score MAE | Average distance from expected score | <0.15 |
| Risk score Spearman correlation | Rank ordering quality | >0.7 |
| Failure rate | % of classifications that errored | <2% |
| Low confidence rate | % with confidence <0.6 | <15% |

### 3. Run on Every Change

Integrate evaluation into the development workflow:

- **Before prompt changes**: Run baseline evaluation, save results
- **After prompt changes**: Run again, compare metrics
- **Model changes**: Evaluate old model, new model, compare side-by-side
- **Chunking changes**: Evaluate with old chunks, new chunks

Store results in `tests/evaluation/results/` with timestamps for historical comparison.

### 4. Confusion Matrix Analysis

The most valuable output is the confusion matrix for clause types. It shows:
- Which types are commonly confused (indemnification vs limitation_of_liability)
- Which types have low recall (the model misses them)
- Whether "other" is a catch-all bucket hiding real classifications

Example:
```
                    Predicted →
Actual ↓           indem  lol  term  conf  pay  ip   other
indemnification     12    2    0     0     0    0    1
limit_of_liability   1   11    0     0     0    0    0
termination          0    0    9     0     0    0    1
confidentiality      0    0    0    10    0    0    0
payment_terms        0    0    0     0     8    0    2
```

This directly informs few-shot example selection (ADR-009) — add examples for the most confused pairs.

### 5. A/B Testing Framework for Model Changes

When evaluating a new model (e.g., GPT-4o-mini → GPT-5 mini):

```python
def compare_models(test_set, model_a, model_b):
    results_a = evaluate_with_model(test_set, model_a)
    results_b = evaluate_with_model(test_set, model_b)

    print(f"Clause type accuracy: {results_a.accuracy:.1%} vs {results_b.accuracy:.1%}")
    print(f"Risk level accuracy:  {results_a.risk_accuracy:.1%} vs {results_b.risk_accuracy:.1%}")
    print(f"Avg latency:          {results_a.avg_latency:.1f}s vs {results_b.avg_latency:.1f}s")
    print(f"Cost per clause:      ${results_a.cost:.4f} vs ${results_b.cost:.4f}")
```

## Implementation

### Phase 1: Gold standard + basic evaluation (1-2 days)
- Create `tests/evaluation/gold_standard.json` with 50 manually reviewed clauses
- Create `tests/evaluation/evaluate.py` script
- Report accuracy, F1, confusion matrix

### Phase 2: CUAD integration (1 day)
- Download CUAD dataset, map 41 categories to our 15
- Add 150+ external clauses to test set
- Re-run evaluation for broader coverage

### Phase 3: CI integration (optional)
- Run evaluation on prompt/model changes
- Store results with git history
- Alert if accuracy drops below thresholds

## Files to Create

| File | Purpose |
|---|---|
| `tests/evaluation/gold_standard.json` | Human-labeled test set |
| `tests/evaluation/evaluate.py` | Evaluation script |
| `tests/evaluation/results/` | Historical evaluation results |
| `tests/evaluation/cuad_mapping.json` | CUAD → ContractLens type mapping |

## Consequences

### Positive
- Can measure whether changes improve or degrade quality
- Confusion matrix identifies weakest classifications for targeted improvement
- Prevents silent regressions from model/prompt/chunking changes
- Provides evidence for model selection decisions (ADR-012)
- Builds confidence that the system's output is trustworthy

### Negative
- Manual labeling effort for Phase 1 (2-3 hours for 50 clauses)
- Evaluation runs cost API credits (~$0.02 per run with 50 clauses)
- Test set needs ongoing maintenance as clause types evolve

### Trade-offs
- Starting with 50 clauses rather than 500 — enough to detect major issues, not enough for statistical significance on rare types
- Manual review rather than crowdsourced labeling — higher quality, slower to scale
- Not implementing continuous evaluation in CI yet — run manually until the framework proves useful

## References
- [ContractEval: Benchmarking LLMs for Clause-Level Legal Risk](https://arxiv.org/abs/2508.03080)
- [CUAD: An Expert-Annotated NLP Dataset for Legal Contract Review](https://www.atticusprojectai.org/cuad)
- [LegalBench: A Collaboratively Built Benchmark for Legal Reasoning](https://huggingface.co/datasets/nguha/legalbench)
- [ACORD: Expert-Annotated Dataset for Legal Contract Clause Retrieval](https://aclanthology.org/2025.acl-long.1206.pdf)
