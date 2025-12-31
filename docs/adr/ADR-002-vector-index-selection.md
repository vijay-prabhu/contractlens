# ADR-002: Vector Index Selection for Semantic Search

## Status
Accepted

## Date
2024-12-31

## Context
ContractLens uses pgvector for storing and searching clause embeddings (1536-dimensional vectors from OpenAI's text-embedding-3-small model). We need an efficient index for similarity search across potentially millions of clauses.

### Initial Approach
We initially created an **ivfflat** (Inverted File with Flat compression) index:
```sql
CREATE INDEX ix_clauses_embedding ON clauses
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

### Problem Discovered
During development testing with a small dataset (1 clause), we discovered that:
1. Queries with `ORDER BY embedding <=> query_vector` returned 0 results
2. The same query without ORDER BY returned correct results
3. The similarity scores were correct when calculated

**Root Cause:** ivfflat uses k-means clustering to partition vectors into "lists". With insufficient data:
- Clusters are poorly formed or empty
- The index probe misses the correct cluster
- ORDER BY triggers index usage, causing incorrect results

## Decision
Switch from **ivfflat** to **HNSW** (Hierarchical Navigable Small World) index.

```sql
CREATE INDEX ix_clauses_embedding ON clauses
USING hnsw (embedding vector_cosine_ops)
WITH (m = 16, ef_construction = 64);
```

## Rationale

### Why HNSW over ivfflat?

| Aspect | ivfflat | HNSW |
|--------|---------|------|
| Small datasets | Poor (needs clusters) | Works correctly |
| Build time | Fast | Slower |
| Query time | Fast | Fast |
| Memory usage | Lower | Higher |
| Accuracy | Good with tuning | Excellent |
| Maintenance | Needs reindexing | Self-maintaining |

### HNSW Parameters
- `m = 16`: Maximum connections per node. Higher values improve recall but use more memory. 16 is a good balance.
- `ef_construction = 64`: Search width during index building. Higher values create better quality indexes but take longer to build.

## Consequences

### Positive
- Consistent behavior from development (1 row) to production (millions of rows)
- No need to rebuild index as data grows
- Better recall (accuracy) for similarity searches
- Simpler operational model

### Negative
- ~2x more memory usage for the index
- Slower initial index build (acceptable for our use case)

### Neutral
- Query performance is comparable to well-tuned ivfflat

## Alternatives Considered

1. **No index (exact search)**: Works for small datasets but O(n) doesn't scale
2. **ivfflat with dynamic lists**: Requires manual tuning and reindexing
3. **External vector database (Pinecone, Weaviate)**: Adds operational complexity

## References
- [pgvector HNSW documentation](https://github.com/pgvector/pgvector#hnsw)
- [HNSW paper](https://arxiv.org/abs/1603.09320)
- [Choosing vector indexes](https://www.pinecone.io/learn/vector-database-index-types/)
