# ADR-009: Classification Quality — Structured Outputs, Few-Shot, and Guardrails

## Status
Accepted (implemented)

## Date
2026-03-28

## Context

ContractLens classifies contract clauses using GPT-4o-mini. The current implementation has several gaps that affect classification reliability and make it hard to detect when things go wrong.

### Current Implementation

```python
response = self.client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this contract clause:\n\n{text}"},
    ],
    temperature=0.1,
    max_tokens=300,
)
result_text = response.choices[0].message.content.strip()
# Manual JSON parsing with regex fallbacks for markdown code blocks
```

### Problems Identified

**1. Free-text JSON parsing (hallucination risk: HIGH)**

The prompt says "Respond ONLY with valid JSON" but we parse the response as free text. When GPT wraps the JSON in markdown code blocks, we regex-extract it. When it returns invalid JSON, we catch the exception and silently default to `clause_type: "other", risk_score: 0.0`. There's no schema enforcement.

OpenAI's Structured Outputs API (`response_format: { type: "json_schema" }`) guarantees 100% schema compliance — the model physically cannot return malformed output. GPT-4o-mini supports this since 2024-07-18.

**2. Zero-shot classification (quality: MEDIUM)**

The prompt defines 15 clause types with one-line descriptions but provides zero examples of correct classification. Research consistently shows few-shot prompting improves classification accuracy 10-25% over zero-shot. Legal clause classification has nuanced boundaries — "indemnification" vs "limitation_of_liability" can overlap in the same sentence.

**3. Self-reported confidence is uncalibrated (grounding: MEDIUM)**

The model returns a `confidence` field (0.0-1.0), but LLM self-reported confidence is poorly calibrated — models are often confidently wrong. The confidence score is stored per clause but never used for any decision. Low-confidence results look identical to high-confidence ones in the UI.

**4. Silent error fallback masks failures (reliability: MEDIUM)**

When classification fails (JSON parse error, API timeout, rate limit), the code returns:
```python
ClassificationResult(
    clause_type="other",
    risk_level="low",
    risk_score=0.0,
    risk_explanation=f"Classification error: {str(e)}",
    confidence=0.0,
    recommendations=[],
)
```
This is indistinguishable from a genuine "other/low" classification in the UI. With 10 concurrent API calls, transient errors silently degrade results. Users can't tell whether a clause was actually low risk or just failed to classify.

**5. Temperature 0.1 allows non-determinism**

The same clause text can produce different risk scores across runs. For a legal tool, reproducibility matters — the same contract should get the same classification every time. Temperature 0 gives deterministic output.

**6. Model not version-pinned**

Using `gpt-4o-mini` without a date suffix means OpenAI can update the model silently. A model update could change classification behavior across all documents without any code change.

## Decision

### 1. Switch to Structured Outputs

Replace free-text JSON parsing with OpenAI's Structured Outputs:

```python
from pydantic import BaseModel, Field
from typing import List, Literal

class ClauseClassification(BaseModel):
    clause_type: Literal[
        "indemnification", "limitation_of_liability", "termination",
        "confidentiality", "payment_terms", "intellectual_property",
        "governing_law", "force_majeure", "warranty", "dispute_resolution",
        "assignment", "notice", "amendment", "entire_agreement", "other"
    ]
    risk_level: Literal["critical", "high", "medium", "low"]
    risk_score: float = Field(ge=0.0, le=1.0)
    risk_explanation: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommendations: List[str] = Field(max_length=3)

response = client.beta.chat.completions.parse(
    model="gpt-4o-mini-2024-07-18",
    messages=[...],
    response_format=ClauseClassification,
)
result = response.choices[0].message.parsed
```

This eliminates all JSON parsing code, the markdown regex fallback, and the `_parse_classification_response` method. The model is constrained to the exact schema.

### 2. Add Few-Shot Examples

Add 3-4 examples to the system prompt covering boundary cases:

