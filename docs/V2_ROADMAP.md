# ContractLens v2.0 Roadmap

Items identified during the v1 audit and implementation session (2026-03-28). Ordered by impact.

## High Priority

### Real-Time Streaming (ADR-005)
The UI polls every 2 seconds during document processing. Replace with SSE or Supabase Realtime so clauses appear one by one as they're classified. Total processing is ~12s but perceived wait drops to ~2-3s.

### Custom Clause Types UI (ADR-006 Phase 4-5)
Config-driven taxonomy is done (23 types from YAML). Next step: let users add custom types via the UI. Needs a database table for custom types, CRUD API, and a settings page. Legal teams in different industries need different taxonomies.

### Party-Perspective Risk Scoring (ADR-003)
The classifier doesn't know which party's perspective to assess risk from. The same clause change can be risk-reducing for one party and risk-increasing for the other. Needs a party selector in the UI and dual scoring in the prompt.

### Evaluation Phase 2 (ADR-011)
The gold standard has 29 clauses from one contract. Expand to 200+ clauses using the CUAD dataset (13,101 labeled clauses from 510 contracts). Map their 41 categories to our 23 types. This gives statistical confidence on accuracy per type.

## Medium Priority

### Training Data Export
Export all GPT-4o-mini classified clauses as JSON for future fine-tuning of a local BERT/DistilBERT model (ADR-007 Phase 3). One SQL query, simple script. Wait until 1000+ classified clauses before fine-tuning.

### Benchmark Corpus Ingestion
Batch import CUAD and ContractEval datasets for evaluation. Needs a loader script that maps external taxonomies to ours. This is the data engineering piece we deferred.

### Section-Aware Comparison (ADR-004)
Docling now produces section-level output. The comparison service should match at section level (not chunk level) to reduce false positives. ADR-004's addendum documented the problem: 36 changes detected when only 14 were real.

### Rate Limiting (ADR-014 Phase 2)
Security module has rate limiting code but Redis isn't connected in the app. Wire Redis, add per-user limits on uploads (20/hour) and classification calls (100/hour).

### Langfuse Phase 2-3 (ADR-013)
Trace embedding calls and add document-level parent traces. Track cost per document, per user, per month. Currently only classification calls are traced.

## Low Priority

### Dark Mode
Frontend has no `dark:` Tailwind variants. Add dark mode support across all components.

### Component Memoization
Compare page child components (SummaryCard, RiskTrendIndicator, ClauseChangeCard) are not memoized. Unnecessary re-renders on filter changes.

### Data Residency Documentation (ADR-014 Phase 3)
Document what data goes to OpenAI for user trust. Add a privacy section to the UI or README.

### Embedding Model Phase 2 (ADR-012)
Evaluate full 3072-dimension embeddings (needs DB migration), Cohere Embed v4, and domain-specific legal embeddings. Depends on evaluation framework being expanded first.

### Model A/B Testing (ADR-011)
Benchmark GPT-4o-mini vs GPT-5 mini vs Claude Haiku 4.5 on our gold standard. Pick the best model for accuracy, latency, and cost.

## Completed (v1)

- Parallel classification: 84s to 12s (ADR-007)
- CVSS-inspired risk scoring (ADR-008)
- Structured outputs with few-shot examples (ADR-009)
- Docling parsing with section-aware chunking (ADR-010)
- Evaluation framework with 96.6% baseline (ADR-011)
- Embedding model upgrade to text-embedding-3-large (ADR-012)
- Langfuse AI observability (ADR-013)
- Input sanitization and anomaly detection (ADR-014)
- CI/CD eval gate on GitHub Actions (ADR-015)
- Config-driven taxonomy with 23 clause types (ADR-006)
- Code standards cleanup, DI, constants, error boundaries
- AGENTS.md, CONTRIBUTING.md, ESLint/Prettier config
- Dev scripts, Docker fix, port standardization
