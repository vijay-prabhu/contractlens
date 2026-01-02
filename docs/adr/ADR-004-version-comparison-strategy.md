# ADR-004: Version Comparison Strategy

## Status
Accepted

## Date
2024-12-31

## Context

ContractLens needs to compare different versions of contracts to help users understand what changed between revisions. This is critical for:
- Tracking negotiation changes (what did the other party modify?)
- Compliance review (what terms changed from the approved template?)
- Risk assessment (did risk increase or decrease between versions?)

### Key Challenges

1. **Text changes vs. Semantic changes**: A clause might be reworded without changing its meaning, or slightly modified with significant legal implications
2. **Clause matching**: How do we know if clause A in version 1 corresponds to clause B in version 2?
3. **Risk tracking**: How do we quantify whether changes made the contract riskier?

## Decision

Implement a **hybrid comparison approach** combining text-based diff with semantic similarity matching.

### 1. Text-Based Diff (difflib)

Use Python's `difflib` for character-level and line-level differences:

```python
import difflib

def compute_text_diff(text1: str, text2: str) -> list[dict]:
    differ = difflib.unified_diff(
        text1.splitlines(keepends=True),
        text2.splitlines(keepends=True),
        lineterm=""
    )
    return list(differ)
```

**Purpose**: Shows exact textual changes (additions, deletions, modifications)
**Use case**: Legal review where exact wording matters

### 2. Semantic Clause Matching (Embeddings)

Use cosine similarity between clause embeddings to match clauses across versions:

```python
def match_clauses(clauses_v1: list, clauses_v2: list) -> list[ClauseMatch]:
    matches = []
    for c1 in clauses_v1:
        best_match = None
        best_similarity = 0
        for c2 in clauses_v2:
            similarity = cosine_similarity(c1.embedding, c2.embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = c2

        if best_similarity >= SAME_THRESHOLD:
            matches.append(ClauseMatch(c1, best_match, "unchanged"))
        elif best_similarity >= MODIFIED_THRESHOLD:
            matches.append(ClauseMatch(c1, best_match, "modified"))
        else:
            matches.append(ClauseMatch(c1, None, "removed"))

    # Find added clauses (in v2 but not matched to v1)
    matched_v2_ids = {m.v2_clause.id for m in matches if m.v2_clause}
    for c2 in clauses_v2:
        if c2.id not in matched_v2_ids:
            matches.append(ClauseMatch(None, c2, "added"))

    return matches
```

### 3. Similarity Thresholds

After experimentation with contract clauses, we settled on:

| Threshold | Value | Meaning |
|-----------|-------|---------|
| `SAME_THRESHOLD` | 0.85 | Clauses are semantically identical |
| `MODIFIED_THRESHOLD` | 0.60 | Clauses are related but modified |
| Below 0.60 | - | Clauses are unrelated (added/removed) |

**Rationale**:
- **0.85**: High enough to catch only truly equivalent clauses, even if minor rewording occurred
- **0.60**: Low enough to catch substantial modifications, high enough to avoid false matches between unrelated clauses
- Thresholds determined empirically with sample contracts

### 4. Change Categories

Each clause is categorized as:

| Category | Definition | UI Treatment |
|----------|------------|--------------|
| `unchanged` | similarity ≥ 0.85 | Gray/muted |
| `modified` | 0.60 ≤ similarity < 0.85 | Yellow highlight |
| `added` | In v2, no match in v1 | Green highlight |
| `removed` | In v1, no match in v2 | Red highlight |

### 5. Risk Delta Calculation

Compare aggregate risk between versions:

```python
def calculate_risk_delta(v1_clauses: list, v2_clauses: list) -> RiskDelta:
    v1_risk = sum(c.risk_score for c in v1_clauses) / len(v1_clauses)
    v2_risk = sum(c.risk_score for c in v2_clauses) / len(v2_clauses)

    delta = v2_risk - v1_risk

    return RiskDelta(
        v1_score=v1_risk,
        v2_score=v2_risk,
        delta=delta,
        trend="increased" if delta > 0.05 else "decreased" if delta < -0.05 else "unchanged",
        critical_added=count_by_level(added_clauses, "critical"),
        critical_removed=count_by_level(removed_clauses, "critical"),
        high_risk_changes=count_by_level(modified_clauses, "high")
    )
```

**Risk trend thresholds**:
- `increased`: delta > 0.05 (5% increase in average risk)
- `decreased`: delta < -0.05 (5% decrease)
- `unchanged`: -0.05 ≤ delta ≤ 0.05

## API Response Structure

```json
{
  "text_diff": {
    "additions": 12,
    "deletions": 5,
    "diff_lines": ["+Added text", "-Removed text", "..."]
  },
  "clause_changes": [
    {
      "change_type": "modified",
      "v1_clause": { "id": "...", "text": "...", "risk_level": "medium" },
      "v2_clause": { "id": "...", "text": "...", "risk_level": "high" },
      "similarity": 0.72
    }
  ],
  "risk_summary": {
    "v1_average_risk": 0.45,
    "v2_average_risk": 0.52,
    "trend": "increased",
    "critical_clauses_added": 1,
    "high_risk_modifications": 2
  }
}
```

## Consequences

### Positive

- **Comprehensive analysis**: Catches both textual and semantic changes
- **Actionable insights**: Clear categorization helps users focus on important changes
- **Risk awareness**: Quantified risk delta highlights concerning modifications
- **Performant**: Embeddings are pre-computed during document processing

### Negative

- **Threshold sensitivity**: Fixed thresholds may not work for all document types
- **Embedding limitations**: Very short clauses may have less reliable embeddings
- **No clause splitting detection**: If one clause is split into two, detection is imperfect

### Trade-offs Accepted

- Using fixed thresholds rather than learning user preferences (simplicity over personalization)
- Greedy matching algorithm rather than optimal bipartite matching (performance over perfection)

## Alternatives Considered

### 1. Pure Text Diff (difflib only)

**Pros**: Simple, no AI dependency
**Cons**: Can't detect semantic equivalence, noisy with reformatting
**Decision**: Rejected as primary method; kept for supplementary detail

### 2. LLM-Based Comparison

**Pros**: Could understand nuanced legal implications
**Cons**: Expensive ($0.10+ per comparison), slow, non-deterministic
**Decision**: Rejected for MVP; could add as "deep analysis" feature later

### 3. Edit Distance (Levenshtein)

**Pros**: Fast, well-understood
**Cons**: Character-level, misses semantic similarity
**Decision**: Rejected; embeddings provide semantic awareness

### 4. Document-Level Comparison Only

**Pros**: Simpler implementation
**Cons**: Loses clause-level granularity, less actionable
**Decision**: Rejected; clause-level is essential for legal review

## Implementation Notes

- Embeddings are generated during document processing (not at comparison time)
- Clause matching is O(n×m) where n and m are clause counts; acceptable for contracts (<100 clauses)
- For large documents, could optimize with approximate nearest neighbor search

## Future Enhancements

1. **User-adjustable thresholds**: Let power users tune sensitivity
2. **Clause type weighting**: Prioritize changes in high-risk clause types
3. **Change explanation**: Use LLM to summarize what changed in plain language
4. **Template comparison**: Compare against approved template, not just previous version

## References

- [difflib documentation](https://docs.python.org/3/library/difflib.html)
- [Cosine Similarity for Text](https://www.sciencedirect.com/topics/computer-science/cosine-similarity)
- [Semantic Textual Similarity](https://paperswithcode.com/task/semantic-textual-similarity)
