# ContractLens Architecture

## Overview

ContractLens is an AI-powered contract review and risk analysis tool that helps legal teams analyze contracts quickly and efficiently. The system extracts text from legal documents, classifies clauses using LLMs, scores risk levels, and enables semantic search across documents.

## Current System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 14)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   Landing   │  │    Auth     │  │       Dashboard         │  │
│  │    Page     │  │ Login/Signup│  │  Upload │ List │ Detail │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│                              │                                   │
│  ┌───────────────────────────┴───────────────────────────────┐  │
│  │  Supabase SSR Auth (@supabase/ssr) + Middleware           │  │
│  │  Cookie-based sessions, route protection                  │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                │
                    REST API + JWT Bearer Token
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Middleware Layer                      │    │
│  │  • Request logging (X-Request-ID)                       │    │
│  │  • Security headers (X-Frame-Options, etc.)             │    │
│  │  • CORS configuration                                    │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    API Layer (/api/v1)                   │    │
│  │  documents.py │ search.py │ comparison.py               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Service Layer                          │    │
│  │  extraction │ chunking │ embedding │ classification     │    │
│  │  document   │ search   │ comparison                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              Background Worker (Polling)                 │    │
│  │  document_processor.py - 5 second polling interval       │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                                │
                ┌───────────────┼───────────────┐
                ▼               ▼               ▼
        ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
        │  PostgreSQL  │ │   Supabase   │ │   OpenAI     │
        │  + pgvector  │ │   Storage    │ │     API      │
        │  (Supabase)  │ │              │ │              │
        └──────────────┘ └──────────────┘ └──────────────┘
```

## Component Details

### Frontend (Next.js 14)

**Technology**: Next.js 14 App Router, TypeScript, Tailwind CSS

| Component | Purpose |
|-----------|---------|
| `app/page.tsx` | Landing page with feature highlights |
| `app/login/page.tsx` | Email/password login form |
| `app/signup/page.tsx` | User registration with email confirmation |
| `app/dashboard/page.tsx` | Document list with status polling |
| `app/dashboard/upload/page.tsx` | Drag-and-drop file upload |
| `app/dashboard/documents/[id]/page.tsx` | Risk analysis view |

**Authentication Flow**:
1. User signs up/logs in via Supabase Auth
2. `@supabase/ssr` manages cookie-based sessions
3. Middleware (`middleware.ts`) refreshes tokens and protects routes
4. API client attaches JWT to all backend requests

### Backend (FastAPI)

**Technology**: FastAPI, SQLAlchemy (async), psycopg3

#### API Endpoints

| Endpoint | Handler | Purpose |
|----------|---------|---------|
| `POST /documents/upload` | `documents.py` | Upload and store documents |
| `GET /documents/{id}/analysis` | `documents.py` | Retrieve risk analysis |
| `GET /search` | `search.py` | Semantic search across clauses |
| `GET /compare` | `comparison.py` | Compare document versions |

#### Service Layer

| Service | Responsibility |
|---------|----------------|
| `extraction_service.py` | PDF (PyMuPDF) and DOCX (python-docx) text extraction |
| `chunking_service.py` | LangChain RecursiveCharacterTextSplitter (800 chars, 150 overlap) |
| `embedding_service.py` | OpenAI text-embedding-3-small (1536 dimensions) |
| `classification_service.py` | GPT-4o-mini clause classification and risk scoring |
| `search_service.py` | pgvector cosine similarity search |
| `comparison_service.py` | Text diff (difflib) + semantic diff (embeddings) |
| `document_service.py` | Document CRUD, storage operations |

#### Background Processing

**Current Implementation**: Polling-based worker
- `document_processor.py` polls every 5 seconds for `status='uploaded'` documents
- Processes sequentially: extract → chunk → embed → classify
- Updates status: `uploaded` → `processing` → `completed` / `failed`

### Database (PostgreSQL + pgvector)

**Hosting**: Supabase (Transaction pooler at port 6543)

**Schema**:
```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│    users    │     │    documents     │     │ document_versions│
├─────────────┤     ├──────────────────┤     ├─────────────────┤
│ id (PK)     │◄────│ user_id (FK)     │     │ id (PK)         │
│ email       │     │ id (PK)          │◄────│ document_id (FK)│
│ name        │     │ filename         │     │ version_number  │
│ created_at  │     │ status           │     │ storage_path    │
└─────────────┘     │ error_message    │     │ created_at      │
                    │ extracted_text   │     └─────────────────┘
                    │ created_at       │              │
                    └──────────────────┘              │
                                                      ▼
                                              ┌─────────────────┐
                                              │     clauses     │
                                              ├─────────────────┤
                                              │ id (PK)         │
                                              │ version_id (FK) │
                                              │ text            │
                                              │ clause_type     │
                                              │ risk_level      │
                                              │ risk_score      │
                                              │ risk_explanation│
                                              │ embedding (1536)│
                                              │ start_pos       │
                                              │ end_pos         │
                                              └─────────────────┘
```

**Vector Index**: HNSW (Hierarchical Navigable Small World)
- Works correctly at any dataset size (unlike ivfflat)
- Parameters: `m=16, ef_construction=64`
- See [ADR-002](adr/ADR-002-vector-index-selection.md)

### External Services

| Service | Purpose | Model/Details |
|---------|---------|---------------|
| OpenAI Embeddings | Vector generation | text-embedding-3-small (1536 dims) |
| OpenAI Chat | Clause classification | GPT-4o-mini, temperature=0.1 |
| Supabase Storage | File storage | `documents` bucket |
| Supabase Auth | Authentication | JWT with ES256 signing |

## Data Flow

### Document Upload & Processing

```
1. User uploads file (PDF/DOCX)
         │
         ▼
