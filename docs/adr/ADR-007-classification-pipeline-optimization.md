# ADR-007: Classification Pipeline Optimization

## Status
Accepted

## Date
2026-03-27

## Context

Document processing in ContractLens takes ~84 seconds for a 43KB PDF. I profiled the full pipeline to find where time is spent.

### Profiling Results (43KB PDF, 30 chunks)

| Step | Time | % of Total |
|---|---|---|
| DB fetch (Supabase Postgres) | 0.31s | 0.4% |
| Storage download (Supabase Storage) | 0.67s | 0.8% |
| Text extraction (PyMuPDF) | 0.08s | 0.1% |
| Chunking (LangChain) | 0.00s | 0% |
| **AI embed + classify** | **81.63s** | **97.3%** |
| DB save (Supabase Postgres) | 1.01s | 1.2% |
| **Total** | **83.92s** | |

Breaking down the AI step:
- **Embeddings** (OpenAI text-embedding-3-small): 1.32s — one batch API call, fast
- **Classification** (GPT-4o-mini): 80.31s — 30 sequential API calls, ~2.7s each

### Root Cause

`classify_clauses_batch()` loops through chunks one at a time, making a separate GPT-4o-mini API call for each chunk. The CPU is idle 97% of the time — it's pure I/O wait.

Supabase latency is not the issue. Storage + DB combined is under 2 seconds.

### Key Insight

External LLM API calls have a hard floor of ~1-3s per call. You can't get sub-second classification with external APIs regardless of optimization. Production AI systems solve this by distilling LLM outputs into fast local models.

## Decision

Phased optimization approach:

### Phase 1: Parallelize API calls (immediate)

Run classification calls concurrently using `asyncio.gather` with a concurrency limit of 5-10.

- **Expected improvement**: ~80s → ~8-16s
- **Effort**: Small — change `classify_clauses_batch` to use async + semaphore
- **Risk**: Low — OpenAI rate limits are generous for gpt-4o-mini
- **Trade-off**: Slightly higher burst API usage, but total tokens are identical

### Phase 2: Stream results to frontend (next)

Show clauses appearing one by one as they're classified, instead of waiting for all 30 to complete. Pairs with the SSE approach from ADR-005.

- **Expected improvement**: Perceived wait drops from ~10s to ~2-3s
- **Effort**: Medium — needs frontend changes to handle progressive loading
- **Risk**: Low

### Phase 3: Fine-tuned local classifier (later)

Train a small model (BERT/DistilBERT, ~110M params) on the 14 clause types + risk levels using existing GPT-4o-mini outputs as training data. Run inference locally.

- **Expected improvement**: 80s → <1s for all 30 chunks
- **Effort**: High — needs training pipeline, model serving, evaluation
- **Risk**: Medium — classification quality depends on training data volume and quality
- **Trade-off**: Loses GPT-4o-mini's flexibility for edge cases. Hybrid approach (local model + LLM fallback for low-confidence results) mitigates this.

## Alternatives Considered

### Batch multiple chunks per prompt
Send 3-5 chunks in a single GPT-4o-mini call with structured output.

- Fewer API calls total (~6-10 instead of 30)
- But: larger prompts can degrade classification quality, complex JSON parsing, harder to attribute errors to specific chunks
- Rejected in favor of parallelization which is simpler and equally fast

### OpenAI Batch API
Asynchronous batch processing at 50% cost reduction.

- Results returned within 24 hours, not real-time
- Not suitable for interactive document upload flow
- Could be useful for bulk re-processing or re-classification jobs

### Caching by embedding similarity
Cache classification results and reuse for chunks with >95% embedding similarity.

- Legal contracts reuse boilerplate — high cache hit rate expected
- Good complement to any phase, not a standalone solution
- Worth adding alongside Phase 1 or 2

## Consequences

- Phase 1 gives immediate 5-10x speedup with minimal code change
- Each phase builds on the previous — no throwaway work
- Phase 3 requires accumulating enough classified data first, so Phase 1 serves double duty: faster processing AND training data generation
- The profiling instrumentation (`[PERF]` logs) stays in place to measure improvements
