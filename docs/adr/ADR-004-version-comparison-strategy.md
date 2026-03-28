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
- **Chunk-level granularity mismatch**: See [Addendum — Findings from Real-World Testing](#addendum--findings-from-real-world-testing) below

### Trade-offs Accepted

- Using fixed thresholds rather than learning user preferences (simplicity over personalization)
- Greedy matching algorithm rather than optimal bipartite matching (performance over perfection)
- Comparing at chunk level rather than section level (reuse of existing chunking pipeline over purpose-built section parser)

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

1. **Section-aware comparison** (Priority — see Addendum): Compare at logical section level, not chunk level
2. **User-adjustable thresholds**: Let power users tune sensitivity
3. **Clause type weighting**: Prioritize changes in high-risk clause types
4. **Change explanation**: Use LLM to summarize what changed in plain language
5. **Template comparison**: Compare against approved template, not just previous version

## References

- [difflib documentation](https://docs.python.org/3/library/difflib.html)
- [Cosine Similarity for Text](https://www.sciencedirect.com/topics/computer-science/cosine-similarity)
- [Semantic Textual Similarity](https://paperswithcode.com/task/semantic-textual-similarity)

---

## Addendum — Findings from Real-World Testing

### Problem: Chunk-Level Comparison Produces Misleading Results

The ADR describes "clause matching" but the implementation actually compares **chunks** (800-character text fragments from the chunking service), not logical contract sections. This was not a deliberate design choice but rather an implicit consequence of reusing the same chunking pipeline for both embedding generation and comparison.

Real-world testing with a 14-section contract (v1 vs v2 with 4 modified, 2 removed, 2 added, 6 unchanged sections) revealed significant discrepancies between expected and actual comparison results.

### Test Results

**Expected** (section-level):

| Change Type | Count |
|-------------|-------|
| Added | 2 (Data Protection, Audit Rights) |
| Removed | 2 (Non-Compete, Force Majeure) |
| Modified | 4 (Indemnification, Limitation of Liability, Confidentiality, Payment) |
| Unchanged | 6 (IP, Termination, Warranty, Representations, Governing Law, Assignment, Notice, Amendment) |
| **Total** | **14** |

**Actual** (chunk-level):

| Change Type | Count |
|-------------|-------|
| Added | 6 |
| Removed | 5 |
| Modified | 21 |
| Unchanged | 4 |
| **Total** | **36** |

### Root Causes Identified

#### 1. Section Number Shifting Creates False Modifications

Removing a section (e.g., Non-Compete was Section 4 in v1) causes all subsequent sections to renumber. "Section 6. CONFIDENTIALITY" becomes "Section 5. CONFIDENTIALITY". Since the "Section N." prefix is part of the chunk text, the embeddings differ even though the legal content is identical.

**Example**: Confidentiality was unchanged but showed as "Modified, 97% similar" purely because of the section number change.

#### 2. Chunk Boundary Drift

The chunker splits at ~800 characters with 150-character overlap. When sections are added or removed, the entire document's chunk boundaries shift. The same text ends up split at different positions in v1 vs v2, creating chunks with different content even from identical sections.

**Example**: IP Rights (identical in both versions) appeared as two "Modified" entries at 94% and 82% similarity because the chunks split at different character positions.

#### 3. Cross-Section Mismatching

The greedy matching algorithm can match chunks from different sections if they share enough legal terminology. When a section is removed and the next section takes its number, chunks get incorrectly paired.

**Example**: v1 Non-Compete (Section 4) was matched to v2 Termination (Section 4) at 69% similarity because both share "Section 4." prefix and general contractual language. This was classified as "Modified" when it should have been "Removed" (Non-Compete) and "Unchanged" (Termination).

#### 4. Mid-Sentence Chunks Lose Classification Context

When a chunk starts mid-sentence (due to chunk boundary splitting), GPT-4o-mini cannot reliably identify the clause type. The tail chunk of the Non-Compete section was classified as "other" instead of "non_compete".

### What Worked Correctly

Despite the chunk-level issues, the core semantic comparison logic worked well:

| Finding | Evidence |
|---------|----------|
| Indemnification cap change detected | critical → medium risk, 89% similarity, correctly identified the $5M cap addition |
| Force Majeure removal detected | Both chunks correctly marked as "Removed" |
| Data Protection addition detected | All chunks correctly marked as "Added" |
| Audit Rights addition detected | Both chunks correctly marked as "Added" |
| Payment terms change detected | Correctly identified Net-60 → Net-120 modification |
| Confidentiality duration change detected | Caught the 5-year → 3-year change at 69% similarity |
| Overall risk trend accurate | 0.40 → 0.41 (unchanged) — net effect of increases and decreases balanced out |

### Proposed Fix: Section-Aware Comparison

#### Phase 1: Section Header Detection

Parse section boundaries using regex patterns common in legal contracts:

```python
import re

SECTION_PATTERNS = [
    r'^Section\s+\d+[\.\:]',
    r'^Article\s+\d+[\.\:]',
    r'^\d+\.\s+[A-Z]',
    r'^[A-Z][A-Z\s]{3,}$',  # ALL-CAPS headings
]

def extract_sections(text: str) -> list[Section]:
    """Split document into logical sections by detecting headers."""
    # Find all section header positions
    # Group text between consecutive headers into sections
    # Return list of Section(title, body, start_pos, end_pos)
```

#### Phase 2: Two-Level Comparison

1. **Section-level matching** (primary): Match sections by title similarity and embedding similarity. Produces the user-facing summary counts (Added: 2, Removed: 2, Modified: 4, Unchanged: 6).
2. **Chunk-level detail** (secondary): Within each matched section pair, show chunk-level diffs for the detailed "what changed" view.

#### Phase 3: Ignore Section Number Changes

Strip or normalize section numbering before comparison:

```python
def normalize_section_text(text: str) -> str:
    """Remove section numbers to prevent false diffs from renumbering."""
    return re.sub(r'^Section\s+\d+[\.\:]\s*', 'Section. ', text)
```

### Impact Assessment

| Metric | Current (Chunk-Level) | Proposed (Section-Level) |
|--------|----------------------|--------------------------|
| Change count accuracy | ~36 items (inflated 2.5x) | ~14 items (matches reality) |
| False "Modified" rate | ~60% of modifications are false positives | Near zero with section matching |
| User trust | Low — confusing inflated counts | High — matches user's mental model |
| Implementation effort | Already built | Medium — ~2 weeks for phases 1-3 |

---

## Addendum 2 — pgvector Nearest-Neighbor Optimization (2026-03-28)

### Problem: O(n²) In-Memory Similarity Calculations

The original `_compare_clauses` implementation used a double nested loop — for each old clause, it iterated all new clauses and computed cosine similarity in Python. This meant:

- 33 clauses × 33 clauses = 1,089 similarity calculations
- Each calculation iterated 1,536 floats in a Python loop
- A second nested loop ran again for partial matches (MODIFICATION_THRESHOLD)
- Total: ~2,178 similarity computations per comparison

The original ADR noted this was "acceptable for contracts (<100 clauses)" and chose a "greedy matching algorithm rather than optimal bipartite matching (performance over perfection)". At MVP scale this was fine, but the database already had an HNSW index on clause embeddings that could do this work.

### Fix: Delegate to pgvector HNSW Index

Replaced the nested loop with per-clause pgvector nearest-neighbor queries:

```sql
SELECT c.id, 1 - (c.embedding <=> cast(:embedding as vector)) as similarity
FROM clauses c
WHERE c.document_version_id = :version_id
  AND c.id NOT IN (:excluded_ids)
ORDER BY c.embedding <=> cast(:embedding as vector)
LIMIT 1
```

For each old clause, one HNSW probe finds the closest match in the new version's clauses. The `matched_new` exclusion set preserves greedy matching semantics. Falls back to difflib text similarity when embeddings are missing.

### Complexity Change

| Aspect | Before | After |
|--------|--------|-------|
| Algorithm | O(n × m) Python cosine similarity | O(n log m) HNSW index probes |
| Similarity computation | Python loop over 1,536 floats | pgvector C extension |
| Network round-trips | 0 (in-memory) | n small queries (same DB session) |
| Double-loop for partial match | Yes (second O(n × m) pass) | No — single query finds best match at any threshold |

### Additional Optimizations

- **Batch storage deletion**: Supabase `.remove()` accepts a list of paths. Replaced sequential per-version deletion with a single batch call.
- **numpy cosine similarity**: Replaced Python loop in `EmbeddingService.calculate_similarity()` with numpy for any remaining callers.
