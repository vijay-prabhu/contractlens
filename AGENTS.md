# ContractLens — Agent Instructions

AI-powered contract review and risk analysis platform. FastAPI + Next.js 14 + PostgreSQL/pgvector + OpenAI.

## Architecture

```
backend/app/
  api/            # FastAPI route handlers — thin, delegate to services
  api/dependencies.py  # Depends() factories for service injection
  core/           # Config, auth, database, constants, middleware
  models/         # SQLAlchemy async models (document, clause, user)
  services/       # Business logic (extraction, chunking, embedding, classification, comparison, search)
  workers/        # Background document processor
frontend/src/
  app/            # Next.js 14 App Router pages
  components/     # React components
  lib/            # API client, Supabase client, constants, utilities
  types/          # TypeScript type definitions
```

## Code Patterns

### Backend (Python)

**Use dependency injection for services:**
```python
# GOOD — injectable, testable
async def upload_document(
    service: DocumentService = Depends(get_document_service),
):

# BAD — hard-wired
async def upload_document(db: AsyncSession = Depends(get_db)):
    service = DocumentService(db)
```

**Keep route handlers thin — business logic goes in services:**
```python
# GOOD
clauses = await service.get_document_clauses(document_id)
risk = classification_service.calculate_document_risk_summary(results)

# BAD — risk calculation logic inside route handler
for clause in clauses:
    risk_counts[clause.risk_level] += 1
avg_risk_score = total / len(clauses)
```

**Use constants, not magic numbers:**
```python
# GOOD
from app.core.constants import SIMILARITY_SAME_THRESHOLD
if similarity >= SIMILARITY_SAME_THRESHOLD:

# BAD
if similarity >= 0.85:
```

**datetime must be timezone-aware:**
```python
# GOOD
from datetime import datetime, timezone
datetime.now(timezone.utc)

# BAD — deprecated in Python 3.12+
datetime.utcnow()
```

**Never log secrets or tokens:**
```python
# GOOD
logger.debug("Attempting to decode JWT token")

# BAD
logger.info(f"Token: {token[:50]}...")
```

**Imports at top of file, never inside functions.**

### Frontend (TypeScript/React)

**TypeScript strict mode is on. No `any` types.**

**Use constants from `@/lib/constants.ts` for intervals/timeouts:**
```typescript
import { POLLING_INTERVAL_MS } from '@/lib/constants'
setInterval(poll, POLLING_INTERVAL_MS)
```

**Upload methods use `uploadWithAuth()` — don't duplicate auth logic.**

**Error boundaries exist at route level. Every `app/*/error.tsx` handles crashes.**

**Client components use `'use client'` directive. Server components are default.**

## Running the Project

```bash
# Local development (preferred)
./dev-start.sh        # Starts backend (port 8200) + frontend (port 3200)
./dev-stop.sh         # Stops all services
./dev-logs.sh [backend|frontend]  # View logs

# Docker (for deployment/CI)
docker compose up
```

## Testing

```bash
cd backend && poetry run pytest -v
```

## Database

PostgreSQL on Supabase with pgvector extension. HNSW index on clause embeddings.

**pgvector queries use raw SQL with parameterized embedding strings:**
```python
embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
sql = text("SELECT 1 - (c.embedding <=> cast(:embedding as vector)) as similarity ...")
```

## Key Conventions

- Backend port: 8200, Frontend port: 3200
- Python line length: 100 (ruff + black)
- Config in `backend/app/core/config.py` via pydantic-settings
- Constants in `backend/app/core/constants.py`
- Frontend constants in `frontend/src/lib/constants.ts`
- CORS origins configurable via `CORS_ORIGINS` env var
- Sentry for error tracking on both sides
- ADRs in `docs/adr/` — check before making architectural changes

## Anti-Patterns to Avoid

- Don't instantiate services inside route handlers — use Depends()
- Don't put business logic in API handlers — use service layer
- Don't hardcode thresholds, timeouts, or intervals — use constants
- Don't swallow exceptions silently — log and handle explicitly
- Don't use `datetime.utcnow()` — use `datetime.now(timezone.utc)`
- Don't log token content, API keys, or PII
- Don't add `any` types in TypeScript
- Don't duplicate auth logic in API client — use shared helpers
