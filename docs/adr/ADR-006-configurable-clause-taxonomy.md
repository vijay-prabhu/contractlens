# ADR-006: Configurable Clause Type Taxonomy

## Status
Partially Implemented (Phase 1 + Phase 3)

### What's implemented (2026-03-28)
- **Phase 1**: `config/clause_types.yaml` as single source of truth
- **Phase 1**: Dynamic prompt builder from YAML config (`clause_taxonomy.py`)
- **Phase 1**: Risk weights loaded from YAML instead of hardcoded dict
- **Phase 2**: Validation logging - unknown types from LLM are logged with suggestion to add to YAML
- **Phase 3**: 8 new built-in types added (23 total, was 15):
  - `non_compete` (0.70) - was classified as "other"
  - `data_protection` (0.65) - was classified as "confidentiality"
  - `audit_rights` (0.50) - was classified as "other"
  - `representations` (0.40) - was classified as "warranty"
  - `insurance` (0.50)
  - `exclusivity` (0.60)
  - `service_levels` (0.55)
  - `change_of_control` (0.55)

### What's pending
- **Phase 4**: Custom types API (DB table, CRUD endpoints)
- **Phase 5**: Custom types UI (settings page, type management)
- **Phase 6**: Re-classification of existing documents with updated taxonomy

## Context

ContractLens classifies contract clauses into one of 15 predefined types. The current implementation hardcodes these types in three separate locations, making the system rigid and difficult to extend.

### Current State

Clause types are hardcoded in **three places** that must be kept in sync:

| Location | File | What's Hardcoded |
|----------|------|------------------|
| Python Enum | `app/models/clause.py:15-32` | `ClauseType` enum with 15 values |
| Domain Risk Weights | `app/services/classification_service.py:33-49` | `CLAUSE_TYPE_RISK_WEIGHTS` dict mapping each type to a float (0.0–1.0) |
| LLM System Prompt | `app/services/classification_service.py:52-110` | `CLASSIFICATION_SYSTEM_PROMPT` string listing all 15 types with descriptions |

### The 15 Clause Types

| Type | Domain Risk Weight | Rationale |
|------|-------------------|-----------|
| `indemnification` | 0.80 | Unlimited indemnity can expose a party to uncapped losses |
| `limitation_of_liability` | 0.85 | Caps (or lack thereof) determine maximum financial exposure |
| `termination` | 0.60 | Difficult exit conditions can trap a party in unfavorable terms |
| `confidentiality` | 0.50 | Overly broad or long-duration obligations create compliance burden |
| `intellectual_property` | 0.70 | IP assignment vs. licensing has significant long-term value implications |
| `warranty` | 0.65 | Warranty disclaimers shift risk; broad warranties create exposure |
| `dispute_resolution` | 0.55 | Arbitration clauses, venue selection affect cost/fairness of resolution |
| `force_majeure` | 0.50 | Broad vs. narrow definitions determine excuse for non-performance |
| `payment_terms` | 0.45 | Late payment penalties, net terms affect cash flow |
| `assignment` | 0.40 | Restricts or permits transfer of obligations to third parties |
| `amendment` | 0.35 | Oral amendment clauses or unilateral modification rights are risky |
| `governing_law` | 0.30 | Usually low-risk but unfavorable jurisdiction can be costly |
| `entire_agreement` | 0.25 | Standard boilerplate, rarely contentious |
| `notice` | 0.20 | Standard procedural clause with minimal risk |
| `other` | 0.30 | Catch-all for unrecognized clause types |

### Why These 15 Types Were Chosen

These types represent the most common clause categories found in commercial contracts (services agreements, NDAs, SaaS/licensing agreements, procurement contracts). The selection was based on:

1. **Legal practice standards**: These map to the sections a corporate legal team would typically review during contract negotiation
2. **Risk differentiation**: Each type has a meaningfully different inherent risk profile (from `notice` at 0.20 to `limitation_of_liability` at 0.85)
3. **LLM classification accuracy**: GPT-4o-mini can reliably distinguish between these categories at low temperature (0.1) with the structured prompt
4. **Coverage**: Together they cover ~90% of clauses in typical commercial contracts, with `other` as a catch-all

### What's Missing

Real-world contracts contain clause types not in the current taxonomy:

