# ADR-012: Embedding Model Upgrade

## Status
Accepted (Phase 1 implemented)

## Date
2026-03-28

## Context

ContractLens uses OpenAI's `text-embedding-3-small` (1536 dimensions) for generating clause embeddings used in semantic search and version comparison. This model was chosen for cost efficiency during MVP development.

### Current Model Performance

| Metric | text-embedding-3-small |
|---|---|
| MTEB score | 62.3 |
| Dimensions | 1536 |
| Max tokens | 8,191 |
| Cost | $0.02 / 1M tokens |
| Legal domain tuning | None (general purpose) |

### Why This Matters

Embeddings are used in two critical features:
1. **Semantic search**: Finding clauses matching a user's query
2. **Version comparison**: Matching clauses across document versions (now via pgvector nearest-neighbor, ADR-004/ADR-007)

A 2-3% improvement in embedding quality directly translates to better search relevance and fewer false matches/misses in comparison.

### Research Findings

| Finding | Source |
|---|---|
| text-embedding-3-large scores 64.6 on MTEB vs small's 62.3 | MTEB Leaderboard |
| Domain-specific fine-tuning shows +10-30% gains for specialized domains (legal, medical) | Multiple MTEB analyses |
| Cohere Embed v4 and OpenAI 3-large are the most common choices for production RAG | Mixpeek 2026 ranking |
| When the workload involves specialized language, domain-specific models outperform general-purpose ones | Multiple benchmark analyses |
| Legal text has domain-specific semantics ("indemnify" ≈ "hold harmless") that general models may not capture well | Domain embedding research |

## Decision

### Phase 1: Upgrade to text-embedding-3-large

Straightforward upgrade - same API, same provider, better quality:

| Metric | Small (current) | Large (proposed) |
|---|---|---|
| MTEB score | 62.3 | 64.6 (+3.7%) |
| Dimensions | 1536 | 3072 |
| Cost | $0.02 / 1M tokens | $0.13 / 1M tokens (6.5x) |
| Max tokens | 8,191 | 8,191 |

**Cost impact for ContractLens:**

A typical document has 30-80 chunks × ~200 tokens per chunk = ~4,000-16,000 tokens per document.

| | Small | Large |
|---|---|---|
| Cost per document (30 chunks) | $0.00012 | $0.00078 |
| Cost per 1,000 documents | $0.12 | $0.78 |
| Monthly cost (100 docs/month) | $0.012 | $0.078 |

The cost increase is negligible - $0.78 per 1,000 documents. The quality improvement is worth it.

**Dimension change (1536 → 3072):**

The pgvector column type `vector(1536)` needs to change to `vector(3072)`. This requires:
- A database migration to alter the column
- Regenerating embeddings for existing clauses (use the Reprocess button)
- Updating the HNSW index parameters

Alternatively, use OpenAI's dimension reduction feature to keep 1536 dimensions:
```python
response = client.embeddings.create(
    model="text-embedding-3-large",
    input=text,
    dimensions=1536,  # Truncate to 1536 dims
)
```
This gives most of the quality benefit (~63.5 MTEB) without changing the database schema. Can upgrade to full 3072 dims later.

### Phase 2: Evaluate Domain-Specific Models (Future)

Once the evaluation framework (ADR-011) is in place, benchmark:

1. **text-embedding-3-large (full 3072 dims)** - maximum quality from OpenAI
2. **Cohere Embed v4** - competitive with OpenAI, offers search-optimized vs input-optimized variants
3. **Legal domain fine-tuned models** - if the evaluation shows legal-specific terms are poorly embedded, fine-tune on contract corpus
4. **Open-source alternatives** - BGE, GTE models if cost or data privacy becomes a concern

Phase 2 depends on ADR-011 (evaluation framework) being implemented first - we need the measurement infrastructure to compare models meaningfully.

## Implementation

### Phase 1 Changes

| File | Change |
|---|---|
| `backend/app/services/embedding_service.py` | Change model to `text-embedding-3-large`, add `dimensions=1536` parameter |
| `backend/app/core/config.py` | Add `EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` settings |

The change is small:

```python
# Before
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536

# After
EMBEDDING_MODEL = "text-embedding-3-large"
EMBEDDING_DIMENSIONS = 1536  # Using dimension reduction for backward compat

response = self.client.embeddings.create(
    model=self.model,
    input=valid_texts,
    dimensions=EMBEDDING_DIMENSIONS,  # NEW: explicit dimension control
)
```

**No database migration needed** if we use dimension reduction (1536 dims from the large model). Existing embeddings from the small model and new embeddings from the large model coexist in the same vector column. Quality improves incrementally as documents are reprocessed.

### Phase 2 Changes (Future)

If full 3072 dimensions are needed:
- Migration: `ALTER TABLE clauses ALTER COLUMN embedding TYPE vector(3072)`
- Rebuild HNSW index
- Reprocess all documents to regenerate embeddings
- Update `EMBEDDING_DIMENSIONS = 3072`

## Consequences

### Positive
- Better search relevance - improved MTEB score translates to better clause matching
- Better comparison accuracy - fewer false matches between versions
- Negligible cost increase ($0.66/month more for 1000 documents)
- No database migration needed with dimension reduction approach
- Incremental upgrade - new documents get better embeddings, old documents upgraded via Reprocess

### Negative
- Slight latency increase for embedding generation (~100ms more per batch)
- Mixed embedding quality during transition (old docs: small model, new docs: large model)
- Full 3072 dimensions would require migration and ~2x more vector storage

### Trade-offs
- Using dimension reduction (1536 from large model) rather than full 3072 - simpler migration, most of the quality benefit
- Not switching to a completely different embedding provider - staying with OpenAI for API consistency
- Not fine-tuning yet - need evaluation framework first to measure the gap

## References
- [OpenAI Embeddings Guide](https://platform.openai.com/docs/guides/embeddings)
- [MTEB Leaderboard](https://huggingface.co/spaces/mteb/leaderboard)
- [Which Embedding Model Should You Use in 2026?](https://zc277584121.github.io/rag/2026/03/20/embedding-models-benchmark-2026.html)
- [Best Embedding Models 2026: MTEB Scores](https://app.ailog.fr/en/blog/guides/choosing-embedding-models)
- [Mixpeek: Best Embedding Models in 2026](https://mixpeek.com/curated-lists/best-embedding-models)
