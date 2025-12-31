# ADR-003: LLM Classification Strategy for Contract Clause Analysis

## Status
Accepted

## Date
2024-12-31

## Context
ContractLens needs to classify contract clauses by type and assess risk levels. This requires:
- Accurate classification across 15 clause types
- Consistent risk scoring (low, medium, high, critical)
- Human-readable explanations for identified risks
- Cost-effective processing for potentially thousands of clauses per document

### Key Questions
1. Which LLM model balances cost and accuracy for classification tasks?
2. How do we ensure consistent, parseable outputs from an LLM?
3. How do we combine LLM judgment with domain expertise?

## Decision

### Model Selection: GPT-4o-mini
**Chosen over GPT-4o for classification tasks.**

| Factor | GPT-4o-mini | GPT-4o |
|--------|-------------|--------|
| Cost | $0.15/1M input tokens | $2.50/1M input tokens |
| Speed | ~500ms/request | ~1-2s/request |
| Classification accuracy | Sufficient for structured tasks | Better for nuanced reasoning |
| Cost for 1000 clauses | ~$0.05 | ~$0.80 |

**Rationale:** Classification is a structured task with clear categories. GPT-4o-mini performs comparably to GPT-4o on well-defined classification problems while being 16x cheaper. The cost savings enable processing more documents within budget.

### Prompt Engineering: Structured JSON Output

**Strategy 1: Low Temperature (0.1)**
- Reduces randomness in output
- Produces consistent JSON structure
- Trade-off: Less creative explanations, but more reliable parsing

**Strategy 2: Explicit JSON Schema in Prompt**
```
Respond ONLY with valid JSON in this exact format:
{
    "clause_type": "<type>",
    "risk_level": "<level>",
    "risk_score": <0.0-1.0>,
    "risk_explanation": "<1-2 sentence explanation>",
    "confidence": <0.0-1.0>
}
```

**Strategy 3: Enumerated Options**
- Provide explicit list of valid clause types and risk levels
- Include brief descriptions to guide classification
- Reduces hallucinated categories

### Hybrid Scoring: LLM + Domain Rules

Pure LLM scoring can be inconsistent. We blend:
- **70% LLM assessment**: Context-aware evaluation of specific language
- **30% Clause type weight**: Domain knowledge that certain clause types are inherently riskier

```python
CLAUSE_TYPE_RISK_WEIGHTS = {
    "indemnification": 0.8,      # Inherently high-risk
    "limitation_of_liability": 0.85,
    "intellectual_property": 0.7,
    "termination": 0.6,
    "confidentiality": 0.5,
    "notice": 0.2,              # Inherently low-risk
    ...
}

adjusted_score = (llm_score * 0.7) + (type_weight * 0.3)
```

**Rationale:** This ensures that an indemnification clause is never scored as "low risk" even if the LLM underestimates it, while still allowing the LLM to identify unusually risky language within typically safe clause types.

## Consequences

### Positive
- **Cost-effective**: ~$0.05 per document vs ~$0.80 with GPT-4o
- **Consistent outputs**: Low temperature + JSON schema = reliable parsing
- **Balanced scoring**: Combines LLM flexibility with domain expertise
- **Explainable**: Risk explanations provide audit trail for decisions

### Negative
- **Latency**: Sequential API calls add ~500ms per clause (mitigated by batch processing)
- **Model dependency**: Tied to OpenAI API availability and pricing
- **Prompt brittleness**: Model updates may require prompt adjustments

### Trade-offs Accepted
- Slightly less nuanced analysis vs GPT-4o in exchange for 16x cost reduction
- Less creative explanations vs higher temperature in exchange for reliable JSON parsing

## Alternatives Considered

### 1. Fine-tuned Model
- **Pros**: Higher accuracy, faster inference, lower per-token cost
- **Cons**: Requires training data, ongoing maintenance, higher upfront cost
- **Decision**: Deferred until we have labeled training data from user feedback

### 2. Claude 3.5 Sonnet
- **Pros**: Excellent reasoning, good at structured output
- **Cons**: Higher cost ($3/1M tokens), requires separate embedding provider
- **Decision**: Not chosen due to cost and ecosystem complexity

### 3. Local LLM (Llama, Mistral)
- **Pros**: No API costs, data privacy
- **Cons**: Requires GPU, classification quality varies, deployment complexity
- **Decision**: Not feasible on target hardware (M1 MacBook Air)

### 4. Pure Rule-Based Classification
- **Pros**: Deterministic, fast, no API costs
- **Cons**: Requires extensive rule engineering, poor generalization
- **Decision**: Rejected; LLM provides better generalization with less engineering

## Monitoring & Iteration
For production, consider:
1. Logging classification confidence scores to identify low-confidence predictions
2. A/B testing prompt variations to improve accuracy
3. User feedback loop to build training data for potential fine-tuning
4. Fallback to GPT-4o for low-confidence classifications

## References
- [OpenAI Model Pricing](https://openai.com/pricing)
- [Prompt Engineering Guide](https://platform.openai.com/docs/guides/prompt-engineering)
- [Structured Outputs Best Practices](https://platform.openai.com/docs/guides/structured-outputs)