| Missing Type | Common In | Example |
|---|---|---|
| `non_compete` / `non_solicitation` | Employment, services | Restrictions on competing or hiring |
| `data_protection` / `privacy` | SaaS, technology | GDPR/CCPA compliance obligations |
| `representations` | M&A, investment | Statements of fact relied upon by counterparty |
| `insurance` | Services, construction | Required coverage types and minimums |
| `audit_rights` | Enterprise, regulated | Right to inspect books, records, compliance |
| `exclusivity` | Distribution, licensing | Exclusive dealing or territory restrictions |
| `service_levels` / `SLA` | SaaS, managed services | Uptime guarantees, response times, credits |
| `change_of_control` | M&A, licensing | Rights triggered by acquisition or merger |

Currently, all of these fall into `other` - losing their specific risk context and domain weight.

### Problems with the Current Approach

1. **Adding a new type requires code changes in 3 files** - easy to miss one and create inconsistency
2. **No user customization** - different industries have different clause taxonomies (healthcare contracts vs. construction vs. SaaS)
3. **`other` is a black hole** - ~15-20% of clauses in test documents land in `other`, losing their specific risk context
4. **Validation silently downgrades** - if GPT-4o-mini returns a type not in the enum, `_validate_result()` (line 219) silently converts it to `other` instead of flagging the gap
5. **Risk weights are developer-defined** - legal teams may disagree with the relative weights (e.g., `governing_law` at 0.30 may be too low for cross-border contracts)

## Decision

Implement a **three-tier configurable clause taxonomy** for v2.0:

### Tier 1: Config File (Backend)

Move clause types, descriptions, and risk weights from Python code to a YAML configuration file:

```yaml
# config/clause_types.yaml
clause_types:
  indemnification:
    description: "Clauses about protecting parties from losses, damages, or liabilities"
    risk_weight: 0.80
    category: "financial"
    builtin: true

  limitation_of_liability:
    description: "Clauses limiting damages or liability exposure"
    risk_weight: 0.85
    category: "financial"
    builtin: true

  data_protection:
    description: "Clauses about data privacy, GDPR/CCPA compliance, data processing"
    risk_weight: 0.65
    category: "compliance"
    builtin: true

  # ... all types listed here

  other:
    description: "Does not fit any defined category"
    risk_weight: 0.30
    category: "general"
    builtin: true
    is_fallback: true

settings:
  hybrid_score_llm_weight: 0.70
  hybrid_score_domain_weight: 0.30
```

**Benefits:**
- Single source of truth for all clause metadata
- Adding a new built-in type = adding a YAML block (no code changes)
- Weights tunable without redeploying code

### Tier 2: Dynamic Prompt Builder (Backend)

Replace the hardcoded `CLASSIFICATION_SYSTEM_PROMPT` with a function that builds the prompt from the config:

```python
def build_classification_prompt(clause_types: dict) -> str:
    """Build GPT-4o-mini system prompt from clause type config."""
    type_descriptions = []
    for type_key, type_config in clause_types.items():
        type_descriptions.append(
            f"- {type_key}: {type_config['description']}"
        )

    return f"""You are a legal contract analyst AI...

## Clause Types (choose one):
{chr(10).join(type_descriptions)}

## Risk Levels:
...
"""
```

**Benefits:**
- Prompt always matches the config - no sync issues
- Custom types automatically appear in the LLM prompt
- Can be rebuilt at startup or when config changes

### Tier 3: User-Defined Custom Types (Frontend + Backend)

Allow users to add custom clause types via the UI:

**Database schema addition:**
```sql
CREATE TABLE custom_clause_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    type_key VARCHAR(50) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    risk_weight FLOAT NOT NULL DEFAULT 0.50,
    category VARCHAR(50) DEFAULT 'custom',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, type_key)
);
```

**API endpoints:**
```
GET    /api/v1/clause-types           → list all types (built-in + user's custom)
POST   /api/v1/clause-types           → create custom type
PATCH  /api/v1/clause-types/{id}      → update custom type (description, weight)
DELETE /api/v1/clause-types/{id}      → soft-delete custom type
```

**Frontend UI:**
- Settings page with clause type management
- Table showing all types with name, description, risk weight, usage count
- "Add Custom Type" form with name, description, risk weight slider
- Edit/delete for custom types only (built-in types show weight adjustment only)
- Toggle to enable/disable types without deleting

**Classification flow with custom types:**
1. On document processing, load built-in types from YAML + user's custom types from DB
2. Build the LLM prompt dynamically with all active types
3. Validate LLM response against the combined type list
4. Apply the appropriate risk weight (custom weight for custom types)

### Validation Changes

Replace the current silent fallback with logging:

