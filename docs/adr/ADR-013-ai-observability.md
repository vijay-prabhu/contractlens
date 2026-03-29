# ADR-013: AI Observability - LLM Monitoring and Cost Tracking

## Status
Accepted (Phase 1 implemented - classification traces)

## Date
2026-03-28

## Context

ContractLens has Sentry for error tracking and custom `[PERF]` logs for pipeline timing. This covers crashes and latency but misses the observability specific to LLM applications:

### What we can't answer today

- How much does it cost to process a document? Per user? Per month?
- How many tokens are we consuming per classification call?
- What's the P99 latency for OpenAI API calls?
- When the model version changes, did classification quality shift?
- Which prompt version is currently deployed?
- Are we seeing classification drift over time (more clauses classified as "other" this week)?

### Industry Standard

Production LLM applications in 2026 use dedicated observability platforms that trace every LLM call with token counts, latency, cost, prompt versions, and response quality. The leading tools are Langfuse (open-source, self-hostable), LangSmith (LangChain ecosystem), and Helicone (proxy-based, fastest setup).

## Decision

Integrate **Langfuse** for LLM observability.

### Why Langfuse

| Criteria | Langfuse | LangSmith | Helicone |
|---|---|---|---|
| Open source | Yes | No | Partial |
| Self-hostable | Yes | No | No |
| Setup time | 1-2 hours | 15 min (LangChain only) | 15 min |
| Prompt management | Yes | Yes | No |
| Evaluations built-in | Yes | Yes | No |
| Cost | Free tier / self-host | Free tier then paid | Free tier then paid |
| Vendor lock-in | None | Tied to LangChain | Proxy dependency |

Langfuse covers all three needs: tracing, prompt management, and evaluations. It's open-source and self-hostable - important for a legal tech app handling confidential contracts.

### What to Track

**Per LLM call:**
- Model, prompt version, token count (input + output), latency, cost
- Classification result (clause_type, risk_level, confidence)
- Whether classification_failed

**Per document:**
- Total token usage, total cost, total processing time
- Number of chunks, extraction method used
- User ID (for per-user cost tracking)

**Aggregated dashboards:**
- Daily/weekly token usage and cost
- Classification distribution over time (detect drift)
- Average confidence by clause type
- Failure rate trends
- Latency percentiles (P50, P95, P99)

### Implementation

**Phase 1: Instrument classification service**

```python
from langfuse import Langfuse

langfuse = Langfuse()

# Wrap each classification call
trace = langfuse.trace(name="classify_clause", user_id=user_id)
generation = trace.generation(
    name="gpt-4o-mini-classification",
    model="gpt-4o-mini-2024-07-18",
    input={"text": clause_text},
    output={"clause_type": result.clause_type, "risk_level": result.risk_level},
    usage={"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens},
)
```

**Phase 2: Instrument embedding service**

Track embedding token usage and batch sizes.

**Phase 3: Document-level traces**

Create a parent trace per document upload that contains all classification and embedding generations as child spans.

## Files to Modify

| File | Change |
|---|---|
| `pyproject.toml` | Add `langfuse` dependency |
| `backend/app/core/config.py` | Add Langfuse env vars (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST) |
| `backend/app/services/classification_service.py` | Wrap LLM calls with Langfuse traces |
| `backend/app/services/embedding_service.py` | Track embedding token usage |
| `backend/app/workers/document_processor.py` | Parent trace per document |

## Consequences

### Positive
- Full visibility into LLM cost, latency, and quality
- Prompt versioning for safe iteration
- Classification drift detection
- Per-user and per-document cost tracking

### Negative
- New external dependency (or self-hosted service)
- Small latency overhead per traced call (~5-10ms)
- Requires Langfuse account or self-hosted instance

## References
- [Langfuse Documentation](https://langfuse.com/docs)
- [Helicone: Complete Guide to LLM Observability](https://www.helicone.ai/blog/the-complete-guide-to-LLM-observability-platforms)
- [Firecrawl: Best LLM Observability Tools 2026](https://www.firecrawl.dev/blog/best-llm-observability-tools)
