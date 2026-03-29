# ContractLens v2.0 Roadmap

## Vision

v2.0 transforms ContractLens from a working prototype into a production-ready platform. The focus areas are: configurable intelligence, reliable infrastructure, and real-time experience.

## Current State (v1.0)

- 15 hardcoded clause types with fixed risk weights
- Chunk-level comparison (produces inflated change counts)
- Polling-based status updates (1.5-5s delay)
- No tests, no rate limiting, no caching
- Single-user scale, localhost deployment
- 23 known gaps documented (5 critical, 5 high, 8 medium, 5 low)

## Release Timeline

### v1.1 — Stability (Pre-requisite for v2.0)

**Focus**: Fix silent failures, error handling, security
**Gaps Addressed**: #1, #2, #3, #4, #5, #8, #9, #12, #13

| Item | Description | Effort |
|------|-------------|--------|
| CORS from env vars | Move `allow_origins` to `CORS_ORIGINS` env var | 0.5 day |
| Worker failure handling | Track partial failures, `completed_with_warnings` status, retry logic | 2-3 days |
| Sanitize API errors | Generic client messages, Sentry for full details | 1 day |
| Rate limiting | `slowapi` middleware (10 searches/min, 5 uploads/min per user) | 1 day |
| Sentry sampling config | Environment-based `traces_sample_rate` and `profiles_sample_rate` | 0.5 day |
| Document list limit | `Query(100, ge=1, le=100)` validation | 0.5 day |
| Error propagation | Replace silent `except: pass` with proper error handling | 1-2 days |
| Console.log cleanup | Remove debug logging from frontend | 0.5 day |
| File magic byte validation | Check `%PDF`/`PK` content, not just extension | 0.5 day |

### v1.2 — UX Polish

**Focus**: Fix loading states, pagination, accessibility
**Gaps Addressed**: #6, #7, #10, #11, #13, #14, #18, #19

| Item | Description | Effort |
|------|-------------|--------|
| Document card during processing | Pass metadata via URL params, render immediately | 1 day |
| Frontend pagination | Pagination controls on dashboard, use backend `skip`/`limit` | 1-2 days |
| Component error boundaries | Wrap clause list, version history, risk summary | 1 day |
| Fix metadata placeholders | Update `title`/`description` in `layout.tsx` | 0.5 day |
| Accessibility pass | `aria-label`, keyboard navigation, heading hierarchy | 2-3 days |
| Token cache fix | Reduce buffer to 10s, clear on 401, retry once | 0.5 day |
| Sentry config migration | Move to non-deprecated `webpack.*` options | 0.5 day |
| Poetry PEP 621 migration | Migrate `pyproject.toml` to `[project]` table | 0.5 day |

### v1.3 — Comparison & Performance

**Focus**: Section-aware comparison, caching, optimization
**Gaps Addressed**: #15 (chunk→section), #16, #17, #21

| Item | Description | Effort |
|------|-------------|--------|
| Section header detection | Parse `Section N.`, `Article N.`, ALL-CAPS headings | 2-3 days |
| Two-level comparison | Section-level summary + chunk-level detail within sections | 3-4 days |
| Section number normalization | Strip numbering before comparison | 1 day |
| Comparison pre-filtering | Compare by clause type first, reduce O(n²) matching | 1-2 days |
| JSONB recommendations | Migrate `TEXT` → `JSONB` for recommendations column | 1 day |
| Redis implementation | Embedding cache, rate limiting backend, session store | 2-3 days |
| Document status enum consistency | Use `DocumentStatus` enum everywhere | 0.5 day |

---

### v2.0 — Production

**Focus**: Configurable clause types, testing, deployment, monitoring

#### Configurable Clause Taxonomy (ADR-006)

| Phase | Description | Effort |
|-------|-------------|--------|
| Config file | `clause_types.yaml` as single source of truth | 1-2 days |
| Dynamic prompt builder | Build LLM system prompt from config at startup | 1 day |
| Validation logging | Log unknown types returned by LLM (instead of silent fallback) | 0.5 day |
| Expanded built-in types | Add `non_compete`, `data_protection`, `representations`, `insurance`, `audit_rights`, `exclusivity`, `service_levels`, `change_of_control` | 1 day |
| Custom types API | DB table (`custom_clause_types`), CRUD endpoints | 2-3 days |
| Custom types UI | Settings page with type management, weight sliders | 2-3 days |
| Re-classification support | Option to re-classify existing documents with updated taxonomy | 1-2 days |

#### Perspective-Aware Risk Scoring (ADR-003 Addendum)