```python
def _validate_result(self, parsed: dict, original_text: str, valid_types: list[str]) -> ClassificationResult:
    clause_type = parsed.get("clause_type", "other").lower()
    if clause_type not in valid_types:
        logger.warning(
            f"LLM returned unknown clause type '{clause_type}', falling back to 'other'. "
            f"Consider adding this type to the taxonomy."
        )
        clause_type = "other"
```

This surfaces types the LLM wants to use but can't, informing future taxonomy expansion.

## Implementation Plan

| Phase | Scope | Effort | Dependencies |
|-------|-------|--------|-------------|
| Phase 1: Config file | Create `clause_types.yaml`, load at startup, build prompt dynamically | 1-2 days | None |
| Phase 2: Validation logging | Log unknown types instead of silent fallback | 0.5 day | Phase 1 |
| Phase 3: Expanded built-in types | Add `non_compete`, `data_protection`, `representations`, `insurance`, `audit_rights`, `exclusivity`, `service_levels`, `change_of_control` to config | 1 day | Phase 1 |
| Phase 4: Custom types API | DB table, CRUD endpoints, merged type loading | 2-3 days | Phase 1 |
| Phase 5: Custom types UI | Settings page, type management, weight adjustment | 2-3 days | Phase 4 |
| Phase 6: Re-classification | Option to re-classify existing documents with updated taxonomy | 1-2 days | Phase 4 |

**Total estimated effort: 7-12 days**

## Consequences

### Positive

- **Single source of truth**: One config file governs types, weights, and descriptions
- **Zero-code extensibility**: New built-in types require only a YAML change
- **User empowerment**: Legal teams can define domain-specific clause types
- **Better coverage**: Reduces `other` bucket from ~15-20% to ~5%
- **Audit trail**: Custom types are persisted with user association
- **Dynamic prompts**: LLM always sees the current taxonomy

### Negative

- **Prompt length increase**: More types = longer system prompt = slightly higher token cost per classification
- **Per-user prompt variation**: Custom types mean the LLM gets different prompts per user, making classification less comparable across users
- **Migration complexity**: Existing `other` clauses may need re-classification after taxonomy expansion
- **Weight tuning responsibility**: Users adjusting weights could produce unexpected risk scores

### Risks

1. **Too many custom types degrade LLM accuracy**: If a user adds 50 custom types, the LLM may struggle to distinguish them
   - Mitigation: Cap custom types at 20 per user, warn when adding similar types
2. **Custom types with overlapping definitions**: User creates `data_privacy` when `data_protection` already exists
   - Mitigation: Show similarity check when creating new types, suggest existing matches
3. **Weight conflicts**: A custom weight of 0.0 on `indemnification` would hide critical risk
   - Mitigation: Built-in types have a minimum weight floor (can be adjusted but not zeroed out)

## Alternatives Considered

### 1. Database-Only Configuration (No YAML)

**Pros**: Single storage mechanism, editable via admin UI
**Cons**: Requires DB access to change built-in types, no version control, harder to deploy defaults
**Decision**: Rejected - YAML for built-in types provides version control and easy deployment; DB for user custom types provides persistence and per-user isolation

### 2. Keep Hardcoded, Add More Types

**Pros**: Simplest change, just expand the enum
**Cons**: Still requires 3-file code changes, no user customization, same maintenance burden
**Decision**: Rejected - doesn't solve the root problem of rigidity

### 3. Fully Dynamic (No Built-in Types)

**Pros**: Maximum flexibility
**Cons**: New users start with empty taxonomy, must configure before first use, no sensible defaults
**Decision**: Rejected - the 15+ built-in types provide immediate value out of the box

## Related: Perspective-Aware Risk Scoring

A separate but closely related gap: the current classification prompt does not specify which party's perspective to assess risk from. The same clause change can be risk-reducing for one party and risk-increasing for the other. Combined with the domain weight floor from the hybrid formula, this means risk score reductions are harder to observe than expected.

This is tracked as a v2.0 enhancement alongside the configurable taxonomy work. See [ADR-003 - Known Limitation: No Party Perspective](ADR-003-llm-classification-strategy.md#known-limitation-no-party-perspective-in-risk-scoring) for the proposed fix (party selection + dual scoring).

## References

- [ADR-003: LLM Classification Strategy](ADR-003-llm-classification-strategy.md) - covers model selection, hybrid scoring, and perspective-aware scoring proposal
- [YAML Configuration Best Practices](https://yaml.org/spec/1.2.2/)
- [Pydantic Settings with YAML](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
