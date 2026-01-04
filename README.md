# ContractLens

AI-powered contract review and risk analysis tool that helps legal teams and businesses analyze contracts quickly and efficiently.

## Features

### Current (MVP)
- **Document Upload**: Drag-and-drop PDF/DOCX upload with validation (10MB limit)
- **AI-Powered Analysis**: Automatic clause classification using GPT-4o-mini
- **Risk Scoring**: Four-level risk assessment (Critical/High/Medium/Low) with explanations
- **Semantic Search**: Vector-based search across document clauses using pgvector
- **Version Comparison**: Text and semantic diff between document versions
- **Authentication**: Secure JWT-based auth with Supabase Auth

### Clause Types Detected
Indemnification, Limitation of Liability, Termination, Confidentiality, Payment Terms, Intellectual Property, Governing Law, Force Majeure, Warranty, Dispute Resolution, Assignment, Notice, Amendment, Entire Agreement

## Tech Stack

### Backend
- **Framework**: FastAPI (Python 3.11)
- **Database**: PostgreSQL + pgvector (Supabase)
- **ORM**: SQLAlchemy (async with psycopg3)
- **AI**: OpenAI API (text-embedding-3-small + GPT-4o-mini)
- **Document Processing**: PyMuPDF, python-docx, LangChain

### Frontend
- **Framework**: Next.js 14 (App Router)
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Auth**: @supabase/ssr

### Infrastructure
- **Database & Auth**: Supabase
- **Storage**: Supabase Storage
- **Deployment**: Vercel (frontend), Railway/Render (backend) - planned

## Project Structure

```
contractlens/
├── backend/
│   ├── app/
│   │   ├── api/           # REST endpoints
│   │   ├── core/          # Config, auth, middleware
│   │   ├── models/        # SQLAlchemy models
│   │   ├── services/      # Business logic
│   │   └── workers/       # Background processing
│   ├── migrations/        # SQL migrations
│   ├── tests/             # pytest tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/           # Next.js pages
│   │   ├── components/    # React components
│   │   ├── lib/           # API client, utilities
│   │   └── types/         # TypeScript definitions
│   └── package.json
└── docs/
    ├── architecture.md
    └── adr/               # Architecture Decision Records
```

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 20+
- Supabase account (free tier works)
- OpenAI API key

### Environment Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/vijay-prabhu/contractlens.git
   cd contractlens
   ```

2. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your credentials:
   # - SUPABASE_URL
   # - SUPABASE_ANON_KEY
   # - SUPABASE_SERVICE_ROLE_KEY
   # - SUPABASE_JWT_SECRET
   # - DATABASE_URL (Supabase connection string)
   # - OPENAI_API_KEY
   ```

3. **Set up the backend**
   ```bash
   cd backend
   poetry install

   # Run database migrations (execute in Supabase SQL editor)
   # See migrations/ folder for SQL files
   ```

4. **Set up the frontend**
   ```bash
   cd frontend
   npm install

   # Create frontend .env.local
   cp .env.example .env.local
   # Add NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY
   ```

### Running the Application

**Terminal 1 - Backend:**
```bash
cd backend
poetry run uvicorn app.main:app --reload --port 8000
```
API docs available at: http://localhost:8000/docs

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```
Frontend available at: http://localhost:3000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/documents/upload` | Upload PDF/DOCX document |
| GET | `/api/v1/documents` | List user's documents |
| GET | `/api/v1/documents/{id}` | Get document details |
| GET | `/api/v1/documents/{id}/analysis` | Get risk analysis with clauses |
| GET | `/api/v1/documents/{id}/versions` | List document versions |
| POST | `/api/v1/documents/{id}/versions` | Upload new version |
| POST | `/api/v1/documents/{id}/process` | Manually trigger processing |
| DELETE | `/api/v1/documents/{id}` | Delete document |
| GET | `/api/v1/search?q=...` | Semantic search across clauses |
| GET | `/api/v1/search/similar/{clause_id}` | Find similar clauses |
| GET | `/api/v1/compare?version1=...&version2=...` | Compare two versions |

All endpoints except `/health` require JWT authentication via `Authorization: Bearer <token>` header.

## Running Tests

```bash
cd backend
poetry run pytest -v

# Run with coverage
poetry run pytest --cov=app --cov-report=html
```

Current test coverage: 38 tests passing (auth, documents, search, comparison)

## Architecture Decisions

Key technical decisions are documented in Architecture Decision Records (ADRs):

- [ADR-001: Technology Stack Selection](docs/adr/ADR-001-technology-stack.md)
- [ADR-002: Vector Index Selection (HNSW vs ivfflat)](docs/adr/ADR-002-vector-index-selection.md)
- [ADR-003: LLM Classification Strategy](docs/adr/ADR-003-llm-classification-strategy.md)
- [ADR-004: Version Comparison Strategy](docs/adr/ADR-004-version-comparison-strategy.md)

## Future Enhancements

### Completed
- [x] Search page with semantic search UI
- [x] Version comparison diff view (side-by-side)

### High Priority (UX Improvements)
- [ ] Expand/collapse clause text in analysis view
- [ ] Filter clauses by risk level (Critical/High/Medium/Low)
- [ ] Toast notifications for user feedback
- [ ] Progress bar during document processing
- [ ] Add recommendations to clause analysis output

### Medium Priority (Features)
- [ ] Export analysis to PDF report
- [ ] Batch upload for multiple files
- [ ] Clause highlighting in original document preview
- [ ] User settings/profile page
- [ ] Dark mode toggle
- [ ] WebSocket for real-time processing updates

### Low Priority (Nice-to-Have)
- [ ] Real-time collaboration
- [ ] Custom risk thresholds per user
- [ ] Contract templates library
- [ ] AI-powered contract drafting suggestions
- [ ] Integration with DocuSign/Adobe Sign
- [ ] Mobile app (React Native)

### Pre-Deployment (Production Readiness)
- [ ] Sentry.io integration (Frontend + Backend error tracking)
- [ ] Performance monitoring with Sentry tracing
- [ ] E2E tests with Playwright
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Rate limiting on API endpoints
- [ ] Deploy to Vercel (Frontend) + Supabase production

### Technical Debt
- [ ] Proper ES256 JWT verification with Supabase public key
- [ ] Redis caching for embeddings and analysis results
- [ ] Better error handling and retry logic for OpenAI calls
- [ ] Optimize API response times (database connection pooling)
- [ ] Response caching for frequently accessed data
- [ ] Loading skeletons for better perceived performance
- [ ] Lazy load clause list for large documents

## Key Learnings

1. **pgvector index selection**: ivfflat fails on small datasets; HNSW works at any scale
2. **Supabase JWT migration**: Handles both HS256 (legacy) and ES256 (current) signing
3. **PyJWT expiration**: Requires explicit `verify_exp: True` and timezone-aware datetime
4. **LLM structured output**: Low temperature (0.1) + JSON schema = reliable parsing

## License

Private - All rights reserved.