```
Example 1 — Indemnification (high risk):
Text: "Provider shall indemnify, defend, and hold harmless Client from any claims arising from Provider's breach..."
Output: { "clause_type": "indemnification", "risk_level": "high", "risk_score": 0.75, ... }

Example 2 — Limitation of Liability (critical risk):
Text: "IN NO EVENT SHALL EITHER PARTY'S AGGREGATE LIABILITY EXCEED THE FEES PAID IN THE PRIOR 12 MONTHS..."
Output: { "clause_type": "limitation_of_liability", "risk_level": "medium", "risk_score": 0.55, ... }

Example 3 — Notice (low risk):
Text: "All notices under this Agreement shall be in writing and delivered to the addresses set forth above..."
Output: { "clause_type": "notice", "risk_level": "low", "risk_score": 0.13, ... }
```

Examples should cover: a high-risk clause, a clause that looks risky but isn't (limitation with reasonable cap), and a straightforward low-risk clause. This anchors the model's scoring calibration.

### 3. Make Error States Visible

Replace silent defaults with explicit error tracking:

```python
@dataclass
class ClassificationResult:
    clause_type: str
    risk_level: str
    risk_score: float
    risk_explanation: str
    confidence: float
    recommendations: List[str]
    classification_failed: bool = False  # NEW: explicit failure flag
```

When classification fails:
- Set `classification_failed = True`
- Set `risk_explanation` to the actual error message
- Store in database with the failure flag
- Surface in the UI as "Classification unavailable" instead of showing fake low-risk scores
- Log and count failures in Sentry for monitoring

### 4. Set Temperature to 0, Pin Model Version

```python
CLASSIFICATION_MODEL = "gpt-4o-mini-2024-07-18"  # Pinned version

response = client.beta.chat.completions.parse(
    model=CLASSIFICATION_MODEL,
    temperature=0,  # Deterministic
    ...
)
```

### 5. Use Confidence Score for Quality Gating

Add a confidence threshold — clauses classified with confidence < 0.6 get flagged:

```python
if result.confidence < 0.6:
    result.risk_explanation = f"[Low confidence: {result.confidence:.0%}] {result.risk_explanation}"
    # Optionally: re-classify with a stronger model (gpt-4o) for low-confidence results
```

This doesn't change the stored result but signals to the user that the classification is uncertain.

## Files to Modify

| File | Change |
|---|---|
| `backend/app/services/classification_service.py` | Structured outputs, few-shot prompt, temperature 0, model pinning, error visibility |
| `backend/app/models/clause.py` | Add `classification_failed` column |
| `backend/app/workers/document_processor.py` | Handle failed classifications differently |
| `backend/migrations/` | New migration for `classification_failed` column |

## Consequences

### Positive
- Zero JSON parsing failures — schema enforced by the API
- More accurate classifications from few-shot examples
- Failures are visible instead of hidden
- Reproducible results from temperature 0 and model pinning
- Low-confidence results flagged for user awareness

### Negative
- Structured Outputs adds ~100ms latency per call (schema validation overhead)
- Few-shot examples increase prompt token count (~200 extra tokens per call, ~$0.01 per document)
- Existing `_parse_classification_response` method and validation code becomes dead code

### Trade-offs
- Using 3-4 few-shot examples rather than fine-tuning (simpler to iterate on, no training pipeline needed)
- Confidence threshold of 0.6 is a starting point — needs tuning with the evaluation framework (ADR-011)
- Not switching to a different model yet — evaluate first with ADR-011's framework, then decide

## References
- [OpenAI Structured Outputs](https://platform.openai.com/docs/guides/structured-outputs)
- [OpenAI: Introducing Structured Outputs](https://openai.com/index/introducing-structured-outputs-in-the-api/)
- [Few-shot Learning for Text Classification (ACL 2023)](https://aclanthology.org/2023.findings-acl.117/)
