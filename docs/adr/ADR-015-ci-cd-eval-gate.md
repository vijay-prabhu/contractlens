# ADR-015: CI/CD Evaluation Gate

## Status
Proposed

## Date
2026-03-28

## Context

ContractLens has an evaluation framework (ADR-011) that measures classification accuracy against a 29-clause gold standard. Currently this runs manually. Changes to prompts, models, chunking, or pipeline logic can silently degrade classification quality.

### Industry Standard

Production LLM applications in 2026 run automated eval suites on every PR that touches AI-related code. The pipeline fails if quality metrics drop below thresholds — exactly like unit tests gate code changes.

### Current Baseline (2026-03-28)

| Metric | Value | Minimum Threshold |
|---|---|---|
| Clause type accuracy | 96.6% | 90% |
| Risk level accuracy | 93.1% | 75% |
| Score in range | 96.6% | 85% |
| Failure rate | 0% | <5% |

## Decision

Add a GitHub Actions workflow that runs the evaluation framework on PRs that modify AI-related files.

### Trigger Conditions

Run the eval when any of these paths change:
```yaml
paths:
  - 'backend/app/services/classification_service.py'
  - 'backend/app/services/extraction_service.py'
  - 'backend/app/services/docling_extraction_service.py'
  - 'backend/app/services/chunking_service.py'
  - 'backend/app/services/section_chunking_service.py'
  - 'backend/app/services/embedding_service.py'
  - 'backend/app/services/risk_scoring.py'
  - 'backend/app/workers/document_processor.py'
  - 'tests/evaluation/**'
```

### Quality Gates

```yaml
# Fail the build if any threshold is breached
- name: Check quality gates
  run: |
    TYPE_ACC=$(jq '.type_accuracy' results.json)
    LEVEL_ACC=$(jq '.level_accuracy' results.json)
    FAIL_RATE=$(jq '.failure_rate' results.json)

    if (( $(echo "$TYPE_ACC < 0.90" | bc -l) )); then
      echo "FAIL: Type accuracy $TYPE_ACC < 0.90"
      exit 1
    fi
    if (( $(echo "$LEVEL_ACC < 0.75" | bc -l) )); then
      echo "FAIL: Level accuracy $LEVEL_ACC < 0.75"
      exit 1
    fi
```

### PR Comment

Post evaluation results as a PR comment for easy review:

```
## Classification Evaluation Results

| Metric | Value | Threshold | Status |
|---|---|---|---|
| Type accuracy | 96.6% | >90% | PASS |
| Risk level accuracy | 93.1% | >75% | PASS |
| Score in range | 96.6% | >85% | PASS |
| Failure rate | 0% | <5% | PASS |

1 misclassification: gs-024 (dispute_resolution → governing_law)
```

### Cost and Time

Each eval run classifies 29 clauses via OpenAI API:
- Cost: ~$0.02 per run (29 × GPT-4o-mini calls)
- Time: ~70 seconds (sequential, could parallelize)
- Runs only on AI-related file changes, not every PR

### Required Secrets

```yaml
env:
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Implementation

### Files to Create

| File | Purpose |
|---|---|
| `.github/workflows/eval.yml` | GitHub Actions workflow |
| `tests/evaluation/check_gates.py` | Script to check thresholds and output results |

### Workflow Structure

```yaml
name: Classification Eval
on:
  pull_request:
    paths: [list of AI-related files]

jobs:
  evaluate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install dependencies
        run: cd backend && pip install poetry && poetry install
      - name: Run evaluation
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: cd backend && poetry run python ../tests/evaluation/evaluate.py --save
      - name: Check quality gates
        run: python tests/evaluation/check_gates.py
      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: # Post results as PR comment
```

## Consequences

### Positive
- Prompt/model changes can't silently degrade quality
- Reviewers see accuracy impact directly on the PR
- Historical eval results tracked in git
- Cheap to run ($0.02 per evaluation)

### Negative
- Adds ~70 seconds to PR checks (only on AI-related changes)
- Requires OPENAI_API_KEY in GitHub Secrets
- Gold standard needs maintenance as taxonomy evolves

## References
- [Arize: How to Add LLM Evaluations to CI/CD Pipelines](https://arize.com/blog/how-to-add-llm-evaluations-to-ci-cd-pipelines/)
- [Deepchecks: LLM Evaluation in CI/CD Pipelines](https://deepchecks.com/llm-evaluation/ci-cd-pipelines/)
- [Evidently AI: LLM Testing in CI/CD with GitHub Actions](https://www.evidentlyai.com/blog/llm-unit-testing-ci-cd-github-actions)