2. Backend validates file (type, size ≤ 10MB)
         │
         ▼
3. File stored in Supabase Storage
   Document record created (status: 'uploaded')
         │
         ▼
4. Background worker picks up document
   Status → 'processing'
         │
         ▼
5. Text extraction (PyMuPDF / python-docx)
         │
         ▼
6. Text chunking (800 chars, 150 overlap)
         │
         ▼
7. Batch embedding generation (OpenAI)
         │
         ▼
8. Clause classification + risk scoring (GPT-4o-mini)
         │
         ▼
9. Clauses saved with embeddings to pgvector
   Status → 'completed'
         │
         ▼
10. Frontend polls and displays results
```

### Semantic Search

```
1. User enters search query
         │
         ▼
2. Query embedded via OpenAI
         │
         ▼
3. pgvector cosine similarity search
   (HNSW index, filtered by user's documents)
         │
         ▼
4. Results ranked by similarity score
   (min_similarity threshold: 0.5)
```

### Version Comparison

```
1. User selects two document versions
         │
         ▼
2. Text diff using Python difflib
   (additions, deletions, modifications)
         │
         ▼
3. Semantic clause matching using embeddings
   - Same clause: similarity ≥ 0.85
   - Modified clause: 0.6 ≤ similarity < 0.85
   - Added/Removed: similarity < 0.6
         │
         ▼
4. Risk delta calculation
   (compare aggregate risk scores)
```

## Authentication & Security

### JWT Authentication

1. **Token Source**: Supabase Auth issues JWTs
2. **Signing Algorithm**: ES256 (ECDSA with P-256 curve)
   - Backend handles both HS256 (legacy) and ES256 (current)
3. **Validation**: Backend verifies signature and expiration
4. **User Binding**: Documents filtered by `user_id` from JWT

### Security Measures

| Measure | Implementation |
|---------|----------------|
| File validation | Type (PDF/DOCX only), size (≤ 10MB) |
| SQL injection | SQLAlchemy ORM with parameterized queries |
| XSS prevention | React's automatic escaping |
| CORS | Configured for frontend origin only |
| Security headers | X-Frame-Options, X-Content-Type-Options |
| Secrets | Environment variables, not committed |

## Performance Considerations

### Current Optimizations

- **HNSW index**: O(log n) vector search vs O(n) sequential scan
- **Batch embeddings**: Multiple chunks embedded in single API call
- **Connection pooling**: psycopg3 with Supabase transaction pooler
- **Async I/O**: SQLAlchemy async for non-blocking database operations

### Known Limitations

- **Polling latency**: 5-second delay for status updates
- **Sequential processing**: One document at a time
- **No caching**: Embeddings regenerated on each search query

## Future Architecture

### Planned Enhancements

```
                    [Future Components - Dotted Lines]

┌─────────────────────────────────────────────────────────────────┐
│                     Frontend (Next.js 14)                        │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │  WebSocket Client │  ◄── Real-time updates │
│                    └───────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Backend (FastAPI)                           │
│                              │                                   │
│         ┌────────────────────┼────────────────────┐             │
│         ▼                    ▼                    ▼             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐     │
│  │  WebSocket  │    │   Redis     │    │  Task Queue     │     │
│  │  Manager    │    │   Cache     │    │  (Celery/ARQ)   │     │
│  └─────────────┘    └─────────────┘    └─────────────────┘     │
└─────────────────────────────────────────────────────────────────┘
```

**Redis** (Planned):
- Cache embeddings to avoid regeneration
- Cache analysis results for repeat views
- Rate limiting token bucket

**WebSocket** (Planned):
- Real-time processing progress updates
- Eliminate polling latency
- Connection per user session

**Task Queue** (Planned):
- Celery or ARQ for distributed processing
- Parallel document processing
- Retry logic for failed jobs

## Deployment Architecture (Planned)

```
┌──────────────────┐     ┌──────────────────┐
│      Vercel      │     │  Railway/Render  │
│    (Frontend)    │────▶│    (Backend)     │
│   Next.js SSR    │     │     FastAPI      │
└──────────────────┘     └──────────────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    ▼             ▼             ▼
             ┌──────────┐  ┌──────────┐  ┌──────────┐
             │ Supabase │  │ Supabase │  │  OpenAI  │
             │    DB    │  │ Storage  │  │   API    │
             └──────────┘  └──────────┘  └──────────┘
```

## Monitoring & Observability (Planned)

| Aspect | Tool/Approach |
|--------|---------------|
| Logging | Structured JSON logs, X-Request-ID tracing |
| Metrics | Prometheus + Grafana |
| Error tracking | Sentry |
| APM | OpenTelemetry |

## References

- [ADR-001: Technology Stack](adr/ADR-001-technology-stack.md)
- [ADR-002: Vector Index Selection](adr/ADR-002-vector-index-selection.md)
- [ADR-003: LLM Classification Strategy](adr/ADR-003-llm-classification-strategy.md)
- [ADR-004: Version Comparison Strategy](adr/ADR-004-version-comparison-strategy.md)
- [ADR-005: Real-time Update Architecture](adr/ADR-005-realtime-architecture.md)
- [ADR-006: Configurable Clause Taxonomy](adr/ADR-006-configurable-clause-taxonomy.md)
- [v2.0 Roadmap](roadmap-v2.md)