| Phase | Description | Effort |
|-------|-------------|--------|
| Party selection | Add `risk_perspective` param (Provider/Client/Balanced) to classification prompt; user selects party role on upload | 2-3 days |
| Dual scoring | Score each clause from both perspectives in a single LLM call; store `risk_score_provider` + `risk_score_client` | 2-3 days |
| UI: Risk to You vs Counterparty | Show dual risk scores in clause detail, comparison, and risk summary | 1-2 days |
| Domain weight floor adjustment | Make the hybrid formula weights (currently 0.7/0.3 LLM/domain split) configurable in `clause_types.yaml` | 0.5 day |

#### Real-Time Architecture (ADR-005)

| Phase | Description | Effort |
|-------|-------------|--------|
| Supabase Realtime | Enable CDC on `documents` table, `useDocumentRealtime` hook | 2-3 days |
| SSE progress endpoint | `/documents/{id}/progress` with in-memory store | 2-3 days |
| Granular progress UI | "Analyzing clause X of Y", smooth progress bar | 1-2 days |
| Redis progress store | Multi-instance support, TTL on entries | 1-2 days |

#### Testing

| Item | Description | Effort |
|------|-------------|--------|
| Backend unit tests | Classification, comparison, search services with mocked OpenAI | 3-4 days |
| Backend integration tests | Full processing pipeline with test DB | 2-3 days |
| Frontend component tests | Document detail, comparison, search pages | 2-3 days |
| E2E tests | Upload → process → analyze → compare flow | 2-3 days |

#### Deployment & Monitoring

| Item | Description | Effort |
|------|-------------|--------|
| CI/CD pipeline | GitHub Actions: lint, test, build, deploy | 2-3 days |
| Frontend deployment | Vercel with preview deploys on PR | 1 day |
| Backend deployment | Railway or Render with auto-deploy from main | 1-2 days |
| Structured logging | JSON logs with X-Request-ID correlation | 1 day |
| Health checks | `/health` endpoint with DB, OpenAI, storage connectivity | 0.5 day |
| OpenTelemetry | Distributed tracing for processing pipeline | 2-3 days |

## Feature Summary

| Feature | ADR | Status |
|---------|-----|--------|
| Technology stack | ADR-001 | Implemented |
| HNSW vector index | ADR-002 | Implemented |
| LLM classification (GPT-4o-mini) | ADR-003 | Implemented |
| Version comparison (hybrid) | ADR-004 | Implemented (pgvector nearest-neighbor) |
| Classification pipeline optimization | ADR-007 | Implemented (84s -> 12s) |
| CVSS-inspired risk scoring | ADR-008 | Implemented |
| Structured outputs + few-shot | ADR-009 | Implemented |
| Docling parsing + section chunking | ADR-010 | Implemented |
| Evaluation framework | ADR-011 | Implemented (96.6% baseline) |
| Embedding model upgrade | ADR-012 | Implemented (text-embedding-3-large) |
| AI observability (Langfuse) | ADR-013 | Implemented |
| AI security (sanitization + anomaly) | ADR-014 | Implemented (Phase 1) |
| CI/CD eval gate | ADR-015 | Implemented |
| Configurable clause taxonomy | ADR-006 | Implemented (Phase 1-3, YAML + 23 types) |
| Custom types UI | ADR-006 Phase 4-5 | Planned |
| Real-time updates (SSE) | ADR-005 | Proposed |
| Perspective-aware risk scoring | ADR-003 addendum | Proposed |
| Redis caching + rate limiting | ADR-014 Phase 2 | Planned |
| Testing suite (unit/integration/E2E) | - | Planned |
| Production deployment | - | Planned |

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Supabase free tier limits | Connection/storage caps hit under load | Upgrade plan or migrate to self-hosted Postgres |
| OpenAI API cost scaling | More types in prompt = more tokens per classification | Monitor token usage, cap custom types at 20 |
| Re-classification cost | Expanding taxonomy means re-processing all existing documents | Make re-classification opt-in per document, batch during off-hours |
| Supabase Realtime limits | Free tier caps real-time connections | Implement graceful fallback to polling |
| Migration complexity | DB schema changes across v1.1→v2.0 | Use Alembic for versioned migrations, test on staging first |

## Success Criteria for v2.0

- [ ] All 25 known gaps resolved
- [ ] Clause types configurable via YAML (built-in) and UI (custom)
- [ ] LLM prompt built dynamically — zero hardcoded type lists in Python code
- [ ] Section-aware comparison producing accurate change counts
- [ ] Real-time processing updates (< 100ms latency)
- [ ] Backend test coverage > 70%
- [ ] CI/CD pipeline with automated deploy
- [ ] Deployed to staging environment (not just localhost)
